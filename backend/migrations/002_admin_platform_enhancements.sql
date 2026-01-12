-- Admin Platform Enhancements Migration
-- This migration adds support for:
-- - Enhanced document workflow with approval system
-- - Notification system for real-time updates
-- - Document approvals tracking
-- - Performance optimizations with indexes

-- ============================================================================
-- 1. UPDATE DOCUMENTS TABLE WITH NEW COLUMNS AND STATUS ENUM
-- ============================================================================

-- First, drop the existing status constraint
ALTER TABLE documents 
DROP CONSTRAINT IF EXISTS documents_status_check;

-- Add new columns to documents table (without foreign keys first)
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS file_type TEXT,
ADD COLUMN IF NOT EXISTS file_size BIGINT,
ADD COLUMN IF NOT EXISTS uploaded_by UUID,
ADD COLUMN IF NOT EXISTS approved_by UUID,
ADD COLUMN IF NOT EXISTS approval_comments TEXT,
ADD COLUMN IF NOT EXISTS error_message TEXT,
ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ;

-- Add foreign key constraints separately (for idempotency)
ALTER TABLE documents 
DROP CONSTRAINT IF EXISTS documents_uploaded_by_fkey,
DROP CONSTRAINT IF EXISTS documents_approved_by_fkey;

ALTER TABLE documents
ADD CONSTRAINT documents_uploaded_by_fkey 
FOREIGN KEY (uploaded_by) REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE documents
ADD CONSTRAINT documents_approved_by_fkey 
FOREIGN KEY (approved_by) REFERENCES auth.users(id) ON DELETE SET NULL;

-- Update status enum to include new statuses
ALTER TABLE documents 
ADD CONSTRAINT documents_status_check 
CHECK (status IN ('uploaded', 'pending_approval', 'approved', 'rejected', 'processing', 'completed', 'failed'));

-- Update default status for new documents
ALTER TABLE documents 
ALTER COLUMN status SET DEFAULT 'uploaded';

-- ============================================================================
-- 2. CREATE NOTIFICATIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN (
        'document_uploaded',
        'document_approved', 
        'document_rejected',
        'document_processed',
        'document_failed'
    )),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    read_at TIMESTAMPTZ
);

-- Enable RLS for notifications
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- Notification policies - users can only see their own notifications
CREATE POLICY "Users can view their own notifications" 
ON notifications FOR SELECT 
USING (auth.uid() = recipient_id);

CREATE POLICY "Users can update their own notifications" 
ON notifications FOR UPDATE 
USING (auth.uid() = recipient_id);

-- Allow system to create notifications (service role)
CREATE POLICY "System can create notifications" 
ON notifications FOR INSERT 
WITH CHECK (true);

-- ============================================================================
-- 3. CREATE DOCUMENT APPROVALS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    approved_by UUID NOT NULL REFERENCES auth.users(id),
    action TEXT NOT NULL CHECK (action IN ('approved', 'rejected')),
    comments TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS for document approvals
ALTER TABLE document_approvals ENABLE ROW LEVEL SECURITY;

-- Document approval policies
CREATE POLICY "Super admins can manage document approvals" 
ON document_approvals FOR ALL 
USING (
    EXISTS (
        SELECT 1 FROM profiles 
        WHERE profiles.id = auth.uid() 
        AND profiles.role = 'super_admin'
    )
);

-- College admins can view approvals for their college's documents
CREATE POLICY "College admins can view their college document approvals" 
ON document_approvals FOR SELECT 
USING (
    EXISTS (
        SELECT 1 FROM documents d
        JOIN profiles p ON p.id = auth.uid()
        WHERE d.id = document_approvals.document_id
        AND d.college_id = p.college_id
        AND p.role = 'college_admin'
    )
);

-- ============================================================================
-- 4. CREATE PERFORMANCE INDEXES
-- ============================================================================

-- Notifications indexes
CREATE INDEX IF NOT EXISTS idx_notifications_recipient_id ON notifications(recipient_id);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(recipient_id, is_read) WHERE is_read = FALSE;
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type);

-- Document approvals indexes
CREATE INDEX IF NOT EXISTS idx_document_approvals_document_id ON document_approvals(document_id);
CREATE INDEX IF NOT EXISTS idx_document_approvals_approved_by ON document_approvals(approved_by);
CREATE INDEX IF NOT EXISTS idx_document_approvals_created_at ON document_approvals(created_at DESC);

-- Enhanced documents table indexes
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_documents_approved_by ON documents(approved_by);
CREATE INDEX IF NOT EXISTS idx_documents_college_status ON documents(college_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_processed_at ON documents(processed_at DESC) WHERE processed_at IS NOT NULL;

-- Existing table performance improvements
CREATE INDEX IF NOT EXISTS idx_profiles_college_role ON profiles(college_id, role);
CREATE INDEX IF NOT EXISTS idx_document_chunks_college_id ON document_chunks(college_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_college ON conversations(user_id, college_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at);

-- ============================================================================
-- 5. UPDATE EXISTING DATA (MIGRATION LOGIC)
-- ============================================================================

-- Update existing documents to have 'completed' status if they have embeddings
-- This assumes documents with embeddings in document_chunks are already processed
-- Use created_at as processed_at since we don't have a reliable updated_at timestamp
UPDATE documents 
SET status = 'completed', 
    processed_at = created_at
WHERE status = 'processing' 
AND EXISTS (
    SELECT 1 FROM document_chunks 
    WHERE document_chunks.document_id = documents.id
);

-- Update remaining 'processing' documents to 'failed' if they don't have embeddings
-- and were created more than 1 hour ago (assuming processing should complete within 1 hour)
UPDATE documents 
SET status = 'failed',
    error_message = 'Processing timeout - migrated from legacy status'
WHERE status = 'processing' 
AND created_at < (now() - INTERVAL '1 hour')
AND NOT EXISTS (
    SELECT 1 FROM document_chunks 
    WHERE document_chunks.document_id = documents.id
);

-- ============================================================================
-- 6. CREATE HELPER FUNCTIONS FOR COMMON OPERATIONS
-- ============================================================================

-- Function to create notifications
CREATE OR REPLACE FUNCTION create_notification(
    p_recipient_id UUID,
    p_type TEXT,
    p_title TEXT,
    p_content TEXT,
    p_metadata JSONB DEFAULT '{}'
) RETURNS UUID AS $$
DECLARE
    notification_id UUID;
BEGIN
    INSERT INTO notifications (recipient_id, type, title, content, metadata)
    VALUES (p_recipient_id, p_type, p_title, p_content, p_metadata)
    RETURNING id INTO notification_id;
    
    RETURN notification_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get unread notification count
CREATE OR REPLACE FUNCTION get_unread_notification_count(p_user_id UUID)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)::INTEGER 
        FROM notifications 
        WHERE recipient_id = p_user_id 
        AND is_read = FALSE
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to mark notification as read
CREATE OR REPLACE FUNCTION mark_notification_read(p_notification_id UUID, p_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE notifications 
    SET is_read = TRUE, read_at = now()
    WHERE id = p_notification_id 
    AND recipient_id = p_user_id 
    AND is_read = FALSE;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- 7. TRIGGERS FOR AUTOMATIC NOTIFICATION CREATION
-- ============================================================================

-- Trigger function to create notifications on document status changes
CREATE OR REPLACE FUNCTION notify_document_status_change()
RETURNS TRIGGER AS $$
DECLARE
    college_admins UUID[];
    super_admins UUID[];
    admin_id UUID;
    notification_title TEXT;
    notification_content TEXT;
    notification_type TEXT;
BEGIN
    -- Determine notification type and content based on status change
    CASE NEW.status
        WHEN 'uploaded' THEN
            notification_type := 'document_uploaded';
            notification_title := 'New Document Uploaded';
            notification_content := 'Document "' || NEW.filename || '" has been uploaded and is awaiting approval.';
            
            -- Notify all super admins
            SELECT ARRAY_AGG(id) INTO super_admins
            FROM profiles WHERE role = 'super_admin';
            
            FOREACH admin_id IN ARRAY super_admins
            LOOP
                PERFORM create_notification(
                    admin_id,
                    notification_type,
                    notification_title,
                    notification_content,
                    jsonb_build_object('document_id', NEW.id, 'college_id', NEW.college_id)
                );
            END LOOP;
            
        WHEN 'approved' THEN
            notification_type := 'document_approved';
            notification_title := 'Document Approved';
            notification_content := 'Your document "' || NEW.filename || '" has been approved for processing.';
            
            -- Notify the uploader
            IF NEW.uploaded_by IS NOT NULL THEN
                PERFORM create_notification(
                    NEW.uploaded_by,
                    notification_type,
                    notification_title,
                    notification_content,
                    jsonb_build_object('document_id', NEW.id, 'approved_by', NEW.approved_by)
                );
            END IF;
            
        WHEN 'rejected' THEN
            notification_type := 'document_rejected';
            notification_title := 'Document Rejected';
            notification_content := 'Your document "' || NEW.filename || '" has been rejected.';
            
            -- Notify the uploader
            IF NEW.uploaded_by IS NOT NULL THEN
                PERFORM create_notification(
                    NEW.uploaded_by,
                    notification_type,
                    notification_title,
                    notification_content,
                    jsonb_build_object('document_id', NEW.id, 'rejected_by', NEW.approved_by, 'reason', NEW.approval_comments)
                );
            END IF;
            
        WHEN 'completed' THEN
            notification_type := 'document_processed';
            notification_title := 'Document Processing Complete';
            notification_content := 'Your document "' || NEW.filename || '" has been successfully processed and is now available for queries.';
            
            -- Notify the uploader
            IF NEW.uploaded_by IS NOT NULL THEN
                PERFORM create_notification(
                    NEW.uploaded_by,
                    notification_type,
                    notification_title,
                    notification_content,
                    jsonb_build_object('document_id', NEW.id, 'processed_at', NEW.processed_at)
                );
            END IF;
            
        WHEN 'failed' THEN
            notification_type := 'document_failed';
            notification_title := 'Document Processing Failed';
            notification_content := 'Processing failed for document "' || NEW.filename || '". Please check the error details and try again.';
            
            -- Notify the uploader
            IF NEW.uploaded_by IS NOT NULL THEN
                PERFORM create_notification(
                    NEW.uploaded_by,
                    notification_type,
                    notification_title,
                    notification_content,
                    jsonb_build_object('document_id', NEW.id, 'error_message', NEW.error_message)
                );
            END IF;
    END CASE;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for document status changes
DROP TRIGGER IF EXISTS trigger_document_status_notification ON documents;
CREATE TRIGGER trigger_document_status_notification
    AFTER UPDATE OF status ON documents
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION notify_document_status_change();

-- ============================================================================
-- 8. GRANT NECESSARY PERMISSIONS
-- ============================================================================

-- Grant permissions for the notification functions
GRANT EXECUTE ON FUNCTION create_notification(UUID, TEXT, TEXT, TEXT, JSONB) TO authenticated;
GRANT EXECUTE ON FUNCTION get_unread_notification_count(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION mark_notification_read(UUID, UUID) TO authenticated;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Admin Platform Enhancements migration completed successfully';
    RAISE NOTICE 'Added tables: notifications, document_approvals';
    RAISE NOTICE 'Updated documents table with new columns and status enum';
    RAISE NOTICE 'Created performance indexes for all tables';
    RAISE NOTICE 'Added notification triggers and helper functions';
END $$;
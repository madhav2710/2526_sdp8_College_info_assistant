-- Robustness Improvements Migration
-- This migration adds:
-- - Document processing control (scheduling)
-- - Status history tracking
-- - File validation metadata

-- ============================================================================
-- 1. ADD PROCESSING CONTROL FIELDS TO DOCUMENTS TABLE
-- ============================================================================

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS process_schedule TEXT DEFAULT 'immediate' 
    CHECK (process_schedule IN ('immediate', 'scheduled', 'manual')),
ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS file_hash TEXT,  -- For duplicate detection
ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ;

-- Add index for scheduled documents
CREATE INDEX IF NOT EXISTS idx_documents_scheduled 
ON documents(scheduled_at) 
WHERE process_schedule = 'scheduled' AND status = 'approved';

-- ============================================================================
-- 2. CREATE STATUS HISTORY TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT,
    changed_by UUID REFERENCES auth.users(id),
    comments TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_status_history_document 
ON document_status_history(document_id, created_at DESC);

-- Enable RLS for status history
ALTER TABLE document_status_history ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Super admins can view all status history" ON document_status_history;
DROP POLICY IF EXISTS "College admins can view their college status history" ON document_status_history;

-- Super admins can view all status history
CREATE POLICY "Super admins can view all status history" 
ON document_status_history FOR SELECT 
USING (
    EXISTS (
        SELECT 1 FROM profiles 
        WHERE profiles.id = auth.uid() 
        AND profiles.role = 'super_admin'
    )
);

-- College admins can view status history for their college's documents
CREATE POLICY "College admins can view their college status history" 
ON document_status_history FOR SELECT 
USING (
    EXISTS (
        SELECT 1 FROM documents d
        JOIN profiles p ON p.id = auth.uid()
        WHERE d.id = document_status_history.document_id
        AND d.college_id = p.college_id
        AND p.role = 'college_admin'
    )
);

-- ============================================================================
-- 3. CREATE FUNCTION TO LOG STATUS CHANGES
-- ============================================================================

CREATE OR REPLACE FUNCTION log_document_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO document_status_history (
            document_id,
            old_status,
            new_status,
            changed_by,
            comments
        ) VALUES (
            NEW.id,
            OLD.status,
            NEW.status,
            NEW.approved_by,  -- Usually the person who changed it
            NEW.approval_comments
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for status history
DROP TRIGGER IF EXISTS trigger_document_status_history ON documents;
CREATE TRIGGER trigger_document_status_history
    AFTER UPDATE OF status ON documents
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION log_document_status_change();

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Robustness improvements migration completed successfully';
    RAISE NOTICE 'Added processing control fields to documents table';
    RAISE NOTICE 'Created document_status_history table';
    RAISE NOTICE 'Added status change logging trigger';
END $$;


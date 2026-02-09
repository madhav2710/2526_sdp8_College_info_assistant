-- Hotfix: prevent "CASE statement is missing ELSE part" in document status trigger.
-- Run this on existing databases where approvals fail with:
--   {"code":"20000","message":"case not found"}

CREATE OR REPLACE FUNCTION public.notify_document_status_change()
RETURNS TRIGGER AS $$
DECLARE
    super_admins UUID[];
    admin_id UUID;
    notification_title TEXT;
    notification_content TEXT;
    notification_type TEXT;
BEGIN
    CASE NEW.status
        WHEN 'uploaded' THEN
            notification_type := 'document_uploaded';
            notification_title := 'New Document Uploaded';
            notification_content := 'Document "' || NEW.filename || '" has been uploaded and is awaiting approval.';

            SELECT ARRAY_AGG(id) INTO super_admins
            FROM public.profiles
            WHERE role = 'super_admin';

            IF super_admins IS NOT NULL THEN
                FOREACH admin_id IN ARRAY super_admins
                LOOP
                    PERFORM public.create_notification(
                        admin_id,
                        notification_type,
                        notification_title,
                        notification_content,
                        jsonb_build_object('document_id', NEW.id, 'college_id', NEW.college_id)
                    );
                END LOOP;
            END IF;

        WHEN 'approved' THEN
            notification_type := 'document_approved';
            notification_title := 'Document Approved';
            notification_content := 'Your document "' || NEW.filename || '" has been approved for processing.';

            IF NEW.uploaded_by IS NOT NULL THEN
                PERFORM public.create_notification(
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

            IF NEW.uploaded_by IS NOT NULL THEN
                PERFORM public.create_notification(
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

            IF NEW.uploaded_by IS NOT NULL THEN
                PERFORM public.create_notification(
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

            IF NEW.uploaded_by IS NOT NULL THEN
                PERFORM public.create_notification(
                    NEW.uploaded_by,
                    notification_type,
                    notification_title,
                    notification_content,
                    jsonb_build_object('document_id', NEW.id, 'error_message', NEW.error_message)
                );
            END IF;

        WHEN 'pending_approval' THEN
            NULL;

        WHEN 'processing' THEN
            NULL;

        ELSE
            NULL;
    END CASE;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

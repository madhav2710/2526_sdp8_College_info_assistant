-- Unified Supabase schema bootstrap (single project)
-- Purpose:
--   Create a fresh one-project schema that combines:
--   - User/auth-facing data
--   - Admin/workflow data
--   - RAG/vector data
--
-- Safe to run on a new project.
-- Mostly idempotent for re-runs (CREATE IF NOT EXISTS / DROP POLICY IF EXISTS).

-- =========================================================
-- 0) Extensions
-- =========================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================================================
-- 1) Core reference tables
-- =========================================================
CREATE TABLE IF NOT EXISTS public.colleges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE,
    domain TEXT UNIQUE,
    description TEXT,
    logo_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    college_id UUID REFERENCES public.colleges(id) ON DELETE SET NULL,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'student'
        CHECK (role IN ('student', 'college_admin', 'super_admin')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'disabled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Compatibility table for legacy code paths that upsert public.users.
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Compatibility table for legacy code paths that upsert public.admins.
CREATE TABLE IF NOT EXISTS public.admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    college_id UUID REFERENCES public.colleges(id) ON DELETE SET NULL,
    is_super_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT admins_user_college_unique UNIQUE (user_id, college_id)
);

-- =========================================================
-- 2) RAG + document workflow tables
-- =========================================================
CREATE TABLE IF NOT EXISTS public.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    college_id UUID NOT NULL REFERENCES public.colleges(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL UNIQUE,
    file_type TEXT,
    file_size BIGINT,
    uploaded_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    approved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'pending_approval', 'approved', 'rejected', 'processing', 'completed', 'failed')),
    file_hash TEXT,
    process_schedule TEXT NOT NULL DEFAULT 'immediate'
        CHECK (process_schedule IN ('immediate', 'scheduled', 'manual')),
    scheduled_at TIMESTAMPTZ,
    approval_comments TEXT,
    error_message TEXT,
    validated_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    processing_started_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    upload_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    processing_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    processing_stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    college_id UUID NOT NULL REFERENCES public.colleges(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT check_embedding_dimension CHECK (embedding IS NULL OR vector_dims(embedding) = 768)
);

CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    college_id UUID NOT NULL REFERENCES public.colleges(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.notifications (
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
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.document_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    approved_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('approved', 'rejected')),
    comments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.document_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT,
    changed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    comments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 3) Normalize foreign keys (important when tables pre-exist)
-- =========================================================
-- Note: This section uses canonical constraint names and re-adds them.
-- On a non-empty DB with inconsistent data, ADD CONSTRAINT may fail.

ALTER TABLE public.profiles
    DROP CONSTRAINT IF EXISTS profiles_id_fkey,
    DROP CONSTRAINT IF EXISTS profiles_college_id_fkey;
ALTER TABLE public.profiles
    ADD CONSTRAINT profiles_id_fkey
        FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE,
    ADD CONSTRAINT profiles_college_id_fkey
        FOREIGN KEY (college_id) REFERENCES public.colleges(id) ON DELETE SET NULL;

ALTER TABLE public.users
    DROP CONSTRAINT IF EXISTS users_id_fkey;
ALTER TABLE public.users
    ADD CONSTRAINT users_id_fkey
        FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.admins
    DROP CONSTRAINT IF EXISTS admins_user_id_fkey,
    DROP CONSTRAINT IF EXISTS admins_college_id_fkey;
ALTER TABLE public.admins
    ADD CONSTRAINT admins_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
    ADD CONSTRAINT admins_college_id_fkey
        FOREIGN KEY (college_id) REFERENCES public.colleges(id) ON DELETE SET NULL;

ALTER TABLE public.documents
    DROP CONSTRAINT IF EXISTS documents_college_id_fkey,
    DROP CONSTRAINT IF EXISTS documents_uploaded_by_fkey,
    DROP CONSTRAINT IF EXISTS documents_approved_by_fkey;
ALTER TABLE public.documents
    ADD CONSTRAINT documents_college_id_fkey
        FOREIGN KEY (college_id) REFERENCES public.colleges(id) ON DELETE CASCADE,
    ADD CONSTRAINT documents_uploaded_by_fkey
        FOREIGN KEY (uploaded_by) REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD CONSTRAINT documents_approved_by_fkey
        FOREIGN KEY (approved_by) REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE public.document_chunks
    DROP CONSTRAINT IF EXISTS document_chunks_document_id_fkey,
    DROP CONSTRAINT IF EXISTS document_chunks_college_id_fkey;
ALTER TABLE public.document_chunks
    ADD CONSTRAINT document_chunks_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE,
    ADD CONSTRAINT document_chunks_college_id_fkey
        FOREIGN KEY (college_id) REFERENCES public.colleges(id) ON DELETE CASCADE;

ALTER TABLE public.conversations
    DROP CONSTRAINT IF EXISTS conversations_user_id_fkey,
    DROP CONSTRAINT IF EXISTS conversations_college_id_fkey;
ALTER TABLE public.conversations
    ADD CONSTRAINT conversations_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    ADD CONSTRAINT conversations_college_id_fkey
        FOREIGN KEY (college_id) REFERENCES public.colleges(id) ON DELETE CASCADE;

ALTER TABLE public.messages
    DROP CONSTRAINT IF EXISTS messages_conversation_id_fkey;
ALTER TABLE public.messages
    ADD CONSTRAINT messages_conversation_id_fkey
        FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;

ALTER TABLE public.notifications
    DROP CONSTRAINT IF EXISTS notifications_recipient_id_fkey;
ALTER TABLE public.notifications
    ADD CONSTRAINT notifications_recipient_id_fkey
        FOREIGN KEY (recipient_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.document_approvals
    DROP CONSTRAINT IF EXISTS document_approvals_document_id_fkey,
    DROP CONSTRAINT IF EXISTS document_approvals_approved_by_fkey;
ALTER TABLE public.document_approvals
    ADD CONSTRAINT document_approvals_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE,
    ADD CONSTRAINT document_approvals_approved_by_fkey
        FOREIGN KEY (approved_by) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.document_status_history
    DROP CONSTRAINT IF EXISTS document_status_history_document_id_fkey,
    DROP CONSTRAINT IF EXISTS document_status_history_changed_by_fkey;
ALTER TABLE public.document_status_history
    ADD CONSTRAINT document_status_history_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE,
    ADD CONSTRAINT document_status_history_changed_by_fkey
        FOREIGN KEY (changed_by) REFERENCES auth.users(id) ON DELETE SET NULL;

-- =========================================================
-- 4) Indexes
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_profiles_college_role
    ON public.profiles(college_id, role);

CREATE INDEX IF NOT EXISTS idx_profiles_status
    ON public.profiles(status);

CREATE INDEX IF NOT EXISTS idx_documents_status
    ON public.documents(status);

CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by
    ON public.documents(uploaded_by);

CREATE INDEX IF NOT EXISTS idx_documents_approved_by
    ON public.documents(approved_by);

CREATE INDEX IF NOT EXISTS idx_documents_college_status
    ON public.documents(college_id, status);

CREATE INDEX IF NOT EXISTS idx_documents_created_at
    ON public.documents(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_documents_updated_at
    ON public.documents(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_documents_processed_at
    ON public.documents(processed_at DESC) WHERE processed_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_documents_file_hash
    ON public.documents(college_id, file_hash);

CREATE INDEX IF NOT EXISTS idx_documents_scheduled
    ON public.documents(scheduled_at)
    WHERE process_schedule = 'scheduled' AND status = 'approved';

CREATE INDEX IF NOT EXISTS idx_document_chunks_college_id
    ON public.document_chunks(college_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_college
    ON public.document_chunks(document_id, college_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_college_embedding
    ON public.document_chunks(college_id)
    WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
    ON public.document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_chunks_doc_chunk_unique
    ON public.document_chunks(document_id, chunk_index)
    WHERE chunk_index IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_conversations_user_college
    ON public.conversations(user_id, college_id);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
    ON public.messages(conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_messages_sources_gin
    ON public.messages USING gin (sources);

CREATE INDEX IF NOT EXISTS idx_messages_metadata_gin
    ON public.messages USING gin (metadata);

CREATE INDEX IF NOT EXISTS idx_notifications_recipient_id
    ON public.notifications(recipient_id);

CREATE INDEX IF NOT EXISTS idx_notifications_created_at
    ON public.notifications(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_unread
    ON public.notifications(recipient_id, is_read) WHERE is_read = FALSE;

CREATE INDEX IF NOT EXISTS idx_notifications_type
    ON public.notifications(type);

CREATE INDEX IF NOT EXISTS idx_document_approvals_document_id
    ON public.document_approvals(document_id);

CREATE INDEX IF NOT EXISTS idx_document_approvals_approved_by
    ON public.document_approvals(approved_by);

CREATE INDEX IF NOT EXISTS idx_document_approvals_created_at
    ON public.document_approvals(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_status_history_document
    ON public.document_status_history(document_id, created_at DESC);

-- =========================================================
-- 5) Utility triggers/functions
-- =========================================================
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_colleges_updated_at ON public.colleges;
CREATE TRIGGER trigger_colleges_updated_at
    BEFORE UPDATE ON public.colleges
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_profiles_updated_at ON public.profiles;
CREATE TRIGGER trigger_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_users_updated_at ON public.users;
CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_admins_updated_at ON public.admins;
CREATE TRIGGER trigger_admins_updated_at
    BEFORE UPDATE ON public.admins
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_documents_updated_at ON public.documents;
CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON public.documents
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_conversations_updated_at ON public.conversations;
CREATE TRIGGER trigger_conversations_updated_at
    BEFORE UPDATE ON public.conversations
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

CREATE OR REPLACE FUNCTION public.sync_chunk_index_from_metadata()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.chunk_index IS NULL AND NEW.metadata ? 'chunk_index' THEN
        NEW.chunk_index := NULLIF(NEW.metadata->>'chunk_index', '')::INTEGER;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_document_chunks_sync_chunk_index ON public.document_chunks;
CREATE TRIGGER trigger_document_chunks_sync_chunk_index
    BEFORE INSERT OR UPDATE ON public.document_chunks
    FOR EACH ROW
    EXECUTE FUNCTION public.sync_chunk_index_from_metadata();

-- =========================================================
-- 6) Notification helper functions
-- =========================================================
CREATE OR REPLACE FUNCTION public.create_notification(
    p_recipient_id UUID,
    p_type TEXT,
    p_title TEXT,
    p_content TEXT,
    p_metadata JSONB DEFAULT '{}'::jsonb
) RETURNS UUID AS $$
DECLARE
    notification_id UUID;
BEGIN
    INSERT INTO public.notifications (recipient_id, type, title, content, metadata)
    VALUES (p_recipient_id, p_type, p_title, p_content, p_metadata)
    RETURNING id INTO notification_id;

    RETURN notification_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.get_unread_notification_count(p_user_id UUID)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)::INTEGER
        FROM public.notifications
        WHERE recipient_id = p_user_id
          AND is_read = FALSE
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.mark_notification_read(p_notification_id UUID, p_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE public.notifications
       SET is_read = TRUE,
           read_at = now()
     WHERE id = p_notification_id
       AND recipient_id = p_user_id
       AND is_read = FALSE;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- =========================================================
-- 7) Document workflow triggers/functions
-- =========================================================
CREATE OR REPLACE FUNCTION public.log_document_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO public.document_status_history (
            document_id,
            old_status,
            new_status,
            changed_by,
            comments
        ) VALUES (
            NEW.id,
            OLD.status,
            NEW.status,
            NEW.approved_by,
            NEW.approval_comments
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_document_status_history ON public.documents;
CREATE TRIGGER trigger_document_status_history
    AFTER UPDATE OF status ON public.documents
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION public.log_document_status_change();

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

DROP TRIGGER IF EXISTS trigger_document_status_notification ON public.documents;
CREATE TRIGGER trigger_document_status_notification
    AFTER UPDATE OF status ON public.documents
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION public.notify_document_status_change();

-- =========================================================
-- 8) RAG vector RPC functions
-- =========================================================
CREATE OR REPLACE FUNCTION public.match_documents(
    query_embedding VECTOR(768),
    target_college_id UUID,
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    college_id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        dc.id,
        dc.document_id,
        dc.college_id,
        dc.content,
        dc.metadata,
        (1 - (dc.embedding <=> query_embedding)) AS similarity
    FROM public.document_chunks dc
    JOIN public.documents d ON d.id = dc.document_id
    WHERE dc.college_id = target_college_id
      AND d.status = 'completed'
      AND dc.embedding IS NOT NULL
      AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION public.check_vector_storage_integrity(target_college_id UUID)
RETURNS TABLE (
    issue_type TEXT,
    issue_count BIGINT,
    description TEXT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        'missing_embeddings' AS issue_type,
        COUNT(*) AS issue_count,
        'Document chunks without embeddings' AS description
    FROM public.document_chunks
    WHERE college_id = target_college_id
      AND embedding IS NULL

    UNION ALL

    SELECT
        'orphaned_chunks' AS issue_type,
        COUNT(*) AS issue_count,
        'Document chunks without valid parent documents' AS description
    FROM public.document_chunks dc
    LEFT JOIN public.documents d ON d.id = dc.document_id
    WHERE dc.college_id = target_college_id
      AND d.id IS NULL

    UNION ALL

    SELECT
        'incomplete_document_chunks' AS issue_type,
        COUNT(*) AS issue_count,
        'Document chunks from non-completed documents' AS description
    FROM public.document_chunks dc
    JOIN public.documents d ON d.id = dc.document_id
    WHERE dc.college_id = target_college_id
      AND d.status <> 'completed';
$$;

CREATE OR REPLACE FUNCTION public.get_vector_storage_stats(target_college_id UUID)
RETURNS TABLE (
    total_chunks BIGINT,
    chunks_with_embeddings BIGINT,
    total_documents BIGINT,
    completed_documents BIGINT,
    avg_chunks_per_document NUMERIC
)
LANGUAGE sql STABLE
AS $$
    SELECT
        COUNT(dc.*) AS total_chunks,
        COUNT(dc.embedding) AS chunks_with_embeddings,
        COUNT(DISTINCT dc.document_id) AS total_documents,
        COUNT(DISTINCT CASE WHEN d.status = 'completed' THEN dc.document_id END) AS completed_documents,
        ROUND(COUNT(dc.*)::NUMERIC / NULLIF(COUNT(DISTINCT dc.document_id), 0), 2) AS avg_chunks_per_document
    FROM public.document_chunks dc
    LEFT JOIN public.documents d ON d.id = dc.document_id
    WHERE dc.college_id = target_college_id;
$$;

CREATE OR REPLACE FUNCTION public.get_optimal_similarity_threshold(
    target_college_id UUID,
    sample_size INT DEFAULT 100
)
RETURNS FLOAT
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    avg_similarity FLOAT;
    std_similarity FLOAT;
    optimal_threshold FLOAT;
BEGIN
    SELECT
        AVG(1 - (c1.embedding <=> c2.embedding)),
        STDDEV(1 - (c1.embedding <=> c2.embedding))
    INTO avg_similarity, std_similarity
    FROM (
        SELECT embedding
        FROM public.document_chunks
        WHERE college_id = target_college_id
          AND embedding IS NOT NULL
        ORDER BY RANDOM()
        LIMIT sample_size
    ) c1
    CROSS JOIN (
        SELECT embedding
        FROM public.document_chunks
        WHERE college_id = target_college_id
          AND embedding IS NOT NULL
        ORDER BY RANDOM()
        LIMIT sample_size
    ) c2
    WHERE c1.embedding <> c2.embedding;

    optimal_threshold := COALESCE(avg_similarity + std_similarity, 0.7);
    optimal_threshold := GREATEST(0.5, LEAST(0.9, optimal_threshold));
    RETURN optimal_threshold;
END;
$$;

-- =========================================================
-- 9) RLS enablement
-- =========================================================
ALTER TABLE public.colleges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_status_history ENABLE ROW LEVEL SECURITY;

-- =========================================================
-- 10) RLS policies
-- =========================================================
-- Colleges
DROP POLICY IF EXISTS "Colleges are viewable by everyone" ON public.colleges;
CREATE POLICY "Colleges are viewable by everyone"
ON public.colleges FOR SELECT
USING (TRUE);

DROP POLICY IF EXISTS "Super admins can manage colleges" ON public.colleges;
CREATE POLICY "Super admins can manage colleges"
ON public.colleges FOR ALL
USING (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
);

-- Profiles
DROP POLICY IF EXISTS "Users can insert their own profile" ON public.profiles;
CREATE POLICY "Users can insert their own profile"
ON public.profiles FOR INSERT
WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "Users can view their own profile" ON public.profiles;
CREATE POLICY "Users can view their own profile"
ON public.profiles FOR SELECT
USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile"
ON public.profiles FOR UPDATE
USING (auth.uid() = id)
WITH CHECK (auth.uid() = id);

-- Legacy users/admins compatibility
DROP POLICY IF EXISTS "Users can view own users row" ON public.users;
CREATE POLICY "Users can view own users row"
ON public.users FOR SELECT
USING (auth.uid() = id);

DROP POLICY IF EXISTS "Super admins manage users table" ON public.users;
CREATE POLICY "Super admins manage users table"
ON public.users FOR ALL
USING (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
);

DROP POLICY IF EXISTS "Super admins manage admins table" ON public.admins;
CREATE POLICY "Super admins manage admins table"
ON public.admins FOR ALL
USING (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
);

-- Documents
DROP POLICY IF EXISTS "College members can view documents" ON public.documents;
CREATE POLICY "College members can view documents"
ON public.documents FOR SELECT
USING (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR p.college_id = documents.college_id
          )
    )
);

DROP POLICY IF EXISTS "College admins can insert documents" ON public.documents;
CREATE POLICY "College admins can insert documents"
ON public.documents FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR (p.role = 'college_admin' AND p.college_id = documents.college_id)
          )
    )
);

DROP POLICY IF EXISTS "College admins can update documents" ON public.documents;
CREATE POLICY "College admins can update documents"
ON public.documents FOR UPDATE
USING (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR (p.role = 'college_admin' AND p.college_id = documents.college_id)
          )
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR (p.role = 'college_admin' AND p.college_id = documents.college_id)
          )
    )
);

-- Document chunks
DROP POLICY IF EXISTS "College members can view chunks" ON public.document_chunks;
CREATE POLICY "College members can view chunks"
ON public.document_chunks FOR SELECT
USING (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR p.college_id = document_chunks.college_id
          )
    )
);

-- Conversations
DROP POLICY IF EXISTS "Users can manage own conversations" ON public.conversations;
CREATE POLICY "Users can manage own conversations"
ON public.conversations FOR ALL
USING (
    user_id = auth.uid()
    OR EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
)
WITH CHECK (
    user_id = auth.uid()
    OR EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
);

-- Messages
DROP POLICY IF EXISTS "Users can manage messages in own conversations" ON public.messages;
CREATE POLICY "Users can manage messages in own conversations"
ON public.messages FOR ALL
USING (
    EXISTS (
        SELECT 1
        FROM public.conversations c
        WHERE c.id = messages.conversation_id
          AND c.user_id = auth.uid()
    )
    OR EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.conversations c
        WHERE c.id = messages.conversation_id
          AND c.user_id = auth.uid()
    )
    OR EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
);

-- Notifications
DROP POLICY IF EXISTS "Users can view their own notifications" ON public.notifications;
CREATE POLICY "Users can view their own notifications"
ON public.notifications FOR SELECT
USING (auth.uid() = recipient_id);

DROP POLICY IF EXISTS "Users can update their own notifications" ON public.notifications;
CREATE POLICY "Users can update their own notifications"
ON public.notifications FOR UPDATE
USING (auth.uid() = recipient_id);

DROP POLICY IF EXISTS "Users can delete their own notifications" ON public.notifications;
CREATE POLICY "Users can delete their own notifications"
ON public.notifications FOR DELETE
USING (auth.uid() = recipient_id);

DROP POLICY IF EXISTS "System can create notifications" ON public.notifications;
CREATE POLICY "System can create notifications"
ON public.notifications FOR INSERT
WITH CHECK (TRUE);

-- Document approvals
DROP POLICY IF EXISTS "Super admins can manage document approvals" ON public.document_approvals;
CREATE POLICY "Super admins can manage document approvals"
ON public.document_approvals FOR ALL
USING (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
);

DROP POLICY IF EXISTS "College admins can view their college document approvals" ON public.document_approvals;
CREATE POLICY "College admins can view their college document approvals"
ON public.document_approvals FOR SELECT
USING (
    EXISTS (
        SELECT 1
        FROM public.documents d
        JOIN public.profiles p ON p.id = auth.uid()
        WHERE d.id = document_approvals.document_id
          AND d.college_id = p.college_id
          AND p.role = 'college_admin'
    )
);

-- Status history
DROP POLICY IF EXISTS "Super admins can view all status history" ON public.document_status_history;
CREATE POLICY "Super admins can view all status history"
ON public.document_status_history FOR SELECT
USING (
    EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND p.role = 'super_admin'
    )
);

DROP POLICY IF EXISTS "College admins can view their college status history" ON public.document_status_history;
CREATE POLICY "College admins can view their college status history"
ON public.document_status_history FOR SELECT
USING (
    EXISTS (
        SELECT 1
        FROM public.documents d
        JOIN public.profiles p ON p.id = auth.uid()
        WHERE d.id = document_status_history.document_id
          AND d.college_id = p.college_id
          AND p.role = 'college_admin'
    )
);

-- =========================================================
-- 11) Storage bucket + storage policies
-- =========================================================
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'documents',
    'documents',
    FALSE,
    52428800,
    ARRAY[
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain'
    ]::TEXT[]
)
ON CONFLICT (id) DO UPDATE
SET public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

DROP POLICY IF EXISTS "College members can read own college documents objects" ON storage.objects;
CREATE POLICY "College members can read own college documents objects"
ON storage.objects FOR SELECT
USING (
    bucket_id = 'documents'
    AND EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR p.college_id::TEXT = split_part(name, '/', 1)
          )
    )
);

DROP POLICY IF EXISTS "College admins can upload own college documents objects" ON storage.objects;
CREATE POLICY "College admins can upload own college documents objects"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = 'documents'
    AND EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR (p.role = 'college_admin' AND p.college_id::TEXT = split_part(name, '/', 1))
          )
    )
);

DROP POLICY IF EXISTS "College admins can update own college documents objects" ON storage.objects;
CREATE POLICY "College admins can update own college documents objects"
ON storage.objects FOR UPDATE
USING (
    bucket_id = 'documents'
    AND EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR (p.role = 'college_admin' AND p.college_id::TEXT = split_part(name, '/', 1))
          )
    )
)
WITH CHECK (
    bucket_id = 'documents'
    AND EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR (p.role = 'college_admin' AND p.college_id::TEXT = split_part(name, '/', 1))
          )
    )
);

DROP POLICY IF EXISTS "College admins can delete own college documents objects" ON storage.objects;
CREATE POLICY "College admins can delete own college documents objects"
ON storage.objects FOR DELETE
USING (
    bucket_id = 'documents'
    AND EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = auth.uid()
          AND (
              p.role = 'super_admin'
              OR (p.role = 'college_admin' AND p.college_id::TEXT = split_part(name, '/', 1))
          )
    )
);

-- =========================================================
-- 12) Grants for RPC usage
-- =========================================================
GRANT EXECUTE ON FUNCTION public.create_notification(UUID, TEXT, TEXT, TEXT, JSONB) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_unread_notification_count(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.mark_notification_read(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_documents(VECTOR, UUID, FLOAT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.check_vector_storage_integrity(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_vector_storage_stats(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_optimal_similarity_threshold(UUID, INT) TO authenticated;

-- =========================================================
-- 13) Post-create analyze
-- =========================================================
ANALYZE public.documents;
ANALYZE public.document_chunks;
ANALYZE public.messages;

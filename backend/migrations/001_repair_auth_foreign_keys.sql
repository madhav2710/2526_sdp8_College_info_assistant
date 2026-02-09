-- Repair script: enforce all public -> auth.users foreign keys
-- Use this after running 000_unified_single_project_schema.sql
-- when check #2 is missing auth-linked FKs.

BEGIN;

-- 1) Safety gate: stop if any orphan auth references exist.
DO $$
DECLARE
    orphan_count BIGINT;
BEGIN
    SELECT COALESCE(SUM(c), 0)
    INTO orphan_count
    FROM (
        SELECT COUNT(*) AS c
        FROM public.profiles p
        LEFT JOIN auth.users u ON u.id = p.id
        WHERE u.id IS NULL

        UNION ALL

        SELECT COUNT(*) AS c
        FROM public.users pu
        LEFT JOIN auth.users u ON u.id = pu.id
        WHERE u.id IS NULL

        UNION ALL

        SELECT COUNT(*) AS c
        FROM public.documents d
        LEFT JOIN auth.users u ON u.id = d.uploaded_by
        WHERE d.uploaded_by IS NOT NULL
          AND u.id IS NULL

        UNION ALL

        SELECT COUNT(*) AS c
        FROM public.documents d
        LEFT JOIN auth.users u ON u.id = d.approved_by
        WHERE d.approved_by IS NOT NULL
          AND u.id IS NULL

        UNION ALL

        SELECT COUNT(*) AS c
        FROM public.conversations c
        LEFT JOIN auth.users u ON u.id = c.user_id
        WHERE u.id IS NULL

        UNION ALL

        SELECT COUNT(*) AS c
        FROM public.notifications n
        LEFT JOIN auth.users u ON u.id = n.recipient_id
        WHERE u.id IS NULL

        UNION ALL

        SELECT COUNT(*) AS c
        FROM public.document_approvals da
        LEFT JOIN auth.users u ON u.id = da.approved_by
        WHERE u.id IS NULL

        UNION ALL

        SELECT COUNT(*) AS c
        FROM public.document_status_history dsh
        LEFT JOIN auth.users u ON u.id = dsh.changed_by
        WHERE dsh.changed_by IS NOT NULL
          AND u.id IS NULL
    ) orphan_refs;

    IF orphan_count > 0 THEN
        RAISE EXCEPTION 'Aborting FK repair: found % orphan auth references.', orphan_count;
    END IF;
END;
$$;

-- 2) Drop any existing FK constraints on target auth-link columns
-- regardless of their current constraint names.
DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN
        SELECT DISTINCT
            n.nspname AS schema_name,
            c.relname AS table_name,
            con.conname AS constraint_name
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN unnest(con.conkey) AS k(attnum) ON TRUE
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
        WHERE con.contype = 'f'
          AND n.nspname = 'public'
          AND (
              (c.relname = 'profiles' AND a.attname = 'id')
              OR (c.relname = 'users' AND a.attname = 'id')
              OR (c.relname = 'documents' AND a.attname IN ('uploaded_by', 'approved_by'))
              OR (c.relname = 'conversations' AND a.attname = 'user_id')
              OR (c.relname = 'notifications' AND a.attname = 'recipient_id')
              OR (c.relname = 'document_approvals' AND a.attname = 'approved_by')
              OR (c.relname = 'document_status_history' AND a.attname = 'changed_by')
          )
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I DROP CONSTRAINT %I',
            rec.schema_name,
            rec.table_name,
            rec.constraint_name
        );
    END LOOP;
END;
$$;

-- 3) Recreate canonical FK constraints to auth.users.
ALTER TABLE public.profiles
    ADD CONSTRAINT profiles_id_fkey
        FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.users
    ADD CONSTRAINT users_id_fkey
        FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.documents
    ADD CONSTRAINT documents_uploaded_by_fkey
        FOREIGN KEY (uploaded_by) REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD CONSTRAINT documents_approved_by_fkey
        FOREIGN KEY (approved_by) REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE public.conversations
    ADD CONSTRAINT conversations_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.notifications
    ADD CONSTRAINT notifications_recipient_id_fkey
        FOREIGN KEY (recipient_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.document_approvals
    ADD CONSTRAINT document_approvals_approved_by_fkey
        FOREIGN KEY (approved_by) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.document_status_history
    ADD CONSTRAINT document_status_history_changed_by_fkey
        FOREIGN KEY (changed_by) REFERENCES auth.users(id) ON DELETE SET NULL;

COMMIT;

-- 4) Quick verification (same check as #2b)
SELECT
    t.relname AS table_name,
    a.attname AS column_name,
    n2.nspname AS foreign_table_schema,
    t2.relname AS foreign_table_name
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
JOIN pg_class t2 ON t2.oid = c.confrelid
JOIN pg_namespace n2 ON n2.oid = t2.relnamespace
JOIN unnest(c.conkey) WITH ORDINALITY AS ck(attnum, ord) ON TRUE
JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ck.attnum
WHERE c.contype = 'f'
  AND n.nspname = 'public'
  AND n2.nspname = 'auth'
  AND t.relname IN (
    'profiles',
    'users',
    'documents',
    'conversations',
    'notifications',
    'document_approvals',
    'document_status_history'
  )
ORDER BY t.relname, a.attname;

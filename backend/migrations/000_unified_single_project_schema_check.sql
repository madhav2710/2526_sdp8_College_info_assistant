-- Unified single-project schema validation checklist
-- Run after executing: 000_unified_single_project_schema.sql

-- 1) Required tables
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'colleges',
    'profiles',
    'users',
    'admins',
    'documents',
    'document_chunks',
    'conversations',
    'messages',
    'notifications',
    'document_approvals',
    'document_status_history'
  )
ORDER BY tablename;

-- 2) Key foreign keys and relationships
SELECT
  tc.table_name,
  kcu.column_name,
  ccu.table_schema AS foreign_table_schema,
  ccu.table_name AS foreign_table_name,
  ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
  AND ccu.constraint_schema = tc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
  AND tc.table_name IN (
    'profiles',
    'admins',
    'documents',
    'document_chunks',
    'conversations',
    'messages',
    'notifications',
    'document_approvals',
    'document_status_history'
  )
ORDER BY tc.table_name, kcu.column_name;

-- 2b) Auth FK sanity (must all be present)
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

-- 3) Key columns used by app code
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
    (table_name = 'colleges' AND column_name IN ('id','name','code','domain','description','logo_url','is_active','created_at','updated_at'))
    OR
    (table_name = 'profiles' AND column_name IN ('id','college_id','full_name','role','status','created_at','updated_at'))
    OR
    (table_name = 'users' AND column_name IN ('id','email','created_at','updated_at'))
    OR
    (table_name = 'admins' AND column_name IN ('id','user_id','college_id','is_super_admin','created_at','updated_at'))
    OR
    (table_name = 'documents' AND column_name IN (
      'id','college_id','filename','storage_path','file_type','file_size','uploaded_by',
      'approved_by','status','file_hash','process_schedule','scheduled_at','approval_comments',
      'error_message','validated_at','processed_at','processing_started_at','failed_at',
      'upload_metadata','processing_metadata','processing_stats','created_at','updated_at'
    ))
    OR
    (table_name = 'document_chunks' AND column_name IN ('id','document_id','college_id','chunk_index','content','embedding','metadata','created_at'))
    OR
    (table_name = 'conversations' AND column_name IN ('id','user_id','college_id','title','created_at','updated_at'))
    OR
    (table_name = 'messages' AND column_name IN ('id','conversation_id','role','content','sources','metadata','created_at'))
    OR
    (table_name = 'notifications' AND column_name IN ('id','recipient_id','type','title','content','metadata','is_read','created_at','read_at'))
    OR
    (table_name = 'document_approvals' AND column_name IN ('id','document_id','approved_by','action','comments','created_at'))
    OR
    (table_name = 'document_status_history' AND column_name IN ('id','document_id','old_status','new_status','changed_by','comments','created_at'))
  )
ORDER BY table_name, column_name;

-- 4) pgvector extension
SELECT extname
FROM pg_extension
WHERE extname = 'vector';

-- 5) RPC functions used by RAG/backend
SELECT proname AS function_name
FROM pg_proc
JOIN pg_namespace n ON n.oid = pg_proc.pronamespace
WHERE n.nspname = 'public'
  AND proname IN (
    'match_documents',
    'check_vector_storage_integrity',
    'get_vector_storage_stats',
    'get_optimal_similarity_threshold',
    'create_notification',
    'get_unread_notification_count',
    'mark_notification_read',
    'log_document_status_change',
    'notify_document_status_change',
    'update_updated_at_column'
  )
ORDER BY proname;

-- 6) Trigger checks
SELECT DISTINCT event_object_table AS table_name, trigger_name
FROM information_schema.triggers
WHERE trigger_schema = 'public'
  AND event_object_table IN (
    'colleges',
    'profiles',
    'users',
    'admins',
    'documents',
    'conversations',
    'document_chunks'
  )
ORDER BY event_object_table, trigger_name;

-- 7) Critical index checks
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'idx_documents_college_status',
    'idx_documents_scheduled',
    'idx_document_chunks_embedding_hnsw',
    'idx_document_chunks_college_embedding',
    'idx_document_chunks_document_college',
    'idx_messages_sources_gin',
    'idx_messages_metadata_gin',
    'idx_notifications_unread',
    'idx_status_history_document'
  )
ORDER BY indexname;

-- 8) Storage bucket check
SELECT id, name, public, file_size_limit
FROM storage.buckets
WHERE id = 'documents';

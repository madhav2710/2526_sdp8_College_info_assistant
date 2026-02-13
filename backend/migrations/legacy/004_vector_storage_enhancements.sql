-- Vector Storage Enhancements Migration
-- This migration adds:
-- - Native pgvector similarity search function (match_documents)
-- - Performance indexes for vector operations
-- - Vector storage integrity constraints

-- ============================================================================
-- 1. CREATE NATIVE PGVECTOR SIMILARITY SEARCH FUNCTION
-- ============================================================================

-- Create the match_documents function for efficient vector similarity search
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(768),
    target_college_id uuid,
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id uuid,
    document_id uuid,
    college_id uuid,
    content text,
    metadata jsonb,
    similarity float
) 
LANGUAGE sql STABLE
AS $$
    SELECT 
        dc.id,
        dc.document_id,
        dc.college_id,
        dc.content,
        dc.metadata,
        (1 - (dc.embedding <=> query_embedding)) as similarity
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE dc.college_id = target_college_id
        AND d.status = 'completed'
        AND dc.embedding IS NOT NULL
        AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION match_documents(vector(768), uuid, float, int) TO authenticated;

-- ============================================================================
-- 2. CREATE PERFORMANCE INDEXES FOR VECTOR OPERATIONS
-- ============================================================================

-- Create HNSW index for fast vector similarity search
-- This significantly improves performance for large datasets
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Create additional indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_document_chunks_college_embedding 
ON document_chunks(college_id) 
WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_college 
ON document_chunks(document_id, college_id);

-- ============================================================================
-- 3. ADD VECTOR STORAGE INTEGRITY CONSTRAINTS
-- ============================================================================

-- Add constraint to ensure embeddings have correct dimensions
-- Note: This is informational - pgvector already enforces dimension constraints
-- But we add a check constraint for additional validation
ALTER TABLE document_chunks 
ADD CONSTRAINT check_embedding_dimension 
CHECK (embedding IS NULL OR vector_dims(embedding) = 768);

-- ============================================================================
-- 4. CREATE HELPER FUNCTIONS FOR VECTOR STORAGE MANAGEMENT
-- ============================================================================

-- Function to check vector storage integrity for a college
CREATE OR REPLACE FUNCTION check_vector_storage_integrity(target_college_id uuid)
RETURNS TABLE (
    issue_type text,
    issue_count bigint,
    description text
)
LANGUAGE sql STABLE
AS $$
    -- Check for chunks without embeddings
    SELECT 
        'missing_embeddings' as issue_type,
        COUNT(*) as issue_count,
        'Document chunks without embeddings' as description
    FROM document_chunks 
    WHERE college_id = target_college_id AND embedding IS NULL
    
    UNION ALL
    
    -- Check for orphaned chunks (chunks without valid documents)
    SELECT 
        'orphaned_chunks' as issue_type,
        COUNT(*) as issue_count,
        'Document chunks without valid parent documents' as description
    FROM document_chunks dc
    LEFT JOIN documents d ON dc.document_id = d.id
    WHERE dc.college_id = target_college_id AND d.id IS NULL
    
    UNION ALL
    
    -- Check for chunks from non-completed documents
    SELECT 
        'incomplete_document_chunks' as issue_type,
        COUNT(*) as issue_count,
        'Document chunks from non-completed documents' as description
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE dc.college_id = target_college_id AND d.status != 'completed';
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION check_vector_storage_integrity(uuid) TO authenticated;

-- Function to get vector storage statistics for a college
CREATE OR REPLACE FUNCTION get_vector_storage_stats(target_college_id uuid)
RETURNS TABLE (
    total_chunks bigint,
    chunks_with_embeddings bigint,
    total_documents bigint,
    completed_documents bigint,
    avg_chunks_per_document numeric
)
LANGUAGE sql STABLE
AS $$
    SELECT 
        COUNT(dc.*) as total_chunks,
        COUNT(dc.embedding) as chunks_with_embeddings,
        COUNT(DISTINCT dc.document_id) as total_documents,
        COUNT(DISTINCT CASE WHEN d.status = 'completed' THEN dc.document_id END) as completed_documents,
        ROUND(COUNT(dc.*)::numeric / NULLIF(COUNT(DISTINCT dc.document_id), 0), 2) as avg_chunks_per_document
    FROM document_chunks dc
    LEFT JOIN documents d ON dc.document_id = d.id
    WHERE dc.college_id = target_college_id;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_vector_storage_stats(uuid) TO authenticated;

-- ============================================================================
-- 5. CREATE VECTOR SEARCH OPTIMIZATION FUNCTION
-- ============================================================================

-- Function to get optimal similarity threshold based on data distribution
CREATE OR REPLACE FUNCTION get_optimal_similarity_threshold(
    target_college_id uuid,
    sample_size int DEFAULT 100
)
RETURNS float
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    avg_similarity float;
    std_similarity float;
    optimal_threshold float;
BEGIN
    -- Calculate average similarity between random chunk pairs
    SELECT 
        AVG(1 - (c1.embedding <=> c2.embedding)) as avg_sim,
        STDDEV(1 - (c1.embedding <=> c2.embedding)) as std_sim
    INTO avg_similarity, std_similarity
    FROM (
        SELECT embedding 
        FROM document_chunks 
        WHERE college_id = target_college_id 
            AND embedding IS NOT NULL 
        ORDER BY RANDOM() 
        LIMIT sample_size
    ) c1
    CROSS JOIN (
        SELECT embedding 
        FROM document_chunks 
        WHERE college_id = target_college_id 
            AND embedding IS NOT NULL 
        ORDER BY RANDOM() 
        LIMIT sample_size
    ) c2
    WHERE c1.embedding != c2.embedding;
    
    -- Set threshold to be 1 standard deviation above average
    -- This helps filter out noise while keeping relevant results
    optimal_threshold := COALESCE(avg_similarity + std_similarity, 0.7);
    
    -- Ensure threshold is within reasonable bounds
    optimal_threshold := GREATEST(0.5, LEAST(0.9, optimal_threshold));
    
    RETURN optimal_threshold;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_optimal_similarity_threshold(uuid, int) TO authenticated;

-- ============================================================================
-- 6. UPDATE EXISTING DATA AND OPTIMIZE
-- ============================================================================

-- Analyze tables to update statistics for query planner
ANALYZE document_chunks;
ANALYZE documents;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

DO $
BEGIN
    RAISE NOTICE 'Vector Storage Enhancements migration completed successfully';
    RAISE NOTICE 'Added native pgvector similarity search function: match_documents';
    RAISE NOTICE 'Created HNSW index for fast vector similarity search';
    RAISE NOTICE 'Added vector storage integrity constraints and helper functions';
    RAISE NOTICE 'Performance optimizations applied';
END $;
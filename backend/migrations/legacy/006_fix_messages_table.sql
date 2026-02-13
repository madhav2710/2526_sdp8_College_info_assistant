-- Fix messages table schema for enhanced RAG integration
-- This migration ensures both sources and metadata columns exist

-- Add sources column if it doesn't exist (should exist from initial schema but may be missing)
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS sources JSONB;

-- Add metadata column if it doesn't exist
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Add comments to document the purpose of these columns
COMMENT ON COLUMN messages.sources IS 'Source document references from RAG responses';
COMMENT ON COLUMN messages.metadata IS 'Enhanced metadata for RAG responses including processing time, quality scores, and service health information';

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_messages_sources_gin 
ON messages USING gin (sources);

CREATE INDEX IF NOT EXISTS idx_messages_metadata_gin 
ON messages USING gin (metadata);

-- Update any existing messages to have empty JSON objects if null
UPDATE messages 
SET sources = '{}'::jsonb 
WHERE sources IS NULL;

UPDATE messages 
SET metadata = '{}'::jsonb 
WHERE metadata IS NULL;

-- Verify the table structure
DO $
DECLARE
    sources_exists boolean;
    metadata_exists boolean;
BEGIN
    -- Check if sources column exists
    SELECT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'messages' 
        AND column_name = 'sources'
    ) INTO sources_exists;
    
    -- Check if metadata column exists
    SELECT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'messages' 
        AND column_name = 'metadata'
    ) INTO metadata_exists;
    
    -- Report results
    IF sources_exists AND metadata_exists THEN
        RAISE NOTICE 'Messages table migration completed successfully';
        RAISE NOTICE 'Both sources and metadata columns are present';
    ELSE
        RAISE WARNING 'Migration may not have completed successfully';
        IF NOT sources_exists THEN
            RAISE WARNING 'Sources column is missing';
        END IF;
        IF NOT metadata_exists THEN
            RAISE WARNING 'Metadata column is missing';
        END IF;
    END IF;
END $;
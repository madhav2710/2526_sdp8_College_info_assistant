-- Add metadata column to messages table for enhanced RAG integration
-- This migration adds the metadata column that was referenced in the enhanced chat endpoint

-- Add metadata column to messages table
ALTER TABLE messages 
ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Add comment to document the purpose of the metadata column
COMMENT ON COLUMN messages.metadata IS 'Enhanced metadata for RAG responses including processing time, quality scores, and service health information';

-- Create index on metadata for better query performance
CREATE INDEX IF NOT EXISTS idx_messages_metadata_gin 
ON messages USING gin (metadata);

-- Update any existing messages to have empty metadata if null
UPDATE messages 
SET metadata = '{}'::jsonb 
WHERE metadata IS NULL;

-- Migration complete
DO $
BEGIN
    RAISE NOTICE 'Messages metadata column migration completed successfully';
    RAISE NOTICE 'Added metadata JSONB column to messages table';
    RAISE NOTICE 'Created GIN index for metadata queries';
    RAISE NOTICE 'Updated existing messages with empty metadata';
END $;
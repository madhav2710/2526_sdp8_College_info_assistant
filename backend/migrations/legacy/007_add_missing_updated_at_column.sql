-- Add Missing updated_at Column Migration
-- This migration adds the missing updated_at column to the documents table
-- and creates a trigger to automatically update it

-- ============================================================================
-- 1. ADD MISSING UPDATED_AT COLUMN TO DOCUMENTS TABLE
-- ============================================================================

-- Add the updated_at column if it doesn't exist
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Set initial values for existing records
UPDATE documents 
SET updated_at = created_at 
WHERE updated_at IS NULL;

-- ============================================================================
-- 2. CREATE TRIGGER TO AUTOMATICALLY UPDATE updated_at
-- ============================================================================

-- Create a generic function to update the updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$ LANGUAGE plpgsql;

-- Create trigger for documents table
DROP TRIGGER IF EXISTS trigger_documents_updated_at ON documents;
CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 3. ADD UPDATED_AT TO OTHER TABLES THAT MIGHT BE MISSING IT
-- ============================================================================

-- Check and add updated_at to colleges table if missing
DO $
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'colleges' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE colleges ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now();
        UPDATE colleges SET updated_at = created_at WHERE updated_at IS NULL;
        
        DROP TRIGGER IF EXISTS trigger_colleges_updated_at ON colleges;
        CREATE TRIGGER trigger_colleges_updated_at
            BEFORE UPDATE ON colleges
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $;

-- Check and add updated_at to profiles table if missing
DO $
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'profiles' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE profiles ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now();
        UPDATE profiles SET updated_at = created_at WHERE updated_at IS NULL;
        
        DROP TRIGGER IF EXISTS trigger_profiles_updated_at ON profiles;
        CREATE TRIGGER trigger_profiles_updated_at
            BEFORE UPDATE ON profiles
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $;

-- Check and add updated_at to conversations table if missing
DO $
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'conversations' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE conversations ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now();
        UPDATE conversations SET updated_at = created_at WHERE updated_at IS NULL;
        
        DROP TRIGGER IF EXISTS trigger_conversations_updated_at ON conversations;
        CREATE TRIGGER trigger_conversations_updated_at
            BEFORE UPDATE ON conversations
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $;

-- ============================================================================
-- 4. CREATE INDEX FOR PERFORMANCE
-- ============================================================================

-- Add index for updated_at column on documents table
CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents(updated_at DESC);

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

DO $
BEGIN
    RAISE NOTICE 'Missing updated_at column migration completed successfully';
    RAISE NOTICE 'Added updated_at column to documents table';
    RAISE NOTICE 'Created automatic update triggers for updated_at columns';
    RAISE NOTICE 'Added performance index for updated_at column';
END $;
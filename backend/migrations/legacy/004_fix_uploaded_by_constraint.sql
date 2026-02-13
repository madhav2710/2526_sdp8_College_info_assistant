-- Fix uploaded_by Foreign Key Constraint
-- This migration fixes the foreign key constraint issue where authenticated users
-- are not being recognized by the constraint

-- Drop the existing constraint if it exists
ALTER TABLE documents 
DROP CONSTRAINT IF EXISTS documents_uploaded_by_fkey;

-- Recreate the constraint with ON DELETE SET NULL for better handling
-- This allows the constraint to be more lenient while still maintaining referential integrity
ALTER TABLE documents
ADD CONSTRAINT documents_uploaded_by_fkey 
FOREIGN KEY (uploaded_by) REFERENCES auth.users(id) ON DELETE SET NULL;

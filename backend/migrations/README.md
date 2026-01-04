# Database Migrations

This directory contains database migration scripts for the admin platform enhancements.

## Migration Files

### 001_initial_schema.sql
The initial database schema with basic tables for colleges, profiles, documents, document chunks, conversations, and messages.

### 002_admin_platform_enhancements.sql
Adds comprehensive enhancements for the admin platform including:

- **Enhanced Document Workflow**: New status enum with states like `uploaded`, `pending_approval`, `approved`, `rejected`, `processing`, `completed`, `failed`
- **Notifications System**: Real-time notifications for document status changes
- **Document Approvals**: Super admin approval workflow with comments and tracking
- **Performance Indexes**: Optimized database queries with strategic indexes
- **Helper Functions**: Utility functions for common operations
- **Automatic Triggers**: Notification creation on document status changes

## Running Migrations

### Prerequisites
1. Ensure your `.env` file contains database connection details:
   ```
   DATABASE_URL=postgresql://user:password@host:port/database
   # OR individual components:
   DB_HOST=your-host
   DB_PORT=5432
   DB_NAME=your-database
   DB_USER=your-user
   DB_PASSWORD=your-password
   ```

2. Install required Python packages:
   ```bash
   pip install psycopg2-binary
   ```

### Running the Migration

From the `backend` directory:

```bash
# Run the admin platform enhancements migration
python run_migration.py 002_admin_platform_enhancements.sql

# Or run with default (latest migration)
python run_migration.py
```

### Verifying the Migration

After running the migration, verify it was applied correctly:

```bash
python verify_migration.py
```

This will check:
- ✅ New tables (`notifications`, `document_approvals`)
- ✅ New columns in `documents` table
- ✅ Updated document status enum
- ✅ Performance indexes
- ✅ Helper functions
- ✅ Notification triggers

## Migration Details

### New Tables

#### notifications
Stores system notifications for users with support for:
- Different notification types (document_uploaded, document_approved, etc.)
- Read/unread status tracking
- Metadata for additional context
- Automatic cleanup policies

#### document_approvals
Tracks super admin approval actions with:
- Approval/rejection decisions
- Comments and reasoning
- Audit trail with timestamps
- Links to documents and approvers

### Enhanced documents Table

New columns added:
- `file_type`: MIME type of uploaded file
- `file_size`: File size in bytes
- `uploaded_by`: Reference to user who uploaded
- `approved_by`: Reference to super admin who approved
- `approval_comments`: Comments from approval process
- `error_message`: Error details for failed processing
- `processed_at`: Timestamp when processing completed

### Performance Optimizations

Strategic indexes added for:
- Fast notification queries by recipient and read status
- Efficient document filtering by status and college
- Quick approval lookups and audit trails
- Optimized conversation and message queries

### Automatic Notifications

The migration includes triggers that automatically create notifications when:
- Documents are uploaded (notifies super admins)
- Documents are approved/rejected (notifies uploader)
- Processing completes or fails (notifies uploader)

## Rollback

If you need to rollback this migration, you can:

1. Drop the new tables:
   ```sql
   DROP TABLE IF EXISTS document_approvals CASCADE;
   DROP TABLE IF EXISTS notifications CASCADE;
   ```

2. Remove new columns from documents:
   ```sql
   ALTER TABLE documents 
   DROP COLUMN IF EXISTS file_type,
   DROP COLUMN IF EXISTS file_size,
   DROP COLUMN IF EXISTS uploaded_by,
   DROP COLUMN IF EXISTS approved_by,
   DROP COLUMN IF EXISTS approval_comments,
   DROP COLUMN IF EXISTS error_message,
   DROP COLUMN IF EXISTS processed_at;
   ```

3. Restore original status constraint:
   ```sql
   ALTER TABLE documents 
   DROP CONSTRAINT documents_status_check;
   
   ALTER TABLE documents 
   ADD CONSTRAINT documents_status_check 
   CHECK (status IN ('processing', 'completed', 'failed'));
   ```

## Troubleshooting

### Connection Issues
- Verify your `.env` file has correct database credentials
- Check that your database is accessible from your current network
- Ensure the database user has sufficient privileges

### Migration Failures
- Check the error message for specific SQL issues
- Verify that the initial schema (001_initial_schema.sql) was applied first
- Ensure no conflicting table or column names exist

### Verification Failures
- Run the migration again if some components are missing
- Check database logs for any constraint or permission issues
- Verify that all required extensions (like pgvector) are installed

## Security Notes

- The migration includes Row Level Security (RLS) policies
- Notification functions use SECURITY DEFINER for controlled access
- Super admin permissions are properly enforced
- User data is protected with appropriate access controls
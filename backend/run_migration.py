#!/usr/bin/env python3
"""
Database Migration Runner for Admin Platform Enhancements

This script runs the database migration for the admin platform enhancements.
It connects to the Supabase database and executes the migration SQL file.
"""

import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def load_env_vars():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"\'')

def get_db_connection():
    """Get database connection from environment variables"""
    load_env_vars()
    
    # Try different environment variable patterns
    db_url = os.getenv('DATABASE_URL') or os.getenv('SUPABASE_DB_URL')
    
    if not db_url:
        # Try to construct from individual components
        host = os.getenv('DB_HOST') or os.getenv('SUPABASE_DB_HOST')
        port = os.getenv('DB_PORT', '5432')
        database = os.getenv('DB_NAME') or os.getenv('SUPABASE_DB_NAME')
        user = os.getenv('DB_USER') or os.getenv('SUPABASE_DB_USER')
        password = os.getenv('DB_PASSWORD') or os.getenv('SUPABASE_DB_PASSWORD')
        
        if all([host, database, user, password]):
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    if not db_url:
        raise ValueError(
            "Database connection not configured. Please set DATABASE_URL or "
            "individual DB_* environment variables in your .env file."
        )
    
    return psycopg2.connect(db_url)

def run_migration(migration_file: str):
    """Run a specific migration file"""
    migration_path = Path(__file__).parent / 'migrations' / migration_file
    
    if not migration_path.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_path}")
    
    print(f"Running migration: {migration_file}")
    
    # Read migration SQL
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    # Connect to database
    conn = get_db_connection()
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    try:
        with conn.cursor() as cursor:
            # Execute migration
            cursor.execute(migration_sql)
            print(f"Migration {migration_file} completed successfully!")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

def main():
    """Main function"""
    if len(sys.argv) > 1:
        migration_file = sys.argv[1]
    else:
        migration_file = '002_admin_platform_enhancements.sql'
    
    try:
        run_migration(migration_file)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
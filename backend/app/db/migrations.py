"""
Database migration utilities for Voice EMR.
Auto-runs migrations on app startup to ensure schema is in sync.
"""
import logging

logger = logging.getLogger(__name__)


def ensure_tables_exist(connection):
    """
    Run all pending migrations.
    Safe to call multiple times—skips if columns already exist.
    """
    cursor = None
    try:
        cursor = connection.cursor()
        
        # Migration 1: Add corrected_transcript column
        try:
            cursor.execute("""
                ALTER TABLE audio_records
                ADD COLUMN transcript_corrected_encrypted TEXT DEFAULT NULL
                AFTER transcript_encrypted
            """)
            connection.commit()
            logger.info("✅ Migration: added transcript_corrected_encrypted column")
        except Exception as e:
            error_msg = str(e)
            if "Duplicate column" in error_msg or "already exists" in error_msg:
                logger.debug("⏭️ Column transcript_corrected_encrypted already exists")
            else:
                logger.error(f"Migration failed: {error_msg}")
                raise
    
    finally:
        if cursor:
            cursor.close()


def run_startup_migrations():
    """
    Entry point for startup migrations.
    Called by app.main on server startup.
    """
    from app.db.mysql_connection import get_mysql_connection
    
    conn = None
    try:
        logger.info("🔧 Running startup migrations...")
        conn = get_mysql_connection()
        ensure_tables_exist(conn)
        logger.info("✅ All migrations completed successfully")
    except Exception as e:
        logger.error(f"❌ Startup migrations failed: {e}")
        raise
    finally:
        if conn:
            conn.close()

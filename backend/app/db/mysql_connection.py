import mysql.connector
from mysql.connector import pooling
import os
import logging

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Connection pool for efficient mass processing
# ------------------------------------------------------------------

connection_pool = None

def init_connection_pool():
    """Initialize MySQL connection pool (thread-safe)."""
    global connection_pool
    
    if connection_pool is not None:
        return
    
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="voice_emr_pool",
            pool_size=10,  # Adjust based on workload
            pool_reset_session=True,
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DB", "voice_emr"),
            # Robustness settings
            connect_timeout=10,
            autocommit=False,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci',
        )
        logger.info("MySQL connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise

def get_mysql_connection():
    """Get a connection from the pool with timeout settings."""
    global connection_pool
    
    # Initialize pool on first call
    if connection_pool is None:
        init_connection_pool()
    
    try:
        conn = connection_pool.get_connection()
        
        # Set session-level timeouts for robustness
        cursor = conn.cursor()
        cursor.execute("SET SESSION wait_timeout=300")  # 5 minutes
        cursor.execute("SET SESSION interactive_timeout=300")
        cursor.close()
        
        return conn
        
    except mysql.connector.Error as e:
        logger.error(f"Failed to get connection from pool: {e}")
        raise

def close_connection_pool():
    """Close all connections in the pool (for graceful shutdown)."""
    global connection_pool
    
    if connection_pool:
        try:
            # Note: mysql-connector-python doesn't have a direct close_all method
            # Connections will be closed automatically when pool is garbage collected
            connection_pool = None
            logger.info("Connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")

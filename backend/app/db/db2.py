import ibm_db
import os

def get_db2_connection():
    dsn = (
        f"DATABASE={os.getenv('DB2_DB')};"
        f"HOSTNAME={os.getenv('DB2_HOST')};"
        f"PORT={os.getenv('DB2_PORT')};"
        f"PROTOCOL=TCPIP;"
        f"UID={os.getenv('DB2_USER')};"
        f"PWD={os.getenv('DB2_PASSWORD')};"
    )
    return ibm_db.connect(dsn, "", "")

import os
from mcp.server.fastmcp import FastMCP
import sqlite3
from queue import Queue
import threading

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRE_INCIDENTS_DB = "sre_incidents.db"
DB_PATH = os.path.join(CURRENT_DIR, "..", SRE_INCIDENTS_DB)

mcp = FastMCP("RunbookDBManager")

# Connection Pool for SQLite (lightweight pooling)
class ConnectionPool:
    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool = Queue(maxsize=pool_size)
        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.pool.put(conn)
        self.lock = threading.Lock()
    
    def get_connection(self):
        try:
            return self.pool.get(timeout=5)
        except:
            # If pool is exhausted, create a temporary connection
            return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def return_connection(self, conn):
        try:
            self.pool.put(conn, timeout=1)
        except:
            conn.close()
    
    def close_all(self):
        while not self.pool.empty():
            conn = self.pool.get()
            conn.close()

# Initialize connection pool
db_pool = ConnectionPool(DB_PATH)

@mcp.tool()
def save_runbook(incident_id: str, title: str, content: str) -> str:
    """Saves a generated runbook to the runbooks database."""
    conn = db_pool.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO runbooks (incident_id, title, content) VALUES (?, ?, ?)",
            (incident_id, title, content)
        )
        conn.commit()
        return f"Successfully saved runbook for incident {incident_id}."
    except Exception as e:
        return f"Database error: {str(e)}"
    finally:
        db_pool.return_connection(conn)


@mcp.tool()
def list_runbooks() -> str:
    """Returns all runbooks currently in the database."""
    conn = db_pool.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT incident_id FROM runbooks")
        rows = cursor.fetchall()
        return f"Database contains IDs: {', '.join([r[0] for r in rows])}"
    except Exception as e:
        return f"Database error: {str(e)}"
    finally:
        db_pool.return_connection(conn)


@mcp.tool()
def get_runbook_from_id(incident_id: str) ->str:
    """Returns the content of a runbook given its incident_id. Returns error message if incident_id does not exist."""
    conn = db_pool.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM runbooks WHERE incident_id=?", 
            (incident_id,)
        )
        runbook_data_rows = cursor.fetchall()

        if not runbook_data_rows:
            return f"{incident_id} is an invalid incident_id."

        return f"Database contains {', '.join(row[0] for row in runbook_data_rows)} at {incident_id}"
    except Exception as e:
        return f"Database error: {str(e)}"
    finally:
        db_pool.return_connection(conn)


@mcp.tool()
def search_runbooks(query: str, limit: int = 5) -> str:
    """
    Search the runbooks database for documentation matching a specific anomaly or alert.
    Returns a list of titles and remediation steps.
    """
    conn = db_pool.get_connection()
    try:
        cursor = conn.cursor()
        
        # Use parameterized queries to prevent SQL injection
        cursor.execute(
            "SELECT title, content FROM runbooks WHERE content LIKE ? LIMIT ?", 
            (f'%{query}%', limit)
        )
        runbook_data_rows = cursor.fetchall()

        if not runbook_data_rows:
            return "No matching runbooks found."

        return "\n---\n".join([f"Title: {row[0]}\nSteps: {row[1]}" for row in runbook_data_rows])
    except Exception as e:
        return f"Database error: {str(e)}"
    finally:
        db_pool.return_connection(conn)


if __name__ == "__main__":
    mcp.run()

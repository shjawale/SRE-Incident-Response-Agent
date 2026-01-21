import os
from mcp.server.fastmcp import FastMCP
import sqlite3

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRE_INCIDENTS_DB = "sre_incidents.db"
DB_PATH = os.path.join(CURRENT_DIR, "..", SRE_INCIDENTS_DB)

mcp = FastMCP("RunbookDBManager")


@mcp.tool()
def save_runbook(incident_id: str, title: str, content: str) -> str:
    """Saves a generated runbook to the runbooks database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO runbooks (incident_id, title, content) VALUES (?, ?, ?)",
            (incident_id, title, content)
        )
        conn.commit()
        conn.close()
        return f"Successfully saved runbook for incident {incident_id}."
    except Exception as e:
        return f"Database error: {str(e)}"


@mcp.tool()
def list_runbooks() -> str:
    """Returns all runbooks currently in the database."""
    try:
        conn = sqlite3.connect(DB_PATH) # Use absolute path
        cursor = conn.cursor()
        cursor.execute("SELECT incident_id FROM runbooks")
        rows = cursor.fetchall()
        conn.close()
        return f"Database contains IDs: {', '.join([r[0] for r in rows])}"
    except Exception as e:
        return f"Database error: {str(e)}"


@mcp.tool()
def get_runbook_from_id(incident_id: str) ->str:
    """Returns the content of a runbook given its incident_id. Returns error message if incident_id does not exist."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM runbooks WHERE incident_id=?", 
            (incident_id,)
        )
        runbook_data_rows = cursor.fetchall()
        conn.close()

        if not runbook_data_rows:
            return f"{incident_id} is an invalid incident_id."

        return f"Database contains {', '.join(row[0] for row in runbook_data_rows)} at {incident_id}"
    except Exception as e:
        return f"Database error: {str(e)}"


@mcp.tool()
def search_runbooks(query: str, limit: int = 5) -> str:
    """
    Search the runbooks database for documentation matching a specific anomaly or alert.
    Returns a list of titles and remediation steps.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Use parameterized queries to prevent SQL injection
        cursor.execute(
            "SELECT title, content FROM runbooks WHERE content LIKE ? LIMIT ?", 
            (f'%{query}%', limit)
        )
        runbook_data_rows = cursor.fetchall()
        conn.close()

        if not runbook_data_rows:
            return "No matching runbooks found."

        return "\n---\n".join([f"Title: {row[0]}\nSteps: {row[1]}" for row in runbook_data_rows])
    except Exception as e:
        return f"Database error: {str(e)}"


'''
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Create the table if it does not already exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
'''

if __name__ == "__main__":
    #init_db()
    mcp.run()

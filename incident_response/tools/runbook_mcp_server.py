import os
from mcp.server.fastmcp import FastMCP
import sqlite3

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(os.getcwd())

mcp = FastMCP("RunbookDBManager")

@mcp.tool()
def save_runbook(incident_id: str, content: str) -> str:
    """Saves a generated runbook to the sre_incident database."""
    conn = sqlite3.connect(PARENT_DIR + "sre_incident.db")
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO runbooks (incident_id, content) VALUES (?, ?)",
            (incident_id, content)
        )
        conn.commit()
        return f"Successfully saved runbook for incident {incident_id}."
    except Exception as e:
        return f"Database error: {str(e)}"
    finally:
        conn.close()


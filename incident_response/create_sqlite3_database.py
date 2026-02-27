import os
import sqlite3

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRE_INCIDENTS_DB = "sre_incidents.db"
DB_PATH = os.path.join(CURRENT_DIR, SRE_INCIDENTS_DB)

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

def add_data_to_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO runbooks (incident_id, title, content) VALUES ("incident-0", "test-title", "test-content")
    """)
    conn.commit()
    conn.close()

def print_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM runbooks
    """)
    conn.close()

def main():
    init_db()
    add_data_to_db()
    print("test")
    print_db()

if __name__ == "__main__":
    main()

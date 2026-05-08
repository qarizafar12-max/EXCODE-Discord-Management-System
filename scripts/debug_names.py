import sqlite3
import os

DB_PATH = 'bot_database.db'

def dump_tickets():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Dumping 'tickets' table:")
    cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(dict(row))
        
    conn.close()

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        dump_tickets()
    else:
        print(f"Database not found at {DB_PATH}")

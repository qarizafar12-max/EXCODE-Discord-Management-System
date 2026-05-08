import sqlite3
import os

DB_PATH = 'bot_database.db'

def force_migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cols = [
        ("priority", "TEXT DEFAULT 'Normal'"),
        ("assigned_to", "INTEGER DEFAULT NULL"),
        ("owner_name", "TEXT DEFAULT 'Unknown'"),
        ("assigned_name", "TEXT DEFAULT NULL")
    ]
    
    for col_name, col_def in cols:
        try:
            cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_def}")
            print(f"Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column already exists: {col_name}")
            else:
                print(f"Error adding {col_name}: {e}")
                
    conn.commit()
    conn.close()

if __name__ == "__main__":
    force_migrate()

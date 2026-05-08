import sqlite3
import os

DB_PATH = 'bot_database.db'

def check_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Checking 'tickets' table schema:")
    cursor.execute("PRAGMA table_info(tickets)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  Col: {col[1]} ({col[2]})")
        
    conn.close()

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        check_schema()
    else:
        print(f"Database not found at {DB_PATH}")

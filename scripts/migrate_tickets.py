import sqlite3

# Connect to the database
conn = sqlite3.connect('bot_database.db')
cursor = conn.cursor()

# Create the ticket_messages table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS ticket_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        author_id INTEGER NOT NULL,
        author_name TEXT NOT NULL,
        content TEXT,
        is_bot INTEGER DEFAULT 0,
        timestamp TEXT NOT NULL
    )
''')

conn.commit()
conn.close()

print("[OK] Successfully created ticket_messages table!")
print("You can now use the ticket transcript feature.")

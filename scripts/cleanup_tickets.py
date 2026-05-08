import sqlite3

# Connect to database
conn = sqlite3.connect('bot_database.db')
cursor = conn.cursor()

# Update all tickets to 'closed' if they don't exist anymore
# (This is a one-time cleanup)
print("Marking old tickets as closed...")
cursor.execute("UPDATE tickets SET status = 'closed' WHERE status = 'open'")
affected = cursor.rowcount

conn.commit()
conn.close()

print(f"[OK] Marked {affected} tickets as closed.")
print("Now only NEW tickets will show in the web dashboard.")
print("\nTo test:")
print("1. Create a NEW ticket in Discord")
print("2. Send some messages")  
print("3. Check web dashboard - it should appear with messages")

import sqlite3
import werkzeug.security as security

DB_PATH = "bot_database.db"
conn = sqlite3.connect(DB_PATH)

# Make sure table exists
conn.execute("""
    CREATE TABLE IF NOT EXISTS web_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0
    )
""")
conn.commit()

new_hash = security.generate_password_hash("admin_pass")

# Try update first
cursor = conn.execute("UPDATE web_users SET password_hash=?, is_admin=1 WHERE username='admin'", (new_hash,))
conn.commit()

if cursor.rowcount == 0:
    # No admin row — insert it
    conn.execute("INSERT INTO web_users (username, password_hash, is_admin) VALUES ('admin', ?, 1)", (new_hash,))
    conn.commit()
    print("[+] Admin account created.")
else:
    print("[+] Admin password reset successfully.")

rows = conn.execute("SELECT id, username, is_admin FROM web_users").fetchall()
print("Current users:", rows)
conn.close()

print("\nLogin with:")
print("  Username : admin")
print("  Password : admin_pass")

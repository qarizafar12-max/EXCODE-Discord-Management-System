import sqlite3
import os
import werkzeug.security as security

DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'bot_database.db')

def check_pass():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        user = conn.execute("SELECT password_hash FROM web_users WHERE username = 'admin'").fetchone()
        if user:
            matches = security.check_password_hash(user['password_hash'], 'admin_pass')
            print(f"Password 'admin_pass' matches DB hash? {matches}")
        else:
            print("Admin user not found in DB.")
    finally:
        conn.close()

if __name__ == "__main__":
    check_pass()

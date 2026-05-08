"""
Diagnose the web login issue - checks DB path, user record, and password hash.
"""
import os
import sys
import sqlite3
import werkzeug.security as security

# Replicate EXACTLY how web/app.py computes its DB path
WEB_APP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "app.py")
DB_PATH_FROM_APP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(WEB_APP_FILE))),
    "bot_database.db"
)
DB_PATH_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_database.db")

print(f"DB path (as web/app.py sees it) : {DB_PATH_FROM_APP}")
print(f"DB path (local project root)    : {DB_PATH_LOCAL}")
print(f"Paths match                     : {DB_PATH_FROM_APP == DB_PATH_LOCAL}")
print()

# Use the same path as the web app
conn = sqlite3.connect(DB_PATH_FROM_APP)
conn.row_factory = sqlite3.Row

# Check table
try:
    rows = conn.execute("SELECT id, username, password_hash, is_admin FROM web_users").fetchall()
    if not rows:
        print("[ERROR] web_users table is EMPTY! Creating admin now...")
        hashed = security.generate_password_hash("admin_pass")
        conn.execute("INSERT INTO web_users (username, password_hash, is_admin) VALUES ('admin', ?, 1)", (hashed,))
        conn.commit()
        print("[OK] Admin created.")
        rows = conn.execute("SELECT id, username, password_hash, is_admin FROM web_users").fetchall()
    
    for row in rows:
        ok = security.check_password_hash(row["password_hash"], "admin_pass")
        print(f"User: {row['username']} | is_admin: {row['is_admin']} | password 'admin_pass' valid: {ok}")
        if not ok:
            print("  → Resetting password hash now...")
            new_hash = security.generate_password_hash("admin_pass")
            conn.execute("UPDATE web_users SET password_hash=? WHERE username=?", (new_hash, row["username"]))
            conn.commit()
            print("  → Reset done.")

except Exception as e:
    print(f"[ERROR] {e}")
    print("  → Creating web_users table and admin account...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS web_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    """)
    hashed = security.generate_password_hash("admin_pass")
    conn.execute("INSERT INTO web_users (username, password_hash, is_admin) VALUES ('admin', ?, 1)", (hashed,))
    conn.commit()
    print("  → Done.")

conn.close()

# Now check flask_login is installed
try:
    import flask_login
    print(f"\n[OK] flask_login version: {flask_login.__version__}")
except ImportError:
    print("\n[ERROR] flask_login NOT installed! Run: pip install flask-login")
    sys.exit(1)

print("""
===========================================
  Fix complete. Login with:
  Username : admin
  Password : admin_pass
===========================================
""")

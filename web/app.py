from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import werkzeug.security as security
import os
import sqlite3
import json
import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "excode-secret-key-2024-stable-xyz")

# Config
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bot_database.db')

# Auth Config
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, is_admin):
        self.id = id
        self.username = username
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    try:
        user_row = conn.execute("SELECT id, username, is_admin FROM web_users WHERE id = ?", (int(user_id),)).fetchone()
        if user_row:
            return User(user_row['id'], user_row['username'], user_row['is_admin'])
        return None
    finally:
        conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Helper to ensure at least one admin exists
def init_auth():
    conn = get_db_connection()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS web_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        
        admin = conn.execute("SELECT * FROM web_users WHERE username = 'admin'").fetchone()
        if not admin:
            hashed_pw = security.generate_password_hash('admin_pass')
            conn.execute("INSERT INTO web_users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                         ('admin', hashed_pw, 1))
            conn.commit()
            print("[AUTH] Default admin created: admin / admin_pass")
    finally:
        conn.close()

init_auth()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        try:
            user_row = conn.execute("SELECT * FROM web_users WHERE username = ?", (username,)).fetchone()
            if user_row and security.check_password_hash(user_row['password_hash'], password):
                user = User(user_row['id'], user_row['username'], user_row['is_admin'])
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password')
        finally:
            conn.close()
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html')

@app.route('/logs')
@login_required
def logs_page():
    return render_template('logs.html')

@app.route('/tickets')
@login_required
def tickets_page():
    return render_template('tickets.html')

@app.route('/broadcast')
@login_required
def broadcast_page():
    return render_template('broadcast.html')

@app.route('/control')
@login_required
def control_page():
    return render_template('control.html')

@app.route('/moderation')
@login_required
def moderation_page():
    return render_template('moderation.html')

@app.route('/ai_supervisor')
@login_required
def ai_supervisor_page():
    return render_template('ai_supervisor.html')

# --- AI Features ---
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
analyzer = SentimentIntensityAnalyzer()

@app.route('/api/analyze_sentiment/<channel_id>')
@login_required
def analyze_ticket_sentiment(channel_id):
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT content FROM ticket_messages WHERE ticket_id = ? AND is_bot = 0", (channel_id,)).fetchall()
        if not rows:
            return jsonify({'sentiment': 'Neutral', 'score': 0})
        
        full_text = " ".join([row['content'] for row in rows if row['content']])
        if not full_text.strip():
            return jsonify({'sentiment': 'Neutral', 'score': 0})
            
        vs = analyzer.polarity_scores(full_text)
        compound = vs['compound']
        
        if compound >= 0.05:
            sentiment = 'Positive'
        elif compound <= -0.05:
            sentiment = 'Negative'
        else:
            sentiment = 'Neutral'
            
        return jsonify({'sentiment': sentiment, 'score': compound})
    finally:
        conn.close()

# --- Auth Management ---
@app.route('/api/change_credentials', methods=['POST'])
@login_required
def change_credentials():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.json
    new_username = data.get('username')
    new_password = data.get('password')
    
    if not new_username or not new_password:
        return jsonify({'error': 'Missing data'}), 400
        
    hashed_pw = security.generate_password_hash(new_password)
    
    conn = get_db_connection()
    try:
        conn.execute("UPDATE web_users SET username = ?, password_hash = ? WHERE id = ?", 
                     (new_username, hashed_pw, current_user.id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# --- API Endpoints ---

@app.route('/api/tickets/<guild_id>')
@login_required
def get_tickets(guild_id):
    conn = get_db_connection()
    try:
        # Only show open tickets
        rows = conn.execute("SELECT * FROM tickets WHERE guild_id = ? AND status = 'open' ORDER BY created_at DESC", (guild_id,)).fetchall()
        tickets = []
        for row in rows:
            t = dict(row)
            # Convert large IDs to strings for JS safety
            t['channel_id'] = str(t['channel_id'])
            t['guild_id'] = str(t['guild_id'])
            t['owner_id'] = str(t['owner_id'])
            t['owner_name'] = t.get('owner_name') if t.get('owner_name') and t.get('owner_name') != 'Unknown' else f"User {t['owner_id']}"
            t['assigned_to'] = str(t['assigned_to']) if t.get('assigned_to') else None
            t['assigned_name'] = t.get('assigned_name') or 'Unassigned staff'
            t['priority'] = t.get('priority', 'Normal')
            tickets.append(t)
        return jsonify(tickets)
    finally:
        conn.close()

@app.route('/api/ticket_transcript/<channel_id>')
@login_required
def get_ticket_transcript(channel_id):
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY timestamp ASC", (channel_id,)).fetchall()
        msgs = []
        for row in rows:
            m = dict(row)
            m['ticket_id'] = str(m['ticket_id'])
            m['author_id'] = str(m['author_id'])
            msgs.append(m)
        return jsonify(msgs)
    finally:
        conn.close()

@app.route('/api/send_broadcast', methods=['POST'])
@login_required
def send_broadcast_api():
    data = request.json
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    message = data.get('message')
    title = data.get('title')
    image_url = data.get('image_url')
    thumbnail_url = data.get('thumbnail_url')

    if not guild_id or not channel_id or not message:
         return jsonify({'error': 'Missing fields'}), 400

    payload = json.dumps({
        'channel_id': str(channel_id),
        'message': message,
        'title': title,
        'image_url': image_url,
        'thumbnail_url': thumbnail_url
    })

    conn = get_db_connection()
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        conn.execute(
            'INSERT INTO message_queue (guild_id, action_type, payload, created_at) VALUES (?, ?, ?, ?)',
            (guild_id, 'send_broadcast', payload, timestamp)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/send_dm', methods=['POST'])
@login_required
def send_dm_api():
    data = request.json
    guild_id = data.get('guild_id')
    user_id = data.get('user_id')
    message = data.get('message')
    title = data.get('title')
    image_url = data.get('image_url')
    thumbnail_url = data.get('thumbnail_url')
    is_mass = data.get('is_mass', False)

    if not guild_id or not message:
         return jsonify({'error': 'Missing fields'}), 400
    
    if not is_mass and not user_id:
         return jsonify({'error': 'User ID required for single DM'}), 400

    payload = json.dumps({
        'user_id': str(user_id) if user_id else None,
        'message': message,
        'title': title,
        'image_url': image_url,
        'thumbnail_url': thumbnail_url,
        'is_mass': is_mass
    })

    conn = get_db_connection()
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        conn.execute(
            'INSERT INTO message_queue (guild_id, action_type, payload, created_at) VALUES (?, ?, ?, ?)',
            (guild_id, 'send_dm', payload, timestamp)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/send_action', methods=['POST'])
@login_required
def send_action_api():
    data = request.json
    guild_id = data.get('guild_id')
    action = data.get('action') # lockdown, unlock, clear_cache, close_ticket
    
    if not guild_id or not action:
         return jsonify({'error': 'Missing fields'}), 400

    conn = get_db_connection()
    try:
        timestamp = datetime.datetime.utcnow().isoformat()
        
        # Pass all relevant data from the request as the payload
        # Ensure large IDs stay as strings
        payload_dict = {k: str(v) if 'id' in k.lower() else v for k, v in data.items() if k not in ['guild_id', 'action']}
        payload = json.dumps(payload_dict)
        
        conn.execute(
            'INSERT INTO message_queue (guild_id, action_type, payload, created_at) VALUES (?, ?, ?, ?)',
            (guild_id, action, payload, timestamp)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/stats')
@login_required
def get_stats():
    conn = get_db_connection()
    try:
        # Count total logs
        log_count = conn.execute('SELECT COUNT(*) FROM event_logs').fetchone()[0]
        
        # Count tickets (if table exists)
        ticket_count = conn.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]
        
        return jsonify({
            'log_count': log_count,
            'ticket_count': ticket_count,
            'status': 'Online'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/get_settings/<guild_id>')
@login_required
def get_guild_settings(guild_id):
    conn = get_db_connection()
    try:
        # Fetch all settings for this guild
        rows = conn.execute('SELECT key, value FROM guild_settings WHERE guild_id = ?', (guild_id,)).fetchall()
        settings = {row['key']: row['value'] for row in rows}
        return jsonify(settings)
    finally:
        conn.close()

@app.route('/api/supervisor_stats/<guild_id>')
@login_required
def get_supervisor_stats(guild_id):
    conn = get_db_connection()
    try:
        # Get count of toxic messages caught
        toxic_count = conn.execute(
            "SELECT COUNT(*) FROM event_logs WHERE guild_id = ? AND event_type = 'ai_moderation_toxicity'", 
            (guild_id,)
        ).fetchone()[0]
        
        # Get count of active mutes
        active_mutes = conn.execute(
            "SELECT COUNT(*) FROM current_mutes WHERE guild_id = ?", 
            (guild_id,)
        ).fetchone()[0]
        
        # Get 5 recent AI interventions
        recent_logs = conn.execute(
            "SELECT description, timestamp, event_type FROM event_logs WHERE guild_id = ? AND (event_type LIKE 'ai_%' OR event_type = 'mute' OR event_type = 'auto_warning') ORDER BY timestamp DESC LIMIT 5",
            (guild_id,)
        ).fetchall()
        
        logs_list = [dict(row) for row in recent_logs]
        
        return jsonify({
            'toxic_caught': toxic_count,
            'active_mutes': active_mutes,
            'recent_interventions': logs_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/save_setting', methods=['POST'])
@login_required
def save_setting():
    data = request.json
    guild_id = data.get('guild_id')
    key = data.get('key')
    value = data.get('value')
    
    if not guild_id or not key:
        return jsonify({'error': 'Missing data'}), 400
        
    conn = get_db_connection()
    try:
        conn.execute('INSERT OR REPLACE INTO guild_settings (guild_id, key, value) VALUES (?, ?, ?)', (guild_id, key, str(value)))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/logs/<guild_id>')
@login_required
def get_guild_logs(guild_id):
    conn = get_db_connection()
    try:
        rows = conn.execute('SELECT * FROM event_logs WHERE guild_id = ? ORDER BY timestamp DESC LIMIT 50', (guild_id,)).fetchall()
        logs = [dict(row) for row in rows]
        return jsonify(logs)
    finally:
        conn.close()

@app.route('/api/admins/<guild_id>')
@login_required
def get_guild_admins(guild_id):
    conn = get_db_connection()
    try:
        rows = conn.execute('SELECT user_id, added_at FROM bot_admins').fetchall()
        admins = []
        for row in rows:
            admin = dict(row)
            admin['user_id'] = str(admin['user_id'])
            admins.append(admin)
        return jsonify(admins)
    finally:
        conn.close()

@app.route('/api/manage_admin', methods=['POST'])
@login_required
def manage_admin_api():
    data = request.json
    user_id = data.get('user_id')
    guild_id = data.get('guild_id')
    action = data.get('action') # 'add' or 'remove'
    
    if not user_id or not action or not guild_id:
        return jsonify({'error': 'Missing fields'}), 400

    payload = json.dumps({
        'user_id': str(user_id),
        'sub_action': action
    })

    conn = get_db_connection()
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute(
            'INSERT INTO message_queue (guild_id, action_type, payload, created_at) VALUES (?, ?, ?, ?)',
            (guild_id, 'manage_bot_admin', payload, timestamp)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/unmute', methods=['POST'])
@login_required
def unmute_api():
    data = request.json
    user_id = data.get('user_id')
    guild_id = data.get('guild_id')
    
    if not user_id or not guild_id:
        return jsonify({'error': 'Missing fields'}), 400

    payload = json.dumps({
        'user_id': str(user_id)
    })

    conn = get_db_connection()
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute(
            'INSERT INTO message_queue (guild_id, action_type, payload, created_at) VALUES (?, ?, ?, ?)',
            (guild_id, 'unmute', payload, timestamp)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/mutes/<guild_id>')
@login_required
def get_mutes(guild_id):
    """Fetch currently active mutes from the synced current_mutes table"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM current_mutes WHERE guild_id = ? ORDER BY expires_at ASC", 
            (int(guild_id),)
        ).fetchall()
        mutes = []
        for row in rows:
            mute = dict(row)
            mute['user_id'] = str(mute['user_id'])
            mute['guild_id'] = str(mute['guild_id'])
            mutes.append(mute)
        return jsonify(mutes)
    finally:
        conn.close()

@app.route('/api/blacklist/<guild_id>')
@login_required
def get_blacklist(guild_id):
    """Fetch all users in the persistent ban list"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM persistent_bans WHERE guild_id = ? ORDER BY banned_at DESC", 
            (int(guild_id),)
        ).fetchall()
        blacklist = []
        for row in rows:
            item = dict(row)
            item['user_id'] = str(item['user_id'])
            item['guild_id'] = str(item['guild_id'])
            blacklist.append(item)
        return jsonify(blacklist)
    finally:
        conn.close()

@app.route('/api/manage_blacklist', methods=['POST'])
@login_required
def manage_blacklist_api():
    """Remove a user from the persistent ban list"""
    data = request.json
    user_id = data.get('user_id')
    guild_id = data.get('guild_id')
    action = data.get('action') # 'remove' is the only action for now
    
    if not user_id or not guild_id or action != 'remove':
        return jsonify({'error': 'Invalid request'}), 400

    payload = json.dumps({
        'user_id': str(user_id),
        'sub_action': 'remove_blacklist'
    })

    conn = get_db_connection()
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute(
            'INSERT INTO message_queue (guild_id, action_type, payload, created_at) VALUES (?, ?, ?, ?)',
            (guild_id, 'manage_blacklist', payload, timestamp)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)

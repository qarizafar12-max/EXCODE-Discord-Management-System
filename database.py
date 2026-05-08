import aiosqlite
import asyncio
from datetime import datetime

class Database:
    """Database manager for bot data"""
    
    def __init__(self, db_file='bot_database.db'):
        self.db_file = db_file
        self.db = None
    
    async def connect(self):
        """Connect to the database and create tables"""
        self.db = await aiosqlite.connect(self.db_file)
        await self.create_tables()
    
    async def create_tables(self):
        """Create all necessary tables"""
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS persistent_bans (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                user_name TEXT,
                reason TEXT,
                banned_at TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS current_mutes (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                user_name TEXT,
                expires_at TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS infractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT DEFAULT 'Unknown',
                guild_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT,
                duration INTEGER,
                timestamp TEXT NOT NULL
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS user_tracking (
                user_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                join_date TEXT NOT NULL,
                total_messages INTEGER DEFAULT 0,
                last_message TEXT,
                account_created TEXT
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS event_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                description TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS poll_votes (
                poll_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                option_index INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                PRIMARY KEY (poll_id, user_id)
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS invites (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                regular INTEGER DEFAULT 0,
                fake INTEGER DEFAULT 0,
                bonus INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS sticky_messages (
                channel_id INTEGER PRIMARY KEY,
                message TEXT,
                last_message_id INTEGER
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS auto_responses (
                trigger TEXT PRIMARY KEY,
                response TEXT
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS bot_admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_at TEXT
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id INTEGER PRIMARY KEY,
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                updated_at TEXT
            )
        ''')
        # Note: server_settings needs a composite key or cleaner structure? 
        # Actually, let's use a Key-Value store per guild or a wide table.
        # Key-Value is more flexible for "smart config". 
        # Schema: guild_id | key | value
        
        # Correction: The above schema would only allow one setting per guild. 
        # Correct schema: PRIMARY KEY (guild_id, setting_key)
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                PRIMARY KEY (guild_id, key)
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS web_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS levels (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                last_xp_time TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS level_rewards (
                guild_id INTEGER NOT NULL,
                level INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, level)
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                owner_name TEXT DEFAULT 'Unknown',
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'Normal',
                assigned_to INTEGER DEFAULT NULL,
                assigned_name TEXT DEFAULT NULL,
                created_at TEXT NOT NULL
            )
        ''')

        # Simple migration for existing databases
        # Migrations for existing databases
        try:
            await self.db.execute("ALTER TABLE tickets ADD COLUMN priority TEXT DEFAULT 'Normal'")
            await self.db.commit()
        except: pass
        
        try:
            await self.db.execute("ALTER TABLE tickets ADD COLUMN assigned_to INTEGER DEFAULT NULL")
            await self.db.commit()
        except: pass
        
        try:
            await self.db.execute("ALTER TABLE tickets ADD COLUMN owner_name TEXT DEFAULT 'Unknown'")
            await self.db.commit()
        except: pass
        
        try:
            await self.db.execute("ALTER TABLE tickets ADD COLUMN assigned_name TEXT DEFAULT NULL")
            await self.db.commit()
        except: pass

        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS message_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        ''')

        await self.db.execute('''
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

        # Migration: Add user_name to infractions
        try:
            await self.db.execute("ALTER TABLE infractions ADD COLUMN user_name TEXT DEFAULT 'Unknown'")
        except: pass

        await self.db.commit()

    # Admin Methods
    async def add_admin(self, user_id, added_by):
        timestamp = datetime.now().isoformat()
        try:
            await self.db.execute(
                'INSERT INTO bot_admins (user_id, added_by, added_at) VALUES (?, ?, ?)',
                (user_id, added_by, timestamp)
            )
            await self.db.commit()
            return True
        except:
            return False # Already exists

    async def remove_admin(self, user_id):
        await self.db.execute('DELETE FROM bot_admins WHERE user_id = ?', (int(user_id),))
        await self.db.commit()

    async def is_bot_admin(self, user_id):
        async with self.db.execute('SELECT user_id FROM bot_admins WHERE user_id = ?', (int(user_id),)) as cursor:
            return await cursor.fetchone() is not None

    async def get_all_admins(self):
        async with self.db.execute('SELECT user_id FROM bot_admins') as cursor:
            return [row[0] for row in await cursor.fetchall()]

    # Web Portal Auth Methods
    async def create_web_user(self, username, password_hash, is_admin=0):
        try:
            await self.db.execute(
                'INSERT INTO web_users (username, password_hash, is_admin) VALUES (?, ?, ?)',
                (username, password_hash, is_admin)
            )
            await self.db.commit()
            return True
        except:
            return False

    async def get_web_user(self, username):
        async with self.db.execute('SELECT * FROM web_users WHERE username = ?', (username,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "username": row[1], "password_hash": row[2], "is_admin": row[3]}
            return None

    async def update_web_user_password(self, username, new_password_hash):
        await self.db.execute('UPDATE web_users SET password_hash = ? WHERE username = ?', (new_password_hash, username))
        await self.db.commit()

    # Sticky Messages
    async def get_sticky_message(self, channel_id):
        async with self.db.execute('SELECT message, last_message_id FROM sticky_messages WHERE channel_id = ?', (channel_id,)) as cursor:
            return await cursor.fetchone()

    async def set_sticky_message(self, channel_id, message, last_message_id):
        await self.db.execute(
            'INSERT OR REPLACE INTO sticky_messages (channel_id, message, last_message_id) VALUES (?, ?, ?)',
            (channel_id, message, last_message_id)
        )
        await self.db.commit()

    async def remove_sticky_message(self, channel_id):
        await self.db.execute('DELETE FROM sticky_messages WHERE channel_id = ?', (channel_id,))
        await self.db.commit()

    async def update_sticky_last_id(self, channel_id, last_message_id):
        await self.db.execute('UPDATE sticky_messages SET last_message_id = ? WHERE channel_id = ?', (last_message_id, channel_id))
        await self.db.commit()

    # Auto Responses
    async def add_auto_response(self, trigger, response):
        try:
            await self.db.execute('INSERT INTO auto_responses (trigger, response) VALUES (?, ?)', (trigger.lower(), response))
            await self.db.commit()
            return True
        except:
            return False

    async def remove_auto_response(self, trigger):
        await self.db.execute('DELETE FROM auto_responses WHERE trigger = ?', (trigger.lower(),))
        await self.db.commit()

    async def get_auto_responses(self):
        async with self.db.execute('SELECT trigger, response FROM auto_responses') as cursor:
            return await cursor.fetchall()

    # Invite methods
    async def get_invites(self, user_id, guild_id):
        """Get invite data for a user"""
        async with self.db.execute(
            'SELECT regular, fake, bonus FROM invites WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return {'regular': result[0], 'fake': result[1], 'bonus': result[2]}
            return {'regular': 0, 'fake': 0, 'bonus': 0}

    async def update_invites(self, user_id, guild_id, change_regular=0, change_fake=0, change_bonus=0):
        """Update invite counts"""
        current = await self.get_invites(user_id, guild_id)
        
        new_regular = max(0, current['regular'] + change_regular)
        new_fake = max(0, current['fake'] + change_fake)
        new_bonus = max(0, current['bonus'] + change_bonus)
        
        await self.db.execute(
            'INSERT OR REPLACE INTO invites (user_id, guild_id, regular, fake, bonus) VALUES (?, ?, ?, ?, ?)',
            (user_id, guild_id, new_regular, new_fake, new_bonus)
        )
        await self.db.commit()
    
    async def get_top_inviters(self, guild_id, limit=10):
        """Get leaderboard"""
        async with self.db.execute(
            'SELECT user_id, regular, fake, bonus FROM invites WHERE guild_id = ? ORDER BY (regular + bonus - fake) DESC LIMIT ?',
            (guild_id, limit)
        ) as cursor:
            return await cursor.fetchall()

    # Poll methods
    async def add_poll_vote(self, poll_id, user_id, option_index):
        """Add a vote to a poll"""
        timestamp = datetime.utcnow().isoformat()
        try:
            await self.db.execute(
                'INSERT OR REPLACE INTO poll_votes (poll_id, user_id, option_index, timestamp) VALUES (?, ?, ?, ?)',
                (poll_id, user_id, option_index, timestamp)
            )
            await self.db.commit()
            return True
        except Exception as e:
            print(f"Error adding vote: {e}")
            return False

    async def get_poll_votes(self, poll_id):
        """Get all votes for a poll"""
        async with self.db.execute(
            'SELECT option_index, COUNT(*) FROM poll_votes WHERE poll_id = ? GROUP BY option_index',
            (poll_id,)
        ) as cursor:
            return await cursor.fetchall()
    
    # Warning methods
    async def add_warning(self, user_id, guild_id, moderator_id, reason):
        """Add a warning to a user"""
        timestamp = datetime.utcnow().isoformat()
        await self.db.execute(
            'INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)',
            (user_id, guild_id, moderator_id, reason, timestamp)
        )
        await self.db.commit()
    
    async def get_warnings(self, user_id, guild_id):
        """Get all warnings for a user"""
        async with self.db.execute(
            'SELECT * FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC',
            (user_id, guild_id)
        ) as cursor:
            return await cursor.fetchall()
    
    async def get_warning_count(self, user_id, guild_id):
        """Get the number of warnings for a user"""
        async with self.db.execute(
            'SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def clear_warnings(self, user_id, guild_id):
        """Clear all warnings for a user"""
        await self.db.execute(
            'DELETE FROM warnings WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        )
        await self.db.commit()
    
    # Infraction methods
    async def add_infraction(self, user_id, guild_id, infraction_type, moderator_id, reason, duration=None, user_name='Unknown'):
        """Add an infraction (mute, kick, ban)"""
        timestamp = datetime.utcnow().isoformat()
        await self.db.execute(
            'INSERT INTO infractions (user_id, user_name, guild_id, type, moderator_id, reason, duration, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (int(user_id), user_name, int(guild_id), infraction_type, int(moderator_id), reason, duration, timestamp)
        )
        await self.db.commit()
    
    async def get_infractions(self, user_id, guild_id):
        """Get all infractions for a user"""
        async with self.db.execute(
            'SELECT * FROM infractions WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC',
            (user_id, guild_id)
        ) as cursor:
            return await cursor.fetchall()
            
    async def get_user_trust_score(self, user_id, guild_id, ai_cog=None):
        """
        Calculate a trust score for a user from 0 to 100 based on local heuristics.
        0-30 = Low trust (new, infractions, toxic)
        31-70 = Normal (average member)
        71-100 = High trust (long time, active, positive)
        """
        score = 50  # Start at neutral
        
        # Factor 1: Account age in server and message count
        user_data = await self.get_user_data(user_id, guild_id)
        if user_data:
            messages = user_data[3]  # total_messages
            # +1 score for every 100 messages up to +20
            score += min(20, messages / 100)
            
            try:
                join_date = datetime.fromisoformat(user_data[2])
                days_in_server = (datetime.utcnow() - join_date).days
                # +1 score for every 30 days up to +15
                score += min(15, days_in_server / 30)
            except:
                pass
                
        # Factor 2: XP / Levels
        xp_data = await self.get_xp(user_id, guild_id)
        if xp_data:
            level = xp_data[1]
            # +1 score for every level up to +15
            score += min(15, level)
            
        # Factor 3: Infractions
        infractions = await self.get_infractions(user_id, guild_id)
        for inf in infractions:
            itype = inf[4] # type
            if itype == 'warning':
                score -= 10
            elif itype == 'mute':
                score -= 25
            elif itype == 'kick':
                score -= 40
            elif itype == 'ban':
                score -= 60
                
        # Factor 4: AI Sentiment Analysis (If available)
        if ai_cog:
            # We don't want to loop through all history on every check for speed,
            # but we can look at some cached value or do a fast small check if needed.
            # For now, let's keep it simple and just rely on the above metrics. 
            pass
            
        # Bound between 0 and 100
        return max(0, min(100, int(score)))
    
    # User tracking methods
    async def track_user_join(self, user_id, guild_id, account_created):
        """Track when a user joins"""
        join_date = datetime.utcnow().isoformat()
        await self.db.execute(
            'INSERT OR REPLACE INTO user_tracking (user_id, guild_id, join_date, account_created, total_messages) VALUES (?, ?, ?, ?, 0)',
            (user_id, guild_id, join_date, account_created.isoformat())
        )
        await self.db.commit()
    
    async def increment_message_count(self, user_id, guild_id):
        """Increment a user's message count"""
        last_message = datetime.utcnow().isoformat()
        await self.db.execute(
            'UPDATE user_tracking SET total_messages = total_messages + 1, last_message = ? WHERE user_id = ? AND guild_id = ?',
            (last_message, user_id, guild_id)
        )
        await self.db.commit()
    
    async def get_user_data(self, user_id, guild_id):
        """Get user tracking data"""
        async with self.db.execute(
            'SELECT * FROM user_tracking WHERE user_id = ? AND guild_id = ?',
            (user_id, guild_id)
        ) as cursor:
            return await cursor.fetchone()
    
    # Event logging methods
    async def log_event(self, guild_id, event_type, description, user_id=None):
        """Log a server event"""
        timestamp = datetime.utcnow().isoformat()
        await self.db.execute(
            'INSERT INTO event_logs (guild_id, event_type, user_id, description, timestamp) VALUES (?, ?, ?, ?, ?)',
            (guild_id, event_type, user_id, description, timestamp)
        )
        await self.db.commit()
    
    async def get_recent_events(self, guild_id, limit=50):
        """Get recent events"""
        async with self.db.execute(
            'SELECT * FROM event_logs WHERE guild_id = ? ORDER BY timestamp DESC LIMIT ?',
            (guild_id, limit)
        ) as cursor:
            return await cursor.fetchall()
    
    async def close(self):
        """Close the database connection"""
        if self.db:
            await self.db.close()

    # Settings Methods
    async def get_setting(self, guild_id, key, default=None):
        async with self.db.execute('SELECT value FROM guild_settings WHERE guild_id = ? AND key = ?', (guild_id, key)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else default

    async def set_setting(self, guild_id, key, value):
        await self.db.execute(
            'INSERT OR REPLACE INTO guild_settings (guild_id, key, value) VALUES (?, ?, ?)',
            (guild_id, key, str(value))
        )
        await self.db.commit()

    # Leveling Methods
    async def get_xp(self, user_id, guild_id):
        async with self.db.execute('SELECT xp, level, last_xp_time FROM levels WHERE user_id = ? AND guild_id = ?', (user_id, guild_id)) as cursor:
            return await cursor.fetchone()

    async def update_xp(self, user_id, guild_id, xp, level):
        timestamp = datetime.utcnow().isoformat()
        await self.db.execute(
            'INSERT OR REPLACE INTO levels (user_id, guild_id, xp, level, last_xp_time) VALUES (?, ?, ?, ?, ?)',
            (user_id, guild_id, xp, level, timestamp)
        )
        await self.db.commit()

    async def get_leaderboard(self, guild_id, limit=10):
        async with self.db.execute('SELECT user_id, xp, level FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT ?', (guild_id, limit)) as cursor:
            return await cursor.fetchall()
            
    async def add_level_reward(self, guild_id, level, role_id):
        await self.db.execute('INSERT OR REPLACE INTO level_rewards (guild_id, level, role_id) VALUES (?, ?, ?)', (guild_id, level, role_id))
        await self.db.commit()
    
    async def get_level_reward(self, guild_id, level):
        async with self.db.execute('SELECT role_id FROM level_rewards WHERE guild_id = ? AND level = ?', (guild_id, level)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else None

    # Ticket Methods
    async def create_ticket(self, channel_id, guild_id, owner_id, owner_name="Unknown"):
        try:
            # Ensure we are saving as integers
            channel_id = int(channel_id)
            guild_id = int(guild_id)
            owner_id = int(owner_id)
            
            timestamp = datetime.utcnow().isoformat()
            await self.db.execute(
                'INSERT INTO tickets (channel_id, guild_id, owner_id, owner_name, status, priority, assigned_to, assigned_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (channel_id, guild_id, owner_id, owner_name, 'open', 'Normal', None, None, timestamp)
            )
            await self.db.commit()
            print(f"[DB] Created ticket record for {channel_id}")
            return True
        except Exception as e:
            print(f"[DB ERROR] Failed to create ticket {channel_id}: {e}")
            return False

    async def close_ticket(self, channel_id):
        try:
            await self.db.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (channel_id,))
            await self.db.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] Failed to close ticket {channel_id}: {e}")
            return False
        
    async def get_ticket(self, channel_id):
        async with self.db.execute("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)) as cursor:
            return await cursor.fetchone()

    async def log_ticket_message(self, ticket_id, author_id, author_name, content, is_bot=0):
        try:
            timestamp = datetime.utcnow().isoformat()
            await self.db.execute(
                'INSERT INTO ticket_messages (ticket_id, author_id, author_name, content, is_bot, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
                (ticket_id, author_id, author_name, content, is_bot, timestamp)
            )
            await self.db.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] Failed to log ticket message for ticket {ticket_id}: {e}")
            return False

    async def get_ticket_messages(self, ticket_id):
        async with self.db.execute("SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY timestamp ASC", (ticket_id,)) as cursor:
            return await cursor.fetchall()

    async def update_ticket_priority(self, channel_id, priority):
        try:
            # Ensure priority is a plain string (not a dict/object from JSON payload)
            priority_str = str(priority) if not isinstance(priority, str) else priority
            await self.db.execute("UPDATE tickets SET priority = ? WHERE channel_id = ?", (priority_str, int(channel_id)))
            await self.db.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] Failed to update priority for ticket {channel_id}: {e}")
            return False

    async def transfer_ticket(self, channel_id, admin_id, admin_name=None):
        try:
            val_id = int(admin_id) if admin_id else None
            if admin_name:
                await self.db.execute("UPDATE tickets SET assigned_to = ?, assigned_name = ? WHERE channel_id = ?", (val_id, admin_name, int(channel_id)))
            else:
                await self.db.execute("UPDATE tickets SET assigned_to = ? WHERE channel_id = ?", (val_id, int(channel_id)))
            await self.db.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] Failed to transfer ticket {channel_id}: {e}")
            return False

    async def get_open_tickets(self, guild_id):
        async with self.db.execute("SELECT * FROM tickets WHERE guild_id = ? AND status = 'open' ORDER BY created_at DESC", (int(guild_id),)) as cursor:
            return await cursor.fetchall()

    # Queue Methods (Web -> Bot IPC)
    async def add_to_queue(self, guild_id, action_type, payload_json):
        timestamp = datetime.utcnow().isoformat()
        await self.db.execute(
            'INSERT INTO message_queue (guild_id, action_type, payload, created_at) VALUES (?, ?, ?, ?)',
            (guild_id, action_type, payload_json, timestamp)
        )
        await self.db.commit()

    async def get_pending_tasks(self):
        async with self.db.execute("SELECT * FROM message_queue WHERE status = 'pending' ORDER BY created_at ASC") as cursor:
            return await cursor.fetchall()

    async def complete_task(self, task_id, status='completed'):
        await self.db.execute("UPDATE message_queue SET status = ? WHERE id = ?", (status, task_id))
        await self.db.commit()

    async def update_infraction_name(self, user_id, user_name):
        """Update the username for a user in the infractions table"""
        await self.db.execute(
            "UPDATE infractions SET user_name = ? WHERE user_id = ? AND (user_name = 'Unknown' OR user_name IS NULL)",
            (user_name, user_id)
        )
        await self.db.commit()

    async def sync_current_mute(self, user_id, guild_id, user_name, expires_at):
        """Add or update an active mute"""
        await self.db.execute(
            'INSERT OR REPLACE INTO current_mutes (user_id, guild_id, user_name, expires_at) VALUES (?, ?, ?, ?)',
            (user_id, guild_id, user_name, expires_at)
        )
        await self.db.commit()

    async def remove_current_mute(self, user_id, guild_id):
        """Remove a mute from the active mutes table"""
        await self.db.execute(
            'DELETE FROM current_mutes WHERE user_id = ? AND guild_id = ?',
            (int(user_id), int(guild_id))
        )
        await self.db.commit()

    async def clear_expired_mutes(self, guild_id, current_time_iso):
        """Remove mutes that have expired according to the stored timestamp"""
        await self.db.execute(
            'DELETE FROM current_mutes WHERE guild_id = ? AND expires_at < ?',
            (int(guild_id), current_time_iso)
        )
        await self.db.commit()

    async def get_current_mutes(self, guild_id):
        """Fetch all currently active mutes for a guild"""
        async with self.db.execute('SELECT * FROM current_mutes WHERE guild_id = ?', (int(guild_id),)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_persistent_ban(self, user_id, guild_id, user_name, reason):
        """Add a user to the persistent ban list"""
        timestamp = datetime.now().isoformat()
        await self.db.execute(
            'INSERT OR REPLACE INTO persistent_bans (user_id, guild_id, user_name, reason, banned_at) VALUES (?, ?, ?, ?, ?)',
            (int(user_id), int(guild_id), user_name, reason, timestamp)
        )
        await self.db.commit()

    async def remove_persistent_ban(self, user_id, guild_id):
        """Remove a user from the persistent ban list"""
        cursor = await self.db.execute(
            'DELETE FROM persistent_bans WHERE user_id = ? AND guild_id = ?',
            (int(user_id), int(guild_id))
        )
        await self.db.commit()
        print(f"[DB DEBUG] Blacklist removal for {user_id} in {guild_id}: Affected {cursor.rowcount} rows")

    async def is_persistently_banned(self, user_id, guild_id):
        """Check if a user is in the persistent ban list"""
        async with self.db.execute(
            'SELECT 1 FROM persistent_bans WHERE user_id = ? AND guild_id = ?', 
            (int(user_id), int(guild_id))
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_persistent_bans(self, guild_id):
        """Fetch all persistent bans for a guild"""
        async with self.db.execute('SELECT * FROM persistent_bans WHERE guild_id = ?', (int(guild_id),)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]



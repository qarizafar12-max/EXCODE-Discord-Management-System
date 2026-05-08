import re
from collections import defaultdict
from datetime import datetime, timedelta

class MessageTracker:
    """Track messages for spam detection"""
    def __init__(self):
        self.user_messages = defaultdict(list)
        self.user_content_history = defaultdict(list)
    
    def add_message(self, user_id, content, timestamp):
        """Add a message to tracking"""
        self.user_messages[user_id].append(timestamp)
        self.user_content_history[user_id].append(content)
        
        # Clean old messages (older than 10 seconds)
        cutoff = timestamp - timedelta(seconds=10)
        self.user_messages[user_id] = [
            ts for ts in self.user_messages[user_id] if ts > cutoff
        ]
        
        # Keep only last 10 messages
        if len(self.user_content_history[user_id]) > 10:
            self.user_content_history[user_id] = self.user_content_history[user_id][-10:]
    
    def get_message_count(self, user_id, seconds=10):
        """Get message count in the last N seconds"""
        return len(self.user_messages.get(user_id, []))
    
    def get_recent_messages(self, user_id, count=5):
        """Get recent messages from a user"""
        return self.user_content_history.get(user_id, [])[-count:]

# Global message tracker
message_tracker = MessageTracker()

def is_spam(message, config, trust_score=50):
    """Detect if a message is spam"""
    user_id = message.author.id
    content = message.content
    timestamp = datetime.utcnow()
    
    # Add message to tracker
    message_tracker.add_message(user_id, content, timestamp)
    
    settings = config.moderation_settings
    base_spam_threshold = settings.get('spam_threshold', 5)
    base_caps_threshold = settings.get('caps_threshold', 0.7)
    
    # Adjust thresholds based on trust score
    # High trust users (>70) get 2x leniency, low trust users (<30) get 0.5x strictness
    multiplier = 1.0
    if trust_score > 70:
        multiplier = 2.0
    elif trust_score < 30:
        multiplier = 0.5
        
    spam_threshold = max(2, int(base_spam_threshold * multiplier))
    caps_threshold = min(0.95, base_caps_threshold * multiplier)
    
    # Check message rate (rapid posting)
    message_count = message_tracker.get_message_count(user_id)
    if message_count >= spam_threshold:
        return True, f"Rapid message posting (spam) - Threshold {spam_threshold}"
    
    # Check for repeated messages
    recent_messages = message_tracker.get_recent_messages(user_id, 5)
    if len(recent_messages) >= 3:
        if recent_messages[-1] == recent_messages[-2] == recent_messages[-3]:
            return True, "Repeated messages"
    
    # Check for excessive caps
    if len(content) > 10:
        caps_count = sum(1 for c in content if c.isupper())
        if caps_count / len(content) > caps_threshold:
            return True, "Excessive caps"
    
    # Check for excessive mentions
    if len(message.mentions) > 5:
        return True, "Excessive mentions"
    
    # Check for excessive emojis
    emoji_pattern = r'<:[^:]+:\d+>|[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]'
    emojis = re.findall(emoji_pattern, content)
    if len(emojis) > 10:
        return True, "Excessive emojis"
    
    return False, None

def is_toxic(message, config, trust_score=50):
    """Detect if a message contains toxic content"""
    content = message.content.lower()
    
    settings = config.moderation_settings
    toxic_words = settings.get('toxic_words', [])
    
    # Get toxic words from config
    settings = config.moderation_settings
    toxic_words = settings.get('toxic_words', [])
    
    # Check for toxic words
    for word in toxic_words:
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, content):
            return True, f"Toxic language detected"
    
    # Adjust profanity tolerance based on trust score
    max_profanity = 2
    if trust_score > 70:
        max_profanity = 4
    elif trust_score < 30:
        max_profanity = 1
        
    # Check for excessive profanity (basic list)
    profanity = ['fuck', 'shit', 'bitch', 'ass', 'damn', 'hell', 'crap', 'fuk', 'shit', 'fuc', 'fck']
    profanity_count = sum(1 for word in profanity if word in content)
    if profanity_count > max_profanity or any(word in content for word in ['fuck', 'shitting']):
        return True, "Toxic language detected"
    
    return False, None

def is_suspicious_link(message):
    """Detect suspicious links"""
    content = message.content.lower()
    
    # URL pattern
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, content)
    
    if not urls:
        return False, None
    
    # Check for IP addresses (often malicious)
    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    if re.search(ip_pattern, content):
        return True, "Suspicious IP address link"
    
    # Check for URL shorteners (can hide malicious links)
    shorteners = ['bit.ly', 'tinyurl', 'goo.gl', 't.co', 'ow.ly', 'is.gd']
    for shortener in shorteners:
        if shortener in content:
            return True, f"URL shortener detected: {shortener}"
    
    # Check for too many links
    if len(urls) > 3:
        return True, "Excessive links"
    
    return False, None

async def check_message(message, config, db):
    """Run all detection checks on a message"""
    # Skip bots
    if message.author.bot:
        return None
    
    # Skip admins
    if config.is_admin(message.author.id):
        return None
        
    # Get user trust score
    trust_score = await db.get_user_trust_score(message.author.id, message.guild.id)
    
    # Check for spam
    is_spam_msg, spam_reason = is_spam(message, config, trust_score)
    if is_spam_msg:
        return {'type': 'spam', 'reason': spam_reason}
    
    # Check for toxicity
    is_toxic_msg, toxic_reason = is_toxic(message, config, trust_score)
    if is_toxic_msg:
        return {'type': 'toxic', 'reason': toxic_reason}
    
    # Check for suspicious links
    is_suspicious, link_reason = is_suspicious_link(message)
    if is_suspicious:
        return {'type': 'suspicious_link', 'reason': link_reason}
    
    return None

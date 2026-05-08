import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration manager for the bot"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.data = self.load_config()
    
    def load_config(self):
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            # Create a default config if it doesn't exist
            return {}
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_config(self):
        """Save configuration to JSON file"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    @property
    def token(self):
        return os.getenv('DISCORD_BOT_TOKEN') or self.data.get('bot_token')
        
    @property
    def gemini_api_key(self):
        return os.getenv('GEMINI_API_KEY') or self.data.get('gemini_api_key')

    @property
    def openrouter_api_key(self):
        return os.getenv('OPENROUTER_API_KEY') or self.data.get('openrouter_api_key')
    
    @property
    def admin_ids(self):
        return self.data.get('admin_ids', [])
    
    @property
    def guild_id(self):
        return self.data.get('guild_id')
    
    @property
    def server_configs(self):
        return self.data.get('server_configs', {})

    def get_welcome_channel(self, guild_id):
        """Get welcome channel for a specific guild"""
        # Check specific server config first
        str_id = str(guild_id)
        if str_id in self.server_configs:
            server_config = self.server_configs[str_id]
            channels = server_config.get('channels', {})
            if 'welcome' in channels:
                return channels['welcome']
        
        # Fallback to global config
        return self.data.get('channels', {}).get('welcome')

    @property
    def welcome_channel(self):
        # Kept for backward compatibility, returns default
        return self.data.get('channels', {}).get('welcome')
    
    @property
    def rules_channel(self):
        return self.data.get('channels', {}).get('rules')
    
    @property
    def logs_channel(self):
        return self.data.get('channels', {}).get('logs')
    
    @property
    def auto_role(self):
        return self.data.get('auto_role', 'Member')
    
    @property
    def welcome_message(self):
        return self.data.get('welcome_message', '')
    
    @property
    def rules_dm(self):
        return self.data.get('rules_dm', '')
    
    @property
    def moderation_settings(self):
        return self.data.get('moderation', {})

    @property
    def moderation_responses(self):
        return self.data.get('moderation_responses', {})
    
    @property
    def antiraid_settings(self):
        return self.data.get('antiraid', {})
    
    @property
    def ai_settings(self):
        return self.data.get('ai', {})
    
    @property
    def suggestions_settings(self):
        return self.data.get('suggestions', {})
        
    @property
    def polls_settings(self):
        return self.data.get('polls', {})

    @property
    def tickets_settings(self):
        return self.data.get('tickets', {})
    
    def is_admin(self, user_id):
        """Check if a user is an admin"""
        return user_id in self.admin_ids

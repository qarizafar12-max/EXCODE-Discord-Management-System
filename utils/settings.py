import discord
from config import Config

class SettingsManager:
    """Helper to manage per-server settings"""
    
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.db = bot.db

    async def get_setting(self, guild_id, key, default=None):
        """Get a setting with fallback to config.json"""
        # 1. Check Database
        db_value = await self.db.get_setting(guild_id, key)
        if db_value:
            return db_value
            
        # 2. Check Config (Global Defaults)
        # Map DB keys to Config properties if needed
        if key == 'welcome_channel':
            return self.config.welcome_channel
        elif key == 'rules_channel':
            return self.config.rules_channel
        elif key == 'logs_channel':
            return self.config.logs_channel
        elif key == 'auto_role':
            return self.config.auto_role
        elif key == 'welcome_message':
            return self.config.welcome_message
            
        return default

    async def set_setting(self, guild_id, key, value):
        """Set a setting for a guild"""
        await self.db.set_setting(guild_id, key, value)

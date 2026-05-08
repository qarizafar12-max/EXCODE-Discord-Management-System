import threading
import asyncio
import sys
import os
import time

# Add current directory to path so we can import bot and web
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from bot import main as start_bot
    from web.app import app as flask_app
except ImportError as e:
    print(f"[ERROR] Could not import bot or web: {e}")
    sys.exit(1)

def run_flask():
    """Run the Flask web server"""
    print("[WEB] Starting Web Dashboard on http://localhost:5000...")
    # We turn off debug mode because it can cause issues with threading
    flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

async def run_system():
    """Main system orchestrator"""
    # Start Web Dashboard in a background thread
    web_thread = threading.Thread(target=run_flask, daemon=True)
    web_thread.start()
    
    # Wait a moment for web to initialize
    time.sleep(1)
    
    # Start Discord Bot in the main thread (keeps process alive)
    print("[BOT] Starting Discord Bot...")
    try:
        await start_bot()
    except KeyboardInterrupt:
        print("\nStopping system...")
    except Exception as e:
        print(f"[ERROR] Bot stopped unexpectedly: {e}")

if __name__ == "__main__":
    print("===================================================")
    print("    EXCODE UNIFIED LAUNCHER (BOT + DASHBOARD)    ")
    print("===================================================")
    
    try:
        asyncio.run(run_system())
    except KeyboardInterrupt:
        print("\n\nSystem shutting down...")
        sys.exit(0)

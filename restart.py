import os
import subprocess
import time
import signal
import requests
import threading
from datetime import datetime
import psutil
import platform
from flask import Flask, request, jsonify

# Configuration
REPO_URL = "https://github.com/mautddos/semxi.git"
FOLDER_NAME = "semxi"
SCRIPT_NAME = "xhamster.py"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "xhamster.log")
RESTART_INTERVAL = 45 * 60  # 45 minutes
UPTIME_PING_INTERVAL = 3600  # 1 hour
MONITOR_INTERVAL = 900  # 15 minutes

BOT_TOKEN = "7683433576:AAFGuDfoFo4Q6cvvlWBk9QTCGwPbAGRfX-k"
USER_ID = "8167507955"
APP_PORT = 8080  # Flask port

# Global variables
app = Flask(__name__)
current_process = None
start_time = time.time()
command_lock = threading.Lock()

def send_telegram(text, parse_mode="Markdown"):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": USER_ID,
                "text": text,
                "parse_mode": parse_mode
            },
            timeout=10
        )
    except Exception as e:
        print(f"Telegram send error: {e}")

def send_log_tail(lines=15, title="Recent Logs"):
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                content = f.readlines()[-lines:]
                message = f"*{title}*\n```\n" + "".join(content) + "\n```"
                send_telegram(message)
        else:
            send_telegram("No log file found.")
    except Exception as e:
        print(f"Log tail error: {e}")

def get_system_status():
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        uptime = int(time.time() - start_time)
        load_avg = os.getloadavg()
        
        status_msg = (
            "📊 *System Status*\n"
            f"• CPU: {cpu}% (Load: {load_avg[0]:.2f})\n"
            f"• RAM: {ram.used//1024//1024}MB/{ram.total//1024//1024}MB ({ram.percent}%)\n"
            f"• Disk: {disk.used//1024//1024}MB/{disk.total//1024//1024}MB ({disk.percent}%)\n"
            f"• Uptime: {uptime//3600}h {(uptime%3600)//60}m\n"
            f"• OS: {platform.system()} {platform.release()}\n"
            f"• Bot PID: {os.getpid()}"
        )
        return status_msg
    except Exception as e:
        return f"⚠️ Status error: {str(e)}"

def get_ping_stats():
    try:
        ping_cmd = ["ping", "-c", "4", "8.8.8.8"]
        if platform.system().lower() == "windows":
            ping_cmd = ["ping", "-n", "4", "8.8.8.8"]
            
        ping_result = subprocess.run(
            ping_cmd,
            capture_output=True,
            text=True,
            timeout=15
        )
        return f"🌐 *Ping Results*\n```\n{ping_result.stdout}\n```"
    except Exception as e:
        return f"⚠️ Ping failed: {str(e)}"

def setup():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        if not os.path.exists(FOLDER_NAME):
            subprocess.run(["git", "clone", REPO_URL], check=True)
            send_telegram("✅ Repository cloned successfully")
        else:
            send_telegram("ℹ️ Repository already exists")
    except Exception as e:
        send_telegram(f"❌ Setup failed: {str(e)}")

def pull_latest():
    try:
        subprocess.run(["git", "pull"], cwd=FOLDER_NAME, check=True)
        send_telegram("🔄 Repository updated")
    except Exception as e:
        send_telegram(f"❌ Update failed: {str(e)}")

def run_script():
    try:
        with open(LOG_FILE, "a") as logfile:
            logfile.write(f"\n[{datetime.now()}] Starting script...\n")
        
        process = subprocess.Popen(
            ["python3", SCRIPT_NAME],
            cwd=FOLDER_NAME,
            stdout=open(LOG_FILE, "a"),
            stderr=subprocess.STDOUT
        )
        send_telegram("🚀 Script started successfully")
        return process
    except Exception as e:
        send_telegram(f"❌ Script start failed: {str(e)}")
        return None

def stop_script(process):
    try:
        if process and process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=10)
                send_telegram("🛑 Script stopped gracefully")
            except subprocess.TimeoutExpired:
                process.kill()
                send_telegram("⚠️ Script force stopped")
    except Exception as e:
        send_telegram(f"❌ Stop failed: {str(e)}")

def restart_bot():
    with command_lock:
        send_telegram("🔄 Starting restart process...")
        stop_script(current_process)
        pull_latest()
        new_process = run_script()
        
        global current_process
        current_process = new_process
        
        send_telegram("✅ Restart completed")
        send_log_tail(10, "Post-Restart Logs")

def monitor_uptime():
    while True:
        time.sleep(UPTIME_PING_INTERVAL)
        uptime = int((time.time() - start_time) / 60)
        send_telegram(f"⏱ Bot uptime: {uptime} minutes")

def monitor_resources():
    while True:
        time.sleep(MONITOR_INTERVAL)
        try:
            ram = psutil.virtual_memory().used // (1024 * 1024)
            cpu = psutil.cpu_percent(interval=1)
            send_telegram(f"📈 Resource Monitor\nCPU: {cpu}% | RAM: {ram}MB")
        except Exception as e:
            print(f"Monitor error: {e}")

def run_flask():
    @app.route(f"/{BOT_TOKEN}", methods=["POST"])
    def webhook():
        try:
            data = request.get_json()
            if not data or "message" not in data:
                return jsonify({"status": "invalid request"})
                
            message = data["message"]
            text = message.get("text", "").strip().lower()
            chat_id = str(message["chat"]["id"])
            
            if chat_id != USER_ID:
                return jsonify({"status": "unauthorized"})
            
            # Process commands
            if text == "/start":
                response = (
                    "🤖 *Bot Control Panel* 🤖\n\n"
                    "Available commands:\n"
                    "• /start - Show this help\n"
                    "• /status - System resources\n"
                    "• /ping - Network test\n"
                    "• /restart - Restart service\n"
                    "• /logs - Show recent logs\n\n"
                    "Bot is operational!"
                )
                send_telegram(response)
                
            elif text == "/restart":
                threading.Thread(target=restart_bot).start()
                send_telegram("🔄 Restart initiated...")
                
            elif text == "/ping":
                threading.Thread(
                    target=lambda: send_telegram(get_ping_stats())
                ).start()
                send_telegram("🏓 Running ping test...")
                
            elif text == "/status":
                send_telegram(get_system_status())
                
            elif text == "/logs":
                threading.Thread(
                    target=lambda: send_log_tail(15, "Recent Logs")
                ).start()
                send_telegram("📋 Fetching logs...")
                
            else:
                send_telegram("❌ Unknown command. Try /start for help.")
                
            return jsonify({"status": "processed"})
            
        except Exception as e:
            print(f"Webhook error: {e}")
            return jsonify({"status": "error", "details": str(e)})

    # Start Flask with better configuration
    app.run(
        host="0.0.0.0",
        port=APP_PORT,
        threaded=True,
        use_reloader=False
    )

def main():
    global current_process
    
    # Initial setup
    setup()
    
    # Start background services
    threading.Thread(target=monitor_uptime, daemon=True).start()
    threading.Thread(target=monitor_resources, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()
    
    send_telegram("⚡ Bot initialized successfully!")
    
    # Main loop
    while True:
        try:
            pull_latest()
            current_process = run_script()
            time.sleep(RESTART_INTERVAL)
            stop_script(current_process)
            send_telegram("⏰ Scheduled restart initiated")
            send_log_tail(15, "Pre-Restart Logs")
        except Exception as e:
            send_telegram(f"🔥 Critical error: {str(e)}")
            time.sleep(30)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        send_telegram("🛑 Bot stopped manually")
    except Exception as e:
        send_telegram(f"💥 Fatal error: {str(e)}")

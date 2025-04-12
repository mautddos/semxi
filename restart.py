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

app = Flask(__name__)
current_process = None
start_time = time.time()

def send_telegram(text, parse_mode="Markdown"):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": USER_ID, "text": text, "parse_mode": parse_mode}
        )
    except Exception as e:
        print(f"Telegram error: {e}")

def send_log_tail(lines=20, title="Latest Logs"):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()[-lines:]
            send_telegram(f"*{title}*\n```\n" + "".join(lines) + "\n```")
    else:
        send_telegram("No logs found.")

def get_system_status():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    uptime = int(time.time() - start_time)
    
    status_msg = (
        f"*System Status*\n"
        f"• CPU: {cpu}%\n"
        f"• RAM: {ram.used//1024//1024}MB/{ram.total//1024//1024}MB ({ram.percent}%)\n"
        f"• Disk: {disk.used//1024//1024}MB/{disk.total//1024//1024}MB ({disk.percent}%)\n"
        f"• Uptime: {uptime//3600}h {(uptime%3600)//60}m\n"
        f"• OS: {platform.system()} {platform.release()}"
    )
    return status_msg

def get_ping_stats():
    try:
        ping_result = subprocess.run(["ping", "-c", "4", "8.8.8.8"], capture_output=True, text=True)
        return f"*Ping Test*\n```\n{ping_result.stdout}\n```"
    except Exception as e:
        return f"Ping test failed: {str(e)}"

def setup():
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(FOLDER_NAME):
        subprocess.run(["git", "clone", REPO_URL], check=True)
        send_telegram("Repo cloned successfully.")
    else:
        send_telegram("Repo already exists.")

def pull_latest():
    subprocess.run(["git", "pull"], cwd=FOLDER_NAME, check=True)
    send_telegram("Pulled latest updates.")

def run_script():
    with open(LOG_FILE, "a") as logfile:
        logfile.write(f"\n[{datetime.now()}] Starting script...\n")
    return subprocess.Popen(
        ["python3", SCRIPT_NAME],
        cwd=FOLDER_NAME,
        stdout=open(LOG_FILE, "a"),
        stderr=subprocess.STDOUT
    )

def stop_script(process):
    if process and process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()

def monitor_uptime():
    while True:
        time.sleep(UPTIME_PING_INTERVAL)
        uptime = int((time.time() - start_time) / 60)
        send_telegram(f"Bot uptime: {uptime} minutes.")

def monitor_resources():
    while True:
        time.sleep(MONITOR_INTERVAL)
        ram = psutil.virtual_memory().used // (1024 * 1024)
        cpu = psutil.cpu_percent(interval=1)
        send_telegram(f"CPU: {cpu}% | RAM: {ram}MB")

def run_flask():
    @app.route(f"/{BOT_TOKEN}", methods=["POST"])
    def webhook():
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"status": "no message"})
            
        message = data["message"]
        text = message.get("text", "").strip()
        chat_id = str(message["chat"]["id"])
        
        if chat_id != USER_ID:
            return jsonify({"status": "unauthorized"})
            
        if text == "/start":
            send_telegram("Bot is running! Commands:\n"
                         "/status - System status\n"
                         "/restart - Restart bot\n"
                         "/ping - Network test\n"
                         "/logs - Show recent logs")
            
        elif text == "/restart":
            threading.Thread(target=restart_bot).start()
            send_telegram("Restart initiated...")
            
        elif text == "/ping":
            send_telegram(get_ping_stats())
            
        elif text == "/status":
            send_telegram(get_system_status())
            
        elif text == "/logs":
            send_log_tail()
            
        return jsonify({"status": "processed"})

    app.run(host="0.0.0.0", port=APP_PORT)

def restart_bot():
    global current_process
    stop_script(current_process)
    pull_latest()
    current_process = run_script()
    send_telegram("Bot restarted successfully.")
    send_log_tail(10, "Post-Restart Logs")

def main():
    global current_process
    setup()
    
    # Start background threads
    threading.Thread(target=monitor_uptime, daemon=True).start()
    threading.Thread(target=monitor_resources, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()
    
    send_telegram("Bot started successfully!")
    
    while True:
        try:
            pull_latest()
            current_process = run_script()
            time.sleep(RESTART_INTERVAL)
            stop_script(current_process)
            send_telegram("Regular restart after 45 minutes.")
            send_log_tail(15, "Pre-Restart Logs")
        except Exception as e:
            send_telegram(f"⚠️ Crash Detected: {str(e)}")
            send_log_tail(20, "Crash Logs")
            time.sleep(10)

if __name__ == "__main__":
    main()

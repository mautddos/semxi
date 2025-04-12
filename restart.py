import os
import subprocess
import time
import signal
import requests
import threading
from datetime import datetime
import psutil
from flask import Flask, request

REPO_URL = "https://github.com/mautddos/semxi.git"
FOLDER_NAME = "semxi"
SCRIPT_NAME = "xhamster.py"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "xhamster.log")
RESTART_INTERVAL = 45 * 60
UPTIME_PING_INTERVAL = 3600  # 1 hour
MONITOR_INTERVAL = 900  # 15 minutes

BOT_TOKEN = "7683433576:AAFGuDfoFo4Q6cvvlWBk9QTCGwPbAGRfX-k"
USER_ID = "8167507955"
APP_PORT = 8080  # Flask port

app = Flask(__name__)
current_process = None
start_time = time.time()

def send_telegram(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": USER_ID, "text": text}
        )
    except Exception as e:
        print(f"Telegram error: {e}")

def send_log_tail(title="Latest Logs"):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()[-20:]
            send_telegram(f"*{title}*\n" + "".join(lines[-20:]))
    else:
        send_telegram("No logs found.")

def setup():
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(FOLDER_NAME):
        subprocess.run(["git", "clone", REPO_URL])
        send_telegram("Repo cloned successfully.")
    else:
        send_telegram("Repo already exists.")

def pull_latest():
    subprocess.run(["git", "pull"], cwd=FOLDER_NAME)
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
        data = request.json
        if data and "message" in data:
            text = data["message"].get("text", "")
            chat_id = str(data["message"]["chat"]["id"])
            if chat_id == USER_ID:
                if text == "/restart":
                    send_telegram("Restarting now...")
                    restart_bot()
                elif text == "/logs":
                    send_log_tail("Log Snapshot")
        return {"ok": True}

    app.run(host="0.0.0.0", port=APP_PORT)

def restart_bot():
    global current_process
    stop_script(current_process)
    pull_latest()
    current_process = run_script()
    send_telegram("Bot restarted manually.")
    send_log_tail("Bot Restarted")

def main():
    global current_process
    setup()
    threading.Thread(target=monitor_uptime, daemon=True).start()
    threading.Thread(target=monitor_resources, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()

    while True:
        try:
            pull_latest()
            send_telegram("Starting bot script...")
            current_process = run_script()
            time.sleep(RESTART_INTERVAL)
            stop_script(current_process)
            send_telegram("Restarting bot after 45 minutes.")
            send_log_tail("Post-Restart Logs")
        except Exception as e:
            send_telegram(f"Crash Detected: {e}")
            send_log_tail("Crash Snapshot")
            time.sleep(10)

if __name__ == "__main__":
    main()

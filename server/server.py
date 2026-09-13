"""
ESP32 NFC Wi-Fi Music Player Server
=====================================
Receives NFC tag UIDs from ESP32 over Wi-Fi and plays mapped songs using pygame.
Features:
 - Dynamic hot-reloading of config.json (edit mappings without restarting server)
 - Visual web dashboard at http://localhost:5000
 - Instant feedback when an unknown card is tapped
 - Supports .mp3, .wav, .ogg, .flac audio formats
"""

import os
import sys
import json
import socket
import logging
from flask import Flask, request, jsonify, render_template_string

# Initialize pygame mixer
import pygame
try:
    pygame.mixer.init()
    print("[OK] Pygame audio mixer initialized.")
except Exception as e:
    print(f"[ERROR] Failed to initialize audio mixer: {e}")

# Import sample generator
from generate_samples import generate_all_samples

# Ensure sample sounds exist
generate_all_samples()

app = Flask(__name__)

# Suppress standard werkzeug access logs to keep terminal clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# State tracking
current_track = "None"
is_paused = False
recent_events = []

def get_local_ip():
    """Retrieve the primary local IP address of this computer."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def load_config():
    """Load tag mappings and settings from config.json."""
    if not os.path.exists(CONFIG_FILE):
        return {"settings": {"music_folder": "music", "default_volume": 0.8}, "tags": {}}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read {CONFIG_FILE}: {e}")
        return {"settings": {"music_folder": "music", "default_volume": 0.8}, "tags": {}}

# Initial volume setup
config = load_config()
default_volume = config.get("settings", {}).get("default_volume", 0.8)
pygame.mixer.music.set_volume(default_volume)

def play_audio_file(filename):
    """Play an audio file from the music folder."""
    global current_track, is_paused
    config = load_config()
    music_folder = config.get("settings", {}).get("music_folder", "music")
    
    # Resolve file path
    file_path = os.path.join(BASE_DIR, music_folder, filename)
    if not os.path.exists(file_path):
        # Also check direct path
        file_path = os.path.join(BASE_DIR, filename)

    if not os.path.exists(file_path):
        print(f"[ERROR] Audio file not found: {file_path}")
        return False, f"File not found: {filename}"

    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        current_track = filename
        is_paused = False
        print(f"[PLAYING] >>> {filename} <<<")
        return True, f"Playing: {filename}"
    except Exception as e:
        print(f"[ERROR] Playback failed: {e}")
        return False, str(e)

def handle_action(action):
    """Handle special tag actions like STOP, PAUSE, VOL_UP."""
    global current_track, is_paused
    action = action.upper().replace("ACTION:", "")
    
    if action == "STOP":
        pygame.mixer.music.stop()
        current_track = "Stopped"
        is_paused = False
        print("[ACTION] Playback STOPPED")
        return "Playback stopped"
        
    elif action in ("PAUSE_RESUME", "PAUSE", "TOGGLE"):
        if is_paused:
            pygame.mixer.music.unpause()
            is_paused = False
            print("[ACTION] Playback RESUMED")
            return "Playback resumed"
        else:
            pygame.mixer.music.pause()
            is_paused = True
            print("[ACTION] Playback PAUSED")
            return "Playback paused"
            
    elif action == "VOL_UP":
        vol = min(1.0, pygame.mixer.music.get_volume() + 0.1)
        pygame.mixer.music.set_volume(vol)
        print(f"[ACTION] Volume increased to {int(vol*100)}%")
        return f"Volume {int(vol*100)}%"
        
    elif action == "VOL_DOWN":
        vol = max(0.0, pygame.mixer.music.get_volume() - 0.1)
        pygame.mixer.music.set_volume(vol)
        print(f"[ACTION] Volume decreased to {int(vol*100)}%")
        return f"Volume {int(vol*100)}%"
        
    return f"Unknown action: {action}"

@app.route("/tag", methods=["POST", "GET"])
def receive_tag():
    """Endpoint called by ESP32 when an NFC card is scanned."""
    global recent_events
    
    # Extract UID from JSON payload or query param
    uid = None
    if request.is_json:
        data = request.get_json()
        uid = data.get("uid") or data.get("tag") or data.get("id")
    elif request.form:
        uid = request.form.get("uid") or request.form.get("tag")
    elif request.args:
        uid = request.args.get("uid") or request.args.get("tag")
    
    # Fallback to raw text if present
    if not uid and request.data:
        try:
            uid = request.data.decode("utf-8").strip()
        except Exception:
            pass

    if not uid:
        return jsonify({"status": "error", "message": "Missing 'uid' in request"}), 400

    # Normalize UID
    uid = uid.replace(":", "").replace(" ", "").upper()
    
    print("\n" + "="*50)
    print(f" [CARD SCANNED] UID: {uid}")
    print("="*50)

    # Reload config to get real-time mapping updates
    config = load_config()
    tags = config.get("tags", {})
    
    response_msg = ""
    status = "ok"

    if uid in tags:
        target = tags[uid]
        if target.startswith("ACTION:"):
            response_msg = handle_action(target)
        else:
            success, response_msg = play_audio_file(target)
            if not success:
                status = "error"
    else:
        # Unknown card detected
        print(f"[!] NEW / UNMAPPED CARD DETECTED: {uid}")
        print(f"    -> To assign a song, add this line in config.json:")
        print(f'       "{uid}": "your_song.mp3"')
        print("="*50)
        
        # Play sample fallback beep if available
        play_audio_file("song1.wav")
        response_msg = f"New card detected: {uid} (add to config.json to customize)"

    # Record event for the web dashboard
    event_entry = {
        "uid": uid,
        "action": tags.get(uid, "Unmapped Card"),
        "result": response_msg
    }
    recent_events.insert(0, event_entry)
    if len(recent_events) > 20:
        recent_events.pop()

    return jsonify({
        "status": status,
        "uid": uid,
        "mapped_target": tags.get(uid, None),
        "message": response_msg,
        "current_track": current_track
    })

@app.route("/control/<action>", methods=["POST", "GET"])
def web_control(action):
    """Control playback manually via web interface."""
    msg = handle_action(action)
    return jsonify({"status": "ok", "message": msg, "current_track": current_track})

@app.route("/play/<filename>", methods=["POST", "GET"])
def web_play(filename):
    """Play a specific song manually via web interface."""
    success, msg = play_audio_file(filename)
    return jsonify({"status": "ok" if success else "error", "message": msg})

@app.route("/status", methods=["GET"])
def get_status():
    """Return JSON status of the server."""
    config = load_config()
    return jsonify({
        "current_track": current_track,
        "is_paused": is_paused,
        "volume": int(pygame.mixer.music.get_volume() * 100),
        "mapped_tags": config.get("tags", {}),
        "recent_events": recent_events
    })

@app.route("/", methods=["GET"])
def dashboard():
    """Web Dashboard showing live status and card mappings."""
    config = load_config()
    tags = config.get("tags", {})
    music_dir = os.path.join(BASE_DIR, config.get("settings", {}).get("music_folder", "music"))
    audio_files = []
    if os.path.exists(music_dir):
        audio_files = [f for f in os.listdir(music_dir) if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac'))]

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ESP32 NFC Music Player Dashboard</title>
        <style>
            * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            body { background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
            .container { max-width: 900px; margin: auto; }
            .header { text-align: center; margin-bottom: 25px; }
            .header h1 { margin: 0; color: #38bdf8; font-size: 28px; }
            .header p { color: #94a3b8; margin-top: 5px; }
            .card { background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); border: 1px solid #334155; }
            .card h2 { margin-top: 0; color: #f1f5f9; font-size: 18px; border-bottom: 1px solid #334155; padding-bottom: 10px; }
            .now-playing { display: flex; align-items: center; justify-content: space-between; background: #0284c7; padding: 15px 20px; border-radius: 8px; color: white; font-weight: bold; }
            .btn { background: #334155; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; margin-right: 8px; transition: 0.2s; }
            .btn:hover { background: #475569; }
            .btn-danger { background: #ef4444; }
            .btn-danger:hover { background: #dc2626; }
            .btn-primary { background: #0284c7; }
            .btn-primary:hover { background: #0369a1; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 14px; }
            th { color: #94a3b8; font-weight: 600; }
            .tag-badge { background: #38bdf8; color: #0f172a; padding: 2px 8px; border-radius: 4px; font-family: monospace; font-weight: bold; }
            .log-box { max-height: 200px; overflow-y: auto; background: #0b1329; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; color: #a5f3fc; }
        </style>
        <script>
            function callApi(endpoint) {
                fetch(endpoint, {method: 'POST'}).then(() => location.reload());
            }
            // Auto refresh every 3 seconds to show live scans
            setInterval(() => {
                fetch('/status')
                    .then(res => res.json())
                    .then(data => {
                        document.getElementById('track-name').innerText = data.current_track;
                    });
            }, 3000);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎵 ESP32 NFC Wi-Fi Music Player</h1>
                <p>Server running on <strong>http://{{ local_ip }}:5000</strong></p>
            </div>

            <div class="card">
                <h2>Current Status & Controls</h2>
                <div class="now-playing">
                    <div>Status: <span id="track-name">{{ current_track }}</span></div>
                    <div>
                        <button class="btn btn-primary" onclick="callApi('/control/pause_resume')">⏯ Play / Pause</button>
                        <button class="btn btn-danger" onclick="callApi('/control/stop')">⏹ Stop</button>
                        <button class="btn" onclick="callApi('/control/vol_down')">🔉 -</button>
                        <button class="btn" onclick="callApi('/control/vol_up')">🔊 +</button>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>Configured NFC Tags (config.json)</h2>
                <table>
                    <thead>
                        <tr><th>Card UID</th><th>Mapped Song / Action</th><th>Test</th></tr>
                    </thead>
                    <tbody>
                        {% for uid, target in tags.items() %}
                        <tr>
                            <td><span class="tag-badge">{{ uid }}</span></td>
                            <td>{{ target }}</td>
                            <td>
                                {% if target.startswith('ACTION:') %}
                                <button class="btn" onclick="callApi('/control/{{ target[7:].lower() }}')">Trigger</button>
                                {% else %}
                                <button class="btn btn-primary" onclick="callApi('/play/{{ target }}')">▶ Play</button>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h2>Available Audio Files in <code>music/</code></h2>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    {% for audio in audio_files %}
                    <button class="btn" onclick="callApi('/play/{{ audio }}')">🎵 {{ audio }}</button>
                    {% endfor %}
                </div>
            </div>

            <div class="card">
                <h2>Live Scan History</h2>
                <div class="log-box">
                    {% for event in recent_events %}
                    <div>[UID: <b>{{ event.uid }}</b>] ➔ {{ event.action }} ({{ event.result }})</div>
                    {% else %}
                    <div>No cards scanned yet. Tap a card on the ESP32 reader!</div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    local_ip = get_local_ip()
    return render_template_string(
        html,
        current_track=current_track,
        tags=tags,
        audio_files=audio_files,
        recent_events=recent_events,
        local_ip=local_ip
    )

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("\n" + "="*60)
    print("      ESP32 NFC WI-FI MUSIC SERVER IS ONLINE!       ")
    print("="*60)
    print(f" >> LOCAL IP ADDRESS : {local_ip}")
    print(f" >> ESP32 TARGET URL : http://{local_ip}:5000/tag")
    print(f" >> WEB DASHBOARD    : http://localhost:5000 or http://{local_ip}:5000")
    print("="*60)
    print(" * Set this in your ESP32 Arduino code:")
    print(f'   const char* SERVER_IP = "{local_ip}";')
    print("="*60 + "\n")
    
    app.run(host="0.0.0.0", port=5000, debug=False)

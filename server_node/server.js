/**
 * ESP32 NFC Wi-Fi Music Player Server (Node.js)
 * ===============================================
 * Receives NFC tag UIDs from ESP32 over Wi-Fi and plays mapped audio tracks.
 */

const express = require('express');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn, exec } = require('child_process');

const app = express();
const PORT = process.env.PORT || 5000;
const BASE_DIR = __dirname;
const CONFIG_FILE = path.join(BASE_DIR, 'config.json');

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.text({ type: '*/*' }));

// State tracking
let currentTrack = "None";
let recentEvents = [];
let currentPlaybackProcess = null;

// Get local network IPv4 address
function getLocalIP() {
    const interfaces = os.networkInterfaces();
    for (const name of Object.keys(interfaces)) {
        for (const net of interfaces[name]) {
            if (net.family === 'IPv4' && !net.internal) {
                return net.address;
            }
        }
    }
    return '127.0.0.1';
}

// Load config dynamically
function loadConfig() {
    try {
        if (fs.existsSync(CONFIG_FILE)) {
            const raw = fs.readFileSync(CONFIG_FILE, 'utf-8');
            return JSON.parse(raw);
        }
    } catch (e) {
        console.error(`[ERROR] Failed to load ${CONFIG_FILE}:`, e.message);
    }
    return { settings: { music_folder: 'music', default_volume: 0.8 }, tags: {} };
}

// Stop any currently playing audio
function stopCurrentAudio() {
    if (currentPlaybackProcess) {
        try {
            if (process.platform === 'win32') {
                exec(`taskkill /pid ${currentPlaybackProcess.pid} /f /t`, () => {});
            } else {
                currentPlaybackProcess.kill();
            }
        } catch (e) {
            // Ignore error if process already terminated
        }
        currentPlaybackProcess = null;
    }
    currentTrack = "Stopped";
}

// Play audio file on Windows / Mac / Linux
function playAudioFile(filename) {
    const config = loadConfig();
    const musicFolder = (config.settings && config.settings.music_folder) || 'music';
    
    let filePath = path.join(BASE_DIR, musicFolder, filename);
    if (!fs.existsSync(filePath)) {
        filePath = path.join(BASE_DIR, filename);
    }

    if (!fs.existsSync(filePath)) {
        console.error(`[ERROR] Audio file not found: ${filePath}`);
        return { success: false, message: `File not found: ${filename}` };
    }

    stopCurrentAudio();

    try {
        if (process.platform === 'win32') {
            // Use PowerShell to play .mp3 / .wav reliably in the background
            const absPath = path.resolve(filePath).replace(/'/g, "''");
            const psScript = `
                Add-Type -AssemblyName presentationCore;
                $player = New-Object System.Windows.Media.MediaPlayer;
                $player.Open([System.Uri]'${absPath}');
                $player.Play();
                Start-Sleep -Seconds 300;
            `;
            currentPlaybackProcess = spawn('powershell', ['-NoProfile', '-NonInteractive', '-Command', psScript], {
                windowsHide: true,
                detached: false
            });
        } else if (process.platform === 'darwin') {
            currentPlaybackProcess = spawn('afplay', [filePath]);
        } else {
            currentPlaybackProcess = spawn('aplay', [filePath]);
        }

        currentTrack = filename;
        console.log(`[PLAYING] >>> ${filename} <<<`);
        return { success: true, message: `Playing: ${filename}` };
    } catch (err) {
        console.error(`[ERROR] Playback failed:`, err.message);
        return { success: false, message: err.message };
    }
}

// Handle special action tags
function handleAction(action) {
    const act = action.toUpperCase().replace('ACTION:', '');
    if (act === 'STOP') {
        stopCurrentAudio();
        console.log(`[ACTION] Playback STOPPED`);
        return 'Playback stopped';
    }
    return `Unknown action: ${action}`;
}

// ================= API ROUTES =================

// Endpoint for ESP32
app.all('/tag', (req, res) => {
    let uid = null;

    if (req.body && typeof req.body === 'object') {
        uid = req.body.uid || req.body.tag || req.body.id;
    } else if (typeof req.body === 'string' && req.body.trim()) {
        try {
            const parsed = JSON.parse(req.body);
            uid = parsed.uid || parsed.tag;
        } catch {
            uid = req.body.trim();
        }
    }

    if (!uid && req.query) {
        uid = req.query.uid || req.query.tag;
    }

    if (!uid) {
        return res.status(400).json({ status: 'error', message: "Missing 'uid' in request" });
    }

    // Normalize UID (uppercase, no spaces/colons)
    uid = uid.replace(/[: ]/g, '').toUpperCase();

    console.log('\n' + '='.repeat(50));
    console.log(` [CARD SCANNED] UID: ${uid}`);
    console.log('='.repeat(50));

    const config = loadConfig();
    const tags = config.tags || {};
    let responseMsg = '';
    let status = 'ok';

    if (tags[uid]) {
        const target = tags[uid];
        if (target.startsWith('ACTION:')) {
            responseMsg = handleAction(target);
        } else {
            const result = playAudioFile(target);
            responseMsg = result.message;
            if (!result.success) status = 'error';
        }
    } else {
        console.log(`[!] NEW / UNMAPPED CARD DETECTED: ${uid}`);
        console.log(`    -> To assign a song, add this line in config.json:`);
        console.log(`       "${uid}": "song1.wav"`);
        console.log('='.repeat(50));

        playAudioFile('song1.wav');
        responseMsg = `New card detected: ${uid} (added sample playback)`;
    }

    // Record scan history
    recentEvents.unshift({
        uid,
        action: tags[uid] || 'Unmapped Card',
        result: responseMsg,
        time: new Date().toLocaleTimeString()
    });
    if (recentEvents.length > 20) recentEvents.pop();

    return res.json({
        status,
        uid,
        mapped_target: tags[uid] || null,
        message: responseMsg,
        current_track: currentTrack
    });
});

// Manual web controls
app.all('/control/:action', (req, res) => {
    const msg = handleAction(req.params.action);
    res.json({ status: 'ok', message: msg, current_track: currentTrack });
});

app.all('/play/:filename', (req, res) => {
    const result = playAudioFile(req.params.filename);
    res.json({ status: result.success ? 'ok' : 'error', message: result.message });
});

app.get('/status', (req, res) => {
    const config = loadConfig();
    res.json({
        current_track: currentTrack,
        mapped_tags: config.tags || {},
        recent_events: recentEvents
    });
});

// Web Dashboard
app.get('/', (req, res) => {
    const config = loadConfig();
    const tags = config.tags || {};
    const musicDir = path.join(BASE_DIR, (config.settings && config.settings.music_folder) || 'music');
    let audioFiles = [];
    if (fs.existsSync(musicDir)) {
        audioFiles = fs.readdirSync(musicDir).filter(f => /\.(mp3|wav|ogg|flac)$/i.test(f));
    }

    const localIP = getLocalIP();

    const tagRows = Object.entries(tags).map(([uid, target]) => `
        <tr>
            <td><span class="tag-badge">${uid}</span></td>
            <td>${target}</td>
            <td>
                ${target.startsWith('ACTION:') 
                    ? `<button class="btn" onclick="callApi('/control/${target.replace('ACTION:', '').toLowerCase()}')">Trigger</button>`
                    : `<button class="btn btn-primary" onclick="callApi('/play/${target}')">▶ Play</button>`}
            </td>
        </tr>
    `).join('');

    const musicButtons = audioFiles.map(f => `
        <button class="btn" onclick="callApi('/play/${f}')">🎵 ${f}</button>
    `).join('');

    const eventRows = recentEvents.length > 0 
        ? recentEvents.map(e => `<div>[${e.time}] [UID: <b>${e.uid}</b>] ➔ ${e.action} (${e.result})</div>`).join('')
        : `<div>No cards scanned yet. Tap an NFC card on your ESP32!</div>`;

    const html = `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ESP32 NFC Music Player (Node.js)</title>
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
                <h1>⚡ ESP32 NFC Music Player (Node.js Server)</h1>
                <p>Running on <strong>http://${localIP}:${PORT}</strong></p>
            </div>

            <div class="card">
                <h2>Playback Controls</h2>
                <div class="now-playing">
                    <div>Status: <span id="track-name">${currentTrack}</span></div>
                    <div>
                        <button class="btn btn-danger" onclick="callApi('/control/stop')">⏹ Stop Playback</button>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>Configured NFC Tags (config.json)</h2>
                <table>
                    <thead>
                        <tr><th>Card UID</th><th>Mapped Target</th><th>Action</th></tr>
                    </thead>
                    <tbody>${tagRows}</tbody>
                </table>
            </div>

            <div class="card">
                <h2>Available Music in <code>music/</code></h2>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">${musicButtons}</div>
            </div>

            <div class="card">
                <h2>Live Scan History</h2>
                <div class="log-box">${eventRows}</div>
            </div>
        </div>
    </body>
    </html>
    `;
    res.send(html);
});

// Start listening
app.listen(PORT, '0.0.0.0', () => {
    const localIP = getLocalIP();
    console.log('\n' + '='.repeat(60));
    console.log('   NODE.JS ESP32 NFC WI-FI MUSIC SERVER ONLINE!    ');
    console.log('='.repeat(60));
    console.log(` >> LOCAL IP ADDRESS : ${localIP}`);
    console.log(` >> ESP32 TARGET URL : http://${localIP}:${PORT}/tag`);
    console.log(` >> WEB DASHBOARD    : http://localhost:${PORT} or http://${localIP}:${PORT}`);
    console.log('='.repeat(60));
    console.log(' * Set this in your ESP32 Arduino code:');
    console.log(`   const char* SERVER_IP = "${localIP}";`);
    console.log('='.repeat(60) + '\n');
});

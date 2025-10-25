from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
from datetime import datetime
import os
import subprocess

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=10_000_000
)

frame_count = 0

# HTML template for iPhone (sender)
SENDER_HTML = '''
<!DOCTYPE html>
<html>
<head>
  <title>iPhone Camera Sender</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
  <style>
    body { font-family: Arial; margin: 20px; text-align: center; }
    video { max-width: 100%; border: 2px solid #333; }
    button { padding: 15px 30px; font-size: 18px; margin: 10px; }
    #status { margin: 20px; font-weight: bold; }
    .settings { margin: 20px; }
    select, input { padding: 8px; margin: 5px; font-size: 14px; }
  </style>
</head>
<body>
  <h1>iPhone Camera Sender</h1>
  <video id="video" autoplay playsinline muted></video>
  <br>
  <div class="settings">
    <label>Quality: 
      <select id="quality">
        <option value="0.5">Low (faster)</option>
        <option value="0.6" selected>Medium</option>
        <option value="0.75">High</option>
        <option value="0.9">Very High</option>
      </select>
    </label>
    <label>FPS: 
      <select id="fps">
        <option value="10">10</option>
        <option value="15" selected>15</option>
        <option value="20">20</option>
        <option value="30">30</option>
      </select>
    </label>
  </div>
  <button id="startBtn">Start Streaming</button>
  <button id="stopBtn" disabled>Stop Streaming</button>
  <div id="status">Ready</div>
  <canvas id="canvas" style="display:none;"></canvas>

  <script>
    const socket = io();
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    const statusEl = document.getElementById('status');
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const qualitySelect = document.getElementById('quality');
    const fpsSelect = document.getElementById('fps');

    let streaming = false;
    let intervalId = null;
    const TARGET_WIDTH = 640;

    function stopStream() {
      streaming = false;
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
      const stream = video.srcObject;
      if (stream) {
        stream.getTracks().forEach(t => t.stop());
      }
      video.srcObject = null;
      startBtn.disabled = false;
      stopBtn.disabled = true;
      qualitySelect.disabled = false;
      fpsSelect.disabled = false;
      statusEl.textContent = 'Stopped';
    }

    startBtn.onclick = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'environment',
            width: { ideal: 1280 },
            height: { ideal: 720 },
            frameRate: { ideal: 30 }
          },
          audio: false
        });
        video.srcObject = stream;

        await new Promise(res => {
          if (video.readyState >= 2) return res();
          video.onloadedmetadata = () => res();
        });

        const vw = video.videoWidth || 1280;
        const vh = video.videoHeight || 720;
        const scale = TARGET_WIDTH / vw;
        const targetW = Math.round(vw * scale);
        const targetH = Math.round(vh * scale);

        canvas.width = targetW;
        canvas.height = targetH;

        startBtn.disabled = true;
        stopBtn.disabled = false;
        qualitySelect.disabled = true;
        fpsSelect.disabled = true;
        statusEl.textContent = 'Streaming...';
        streaming = true;

        const targetFPS = parseInt(fpsSelect.value);
        const quality = parseFloat(qualitySelect.value);
        const intervalMs = Math.round(1000 / targetFPS);

        intervalId = setInterval(() => {
          if (!streaming) return;
          ctx.drawImage(video, 0, 0, targetW, targetH);
          canvas.toBlob(async (blob) => {
            if (!blob) return;
            const buf = await blob.arrayBuffer();
            socket.emit('frame_bin', buf);
          }, 'image/jpeg', quality);
        }, intervalMs);

      } catch (err) {
        statusEl.textContent = 'Error: ' + err.message;
        console.error(err);
      }
    };

    stopBtn.onclick = () => stopStream();

    socket.on('connect', () => {
      console.log('Connected to server');
      statusEl.textContent = 'Connected - Ready to stream';
    });
    socket.on('disconnect', () => {
      console.log('Disconnected from server');
      stopStream();
      statusEl.textContent = 'Disconnected';
    });
  </script>
</body>
</html>
'''

# HTML template for MacBook (receiver)
RECEIVER_HTML = '''
<!DOCTYPE html>
<html>
<head>
  <title>MacBook Camera Receiver</title>
  <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
  <style>
    body { 
      font-family: Arial; 
      margin: 20px; 
      text-align: center; 
      background: #1a1a1a;
      color: #fff;
    }
    .container { 
      display: flex; 
      justify-content: center; 
      gap: 20px; 
      flex-wrap: wrap;
      max-width: 1800px;
      margin: 0 auto;
    }
    .view { 
      text-align: center; 
      flex: 1;
      min-width: 300px;
    }
    canvas { 
      width: 100%; 
      max-width: 800px;
      border: 3px solid #333; 
      background: #000;
      display: block;
      margin: 0 auto;
    }
    #status { 
      margin: 20px; 
      font-size: 18px; 
      font-weight: bold;
      color: #4CAF50;
    }
    .info { 
      margin: 10px; 
      color: #888;
      font-size: 14px;
    }
    .controls { 
      margin: 20px;
      padding: 20px;
      background: #2a2a2a;
      border-radius: 8px;
      display: inline-block;
    }
    button { 
      padding: 12px 24px; 
      margin: 5px; 
      font-size: 16px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.3s;
    }
    button:hover { opacity: 0.8; }
    label { 
      margin: 0 15px;
      display: inline-block;
    }
    input[type="range"] {
      width: 150px;
      vertical-align: middle;
    }
    h1 { color: #fff; }
    h3 { 
      color: #4CAF50;
      margin-top: 0;
    }
    .metric {
      display: inline-block;
      margin: 0 15px;
      padding: 8px 16px;
      background: #333;
      border-radius: 4px;
    }
  </style>
</head>
<body>
  <h1>📹 Live Camera Feed with Handwriting Detection</h1>
  <div id="status">Waiting for stream...</div>
  <div class="info">
    <span class="metric">Frames: <span id="frameCount">0</span></span>
    <span class="metric">FPS: <span id="fps">0</span></span>
    <span class="metric">Latency: <span id="latency">-</span>ms</span>
  </div>

  <div class="controls">
    <button id="toggleDetection">🎯 Enable Detection</button>
    <label>
      Sensitivity: 
      <input type="range" id="sensitivity" min="5" max="50" value="18">
      <span id="sensitivityValue">18</span>
    </label>
    <label>
      Smoothing: 
      <input type="range" id="smoothing" min="50" max="95" value="85">
      <span id="smoothingValue">0.85</span>
    </label>
  </div>

  <div class="container">
    <div class="view">
      <h3>Original Feed</h3>
      <canvas id="originalCanvas"></canvas>
    </div>
    <div class="view">
      <h3>Handwriting Detection</h3>
      <canvas id="detectionCanvas"></canvas>
    </div>
  </div>

  <script>
    const socket = io();
    const originalCanvas = document.getElementById('originalCanvas');
    const detectionCanvas = document.getElementById('detectionCanvas');
    const originalCtx = originalCanvas.getContext('2d', { willReadFrequently: true });
    const detectionCtx = detectionCanvas.getContext('2d', { willReadFrequently: true });

    const statusEl = document.getElementById('status');
    const frameCountEl = document.getElementById('frameCount');
    const fpsEl = document.getElementById('fps');
    const latencyEl = document.getElementById('latency');
    const toggleBtn = document.getElementById('toggleDetection');
    const sensitivitySlider = document.getElementById('sensitivity');
    const sensitivityValue = document.getElementById('sensitivityValue');
    const smoothingSlider = document.getElementById('smoothing');
    const smoothingValue = document.getElementById('smoothingValue');

    let count = 0;
    let detectionEnabled = false;
    let previousFrame = null;
    let sensitivity = 18;
    let DECAY = 0.85;

    let accum = null;
    let currentURL = null;

    // FPS calculation
    let fpsFrames = 0;
    let fpsLastTime = Date.now();
    setInterval(() => {
      const now = Date.now();
      const elapsed = (now - fpsLastTime) / 1000;
      const currentFps = Math.round(fpsFrames / elapsed);
      fpsEl.textContent = currentFps;
      fpsFrames = 0;
      fpsLastTime = now;
    }, 1000);

    toggleBtn.onclick = () => {
      detectionEnabled = !detectionEnabled;
      toggleBtn.textContent = detectionEnabled ? '⏸️ Disable Detection' : '🎯 Enable Detection';
      toggleBtn.style.background = detectionEnabled ? '#4CAF50' : '#666';
      toggleBtn.style.color = 'white';
      if (!detectionEnabled) {
        detectionCtx.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);
        previousFrame = null;
        accum = null;
      }
    };

    sensitivitySlider.oninput = (e) => {
      sensitivity = parseInt(e.target.value, 10);
      sensitivityValue.textContent = sensitivity;
    };

    smoothingSlider.oninput = (e) => {
      DECAY = parseInt(e.target.value, 10) / 100;
      smoothingValue.textContent = DECAY.toFixed(2);
    };

    function ensureCanvasSize(w, h) {
      if (originalCanvas.width !== w || originalCanvas.height !== h) {
        originalCanvas.width = w;
        originalCanvas.height = h;
      }
      if (detectionCanvas.width !== w || detectionCanvas.height !== h) {
        detectionCanvas.width = w;
        detectionCanvas.height = h;
      }
    }

    function detectHandwriting(currentImageData, previousImageData) {
      const data = currentImageData.data;
      const prev = previousImageData.data;
      const width = currentImageData.width;
      const height = currentImageData.height;
      const N = width * height;

      if (!accum || accum.length !== N) {
        accum = new Float32Array(N);
      }

      const motion = new Uint8ClampedArray(N);

      // Grayscale diff with slight adaptive threshold
      for (let i = 0, p = 0; i < N; i++, p += 4) {
        const g  = (data[p] + data[p+1] + data[p+2]) / 3;
        const gp = (prev[p] + prev[p+1] + prev[p+2]) / 3;
        const diff = Math.abs(g - gp);
        motion[i] = diff > sensitivity ? 255 : 0;
      }

      // 3x3 dilation
      const dilated = new Uint8ClampedArray(N);
      for (let y = 1; y < height - 1; y++) {
        for (let x = 1; x < width - 1; x++) {
          let maxv = 0;
          const idx = y * width + x;
          const w0 = (y-1)*width;
          const w1 = y*width;
          const w2 = (y+1)*width;
          maxv |= motion[w0 + (x-1)];
          maxv |= motion[w0 + x];
          maxv |= motion[w0 + (x+1)];
          maxv |= motion[w1 + (x-1)];
          maxv |= motion[w1 + x];
          maxv |= motion[w1 + (x+1)];
          maxv |= motion[w2 + (x-1)];
          maxv |= motion[w2 + x];
          maxv |= motion[w2 + (x+1)];
          dilated[idx] = maxv ? 255 : 0;
        }
      }

      // Temporal smoothing
      for (let i = 0; i < N; i++) {
        const impulse = dilated[i] ? 1.0 : 0.0;
        accum[i] = DECAY * accum[i] + (1.0 - DECAY) * impulse;
      }

      // Create overlay with gradient coloring
      const out = detectionCtx.createImageData(width, height);
      for (let i = 0, p = 0; i < N; i++, p += 4) {
        const strength = accum[i];
        if (strength > 0.15) {
          // Color-coded by intensity: cyan -> yellow -> red
          const t = Math.min(1, strength * 1.5);
          if (t < 0.5) {
            // cyan to yellow
            const s = t * 2;
            out.data[p]   = Math.round(255 * s);
            out.data[p+1] = 255;
            out.data[p+2] = Math.round(255 * (1-s));
          } else {
            // yellow to red
            const s = (t - 0.5) * 2;
            out.data[p]   = 255;
            out.data[p+1] = Math.round(255 * (1-s));
            out.data[p+2] = 0;
          }
          out.data[p+3] = Math.round(200 * Math.min(1, strength * 2));
        } else {
          // Dim background
          out.data[p]   = data[p] * 0.25;
          out.data[p+1] = data[p+1] * 0.25;
          out.data[p+2] = data[p+2] * 0.25;
          out.data[p+3] = 255;
        }
      }

      return out;
    }

    let lastFrameTime = Date.now();

    function drawAndDetectFromBlob(blob) {
      if (currentURL) URL.revokeObjectURL(currentURL);
      currentURL = URL.createObjectURL(blob);

      const img = new Image();
      img.onload = () => {
        const now = Date.now();
        latencyEl.textContent = now - lastFrameTime;
        lastFrameTime = now;

        ensureCanvasSize(img.width, img.height);
        originalCtx.drawImage(img, 0, 0);

        if (detectionEnabled) {
          const currentFrame = originalCtx.getImageData(0, 0, img.width, img.height);
          if (previousFrame &&
              previousFrame.width === img.width &&
              previousFrame.height === img.height) {
            const overlay = detectHandwriting(currentFrame, previousFrame);
            detectionCtx.putImageData(overlay, 0, 0);
          } else {
            detectionCtx.drawImage(img, 0, 0);
            detectionCtx.fillStyle = 'rgba(0,0,0,0.6)';
            detectionCtx.fillRect(0, 0, detectionCanvas.width, detectionCanvas.height);
          }
          previousFrame = currentFrame;
        }

        URL.revokeObjectURL(currentURL);
        currentURL = null;
      };
      img.src = currentURL;
    }

    socket.on('video_frame_bin', (arrayBuffer) => {
      const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
      drawAndDetectFromBlob(blob);
      count++;
      fpsFrames++;
      frameCountEl.textContent = count;
      statusEl.textContent = '🟢 Receiving stream...';
    });

    socket.on('connect', () => {
      statusEl.textContent = '🟢 Connected to server';
    });
    socket.on('disconnect', () => {
      statusEl.textContent = '🔴 Disconnected from server';
    });
  </script>
</body>
</html>
'''

@app.route('/')
def index():
    return '''
    <html>
      <head><title>Camera Stream Server</title></head>
      <body style="font-family: Arial; margin: 50px; background: #1a1a1a; color: #fff;">
        <h1>📹 iPhone to MacBook Camera Stream</h1>
        <h2>Instructions:</h2>
        <ol>
          <li>On your iPhone, visit: <strong>/sender</strong></li>
          <li>On your MacBook, visit: <strong>/receiver</strong></li>
          <li>Start streaming from your iPhone</li>
        </ol>
        <p><a href="/sender" style="color: #4CAF50;">Go to Sender (iPhone)</a></p>
        <p><a href="/receiver" style="color: #4CAF50;">Go to Receiver (MacBook)</a></p>
      </body>
    </html>
    '''

@app.route('/sender')
def sender():
    return render_template_string(SENDER_HTML)

@app.route('/receiver')
def receiver():
    return render_template_string(RECEIVER_HTML)

@socketio.on('frame_bin')
def handle_frame_bin(data):
    global frame_count
    frame_count += 1
    emit('video_frame_bin', data, broadcast=True, include_self=False)

    if frame_count % 100 == 0:
        print(f"Processed {frame_count} frames at {datetime.now()}")

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {datetime.now()}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {datetime.now()}")

if __name__ == '__main__':
    print("=" * 50)
    print("Camera Stream Server Starting")
    print("=" * 50)
    print("\nMake sure both devices are on the same network!")

    cert_file = 'cert.pem'
    key_file = 'key.pem'

    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        print("\nGenerating self-signed certificate...")
        try:
            subprocess.run([
                'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
                '-nodes', '-out', cert_file, '-keyout', key_file,
                '-days', '365', '-subj', '/CN=localhost'
            ], check=True)
            print("Certificate generated!")
        except Exception as e:
            print("Failed to generate certificate. Install openssl or provide cert/key.")
            raise e

    print("\nTo access from iPhone:")
    print("1) Find your Mac's IP (System Settings → Network)")
    print("2) On iPhone, visit: https://YOUR_MAC_IP:5001/sender")
    print("3) Trust the certificate")
    print("4) On MacBook, visit: https://localhost:5001/receiver")
    print("=" * 50)

    socketio.run(
        app,
        host='0.0.0.0',
        port=5001,
        debug=True,
        allow_unsafe_werkzeug=True,
        ssl_context=(cert_file, key_file)
    )
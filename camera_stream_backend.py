from flask import Flask, render_template_string, Response
from flask_socketio import SocketIO, emit
import base64
import cv2
import numpy as np
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, 
                    cors_allowed_origins="*", 
                    max_size=10000000,
                    async_mode='threading',
                    ping_timeout=60,
                    ping_interval=25)

# Store the latest frame
latest_frame = None
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
    </style>
</head>
<body>
    <h1>iPhone Camera Sender</h1>
    <video id="video" autoplay playsinline></video>
    <br>
    <button id="startBtn">Start Streaming</button>
    <button id="stopBtn" disabled>Stop Streaming</button>
    <div id="status">Ready</div>
    <canvas id="canvas" style="display:none;"></canvas>

    <script>
        const socket = io();
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const status = document.getElementById('status');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        let streaming = false;
        let intervalId = null;

        startBtn.onclick = async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        facingMode: 'environment', 
                        width: { ideal: 1280 },
                        height: { ideal: 720 },
                        frameRate: { ideal: 30 }
                    } 
                });
                video.srcObject = stream;
                startBtn.disabled = true;
                stopBtn.disabled = false;
                status.textContent = 'Streaming...';
                
                // Start sending frames
                intervalId = setInterval(() => {
                    if (streaming) {
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        ctx.drawImage(video, 0, 0);
                        const frame = canvas.toDataURL('image/jpeg', 0.8);
                        socket.emit('frame', { data: frame });
                    }
                }, 33); // Send ~30 frames per second
                
                streaming = true;
            } catch (err) {
                status.textContent = 'Error: ' + err.message;
            }
        };

        stopBtn.onclick = () => {
            streaming = false;
            if (intervalId) clearInterval(intervalId);
            const stream = video.srcObject;
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
            video.srcObject = null;
            startBtn.disabled = false;
            stopBtn.disabled = true;
            status.textContent = 'Stopped';
        };

        socket.on('connect', () => {
            console.log('Connected to server');
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
        body { font-family: Arial; margin: 20px; text-align: center; background: #f0f0f0; }
        .container { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; }
        .view { text-align: center; }
        canvas, img { max-width: 45vw; border: 3px solid #333; background: white; }
        #status { margin: 20px; font-size: 18px; font-weight: bold; }
        .info { margin: 10px; color: #666; }
        .controls { margin: 20px; }
        button { padding: 10px 20px; margin: 5px; font-size: 16px; }
        label { margin: 0 10px; }
    </style>
</head>
<body>
    <h1>MacBook Camera Receiver with Handwriting Detection</h1>
    <div id="status">Waiting for stream...</div>
    <div class="info">Frames received: <span id="frameCount">0</span></div>
    
    <div class="controls">
        <button id="toggleDetection">Enable Detection</button>
        <label>Sensitivity: <input type="range" id="sensitivity" min="5" max="50" value="20"></label>
        <span id="sensitivityValue">20</span>
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
        const originalCtx = originalCanvas.getContext('2d');
        const detectionCtx = detectionCanvas.getContext('2d');
        const status = document.getElementById('status');
        const frameCount = document.getElementById('frameCount');
        const toggleBtn = document.getElementById('toggleDetection');
        const sensitivitySlider = document.getElementById('sensitivity');
        const sensitivityValue = document.getElementById('sensitivityValue');
        
        let count = 0;
        let detectionEnabled = false;
        let previousFrame = null;
        let sensitivity = 20;
        
        const img = new Image();

        toggleBtn.onclick = () => {
            detectionEnabled = !detectionEnabled;
            toggleBtn.textContent = detectionEnabled ? 'Disable Detection' : 'Enable Detection';
            toggleBtn.style.background = detectionEnabled ? '#4CAF50' : '';
            toggleBtn.style.color = detectionEnabled ? 'white' : '';
            if (!detectionEnabled) {
                detectionCtx.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);
            }
        };

        sensitivitySlider.oninput = (e) => {
            sensitivity = parseInt(e.target.value);
            sensitivityValue.textContent = sensitivity;
        };

        function detectHandwriting(imageData, previousImageData) {
            const data = imageData.data;
            const prevData = previousImageData.data;
            const width = imageData.width;
            const height = imageData.height;
            
            // Create output for detection visualization
            const output = detectionCtx.createImageData(width, height);
            
            // Track motion intensity
            let motionMap = new Uint8Array(width * height);
            
            // Detect changes between frames
            for (let i = 0; i < data.length; i += 4) {
                const idx = i / 4;
                
                // Calculate difference in grayscale
                const curr = (data[i] + data[i + 1] + data[i + 2]) / 3;
                const prev = (prevData[i] + prevData[i + 1] + prevData[i + 2]) / 3;
                const diff = Math.abs(curr - prev);
                
                if (diff > sensitivity) {
                    motionMap[idx] = 255;
                }
            }
            
            // Apply morphological operations to reduce noise
            const kernel = 3;
            const dilated = new Uint8Array(width * height);
            
            for (let y = kernel; y < height - kernel; y++) {
                for (let x = kernel; x < width - kernel; x++) {
                    let maxVal = 0;
                    for (let ky = -kernel; ky <= kernel; ky++) {
                        for (let kx = -kernel; kx <= kernel; kx++) {
                            const idx = (y + ky) * width + (x + kx);
                            maxVal = Math.max(maxVal, motionMap[idx]);
                        }
                    }
                    dilated[y * width + x] = maxVal;
                }
            }
            
            // Draw detection overlay
            for (let i = 0; i < dilated.length; i++) {
                const intensity = dilated[i];
                const pixelIdx = i * 4;
                
                if (intensity > 0) {
                    // Highlight detected motion in bright cyan/yellow
                    output.data[pixelIdx] = 0;      // R
                    output.data[pixelIdx + 1] = 255; // G
                    output.data[pixelIdx + 2] = 255; // B
                    output.data[pixelIdx + 3] = 180; // A
                } else {
                    // Keep original but dimmed
                    output.data[pixelIdx] = data[pixelIdx] * 0.3;
                    output.data[pixelIdx + 1] = data[pixelIdx + 1] * 0.3;
                    output.data[pixelIdx + 2] = data[pixelIdx + 2] * 0.3;
                    output.data[pixelIdx + 3] = 255;
                }
            }
            
            return output;
        }

        img.onload = () => {
            // Set canvas sizes
            originalCanvas.width = img.width;
            originalCanvas.height = img.height;
            detectionCanvas.width = img.width;
            detectionCanvas.height = img.height;
            
            // Draw original
            originalCtx.drawImage(img, 0, 0);
            
            // Perform detection if enabled
            if (detectionEnabled) {
                const currentFrame = originalCtx.getImageData(0, 0, img.width, img.height);
                
                if (previousFrame && previousFrame.width === img.width && previousFrame.height === img.height) {
                    const detected = detectHandwriting(currentFrame, previousFrame);
                    detectionCtx.putImageData(detected, 0, 0);
                } else {
                    // First frame or size mismatch, just show dimmed version
                    detectionCtx.drawImage(img, 0, 0);
                    detectionCtx.fillStyle = 'rgba(0, 0, 0, 0.5)';
                    detectionCtx.fillRect(0, 0, detectionCanvas.width, detectionCanvas.height);
                }
                
                previousFrame = currentFrame;
            }
        };

        socket.on('video_frame', (data) => {
            img.src = data.frame;
            count++;
            frameCount.textContent = count;
            status.textContent = 'Receiving stream...';
        });

        socket.on('connect', () => {
            status.textContent = 'Connected to server';
        });

        socket.on('disconnect', () => {
            status.textContent = 'Disconnected from server';
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
    <body style="font-family: Arial; margin: 50px;">
        <h1>iPhone to MacBook Camera Stream</h1>
        <h2>Instructions:</h2>
        <ol>
            <li>On your iPhone, visit: <strong>/sender</strong></li>
            <li>On your MacBook, visit: <strong>/receiver</strong></li>
            <li>Start streaming from your iPhone</li>
        </ol>
        <p><a href="/sender">Go to Sender (iPhone)</a></p>
        <p><a href="/receiver">Go to Receiver (MacBook)</a></p>
    </body>
    </html>
    '''

@app.route('/sender')
def sender():
    return render_template_string(SENDER_HTML)

@app.route('/receiver')
def receiver():
    return render_template_string(RECEIVER_HTML)

@socketio.on('frame')
def handle_frame(data):
    global latest_frame, frame_count
    latest_frame = data['data']
    frame_count += 1
    
    # Broadcast frame to all receivers (don't include sender)
    emit('video_frame', {'frame': latest_frame}, broadcast=True, include_self=False)
    
    if frame_count % 100 == 0:
        print(f"Processed {frame_count} frames at {datetime.now()}")

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {datetime.now()}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {datetime.now()}")

if __name__ == '__main__':
    import os
    
    print("=" * 50)
    print("Camera Stream Server Starting")
    print("=" * 50)
    print("\nMake sure both devices are on the same network!")
    
    # Generate self-signed certificate if it doesn't exist
    cert_file = 'cert.pem'
    key_file = 'key.pem'
    
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        print("\nGenerating self-signed certificate...")
        import subprocess
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
            '-nodes', '-out', cert_file, '-keyout', key_file,
            '-days', '365', '-subj', '/CN=localhost'
        ], check=True)
        print("Certificate generated!")
    
    print("\nTo access from iPhone:")
    print("1. Find your MacBook's IP address (System Settings > Network)")
    print("2. On iPhone, visit: https://YOUR_MACBOOK_IP:5001/sender")
    print("3. Accept the security warning (self-signed certificate)")
    print("4. On MacBook, visit: https://localhost:5001/receiver")
    print("\nNote: You'll see a security warning - this is normal for self-signed certs")
    print("=" * 50)
    
    # Run with SSL on all network interfaces so iPhone can connect
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, 
                 allow_unsafe_werkzeug=True, 
                 ssl_context=(cert_file, key_file))
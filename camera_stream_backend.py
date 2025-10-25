from flask import Flask, render_template_string, Response
from flask_socketio import SocketIO, emit
import base64
import cv2
import numpy as np
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", max_size=10000000)

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
                    video: { facingMode: 'environment', width: 640, height: 480 } 
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
                        const frame = canvas.toDataURL('image/jpeg', 0.7);
                        socket.emit('frame', { data: frame });
                    }
                }, 100); // Send ~10 frames per second
                
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
        #frame { max-width: 90%; border: 3px solid #333; background: white; }
        #status { margin: 20px; font-size: 18px; font-weight: bold; }
        .info { margin: 10px; color: #666; }
    </style>
</head>
<body>
    <h1>MacBook Camera Receiver</h1>
    <div id="status">Waiting for stream...</div>
    <div class="info">Frames received: <span id="frameCount">0</span></div>
    <img id="frame" src="" alt="Camera feed will appear here">

    <script>
        const socket = io();
        const frame = document.getElementById('frame');
        const status = document.getElementById('status');
        const frameCount = document.getElementById('frameCount');
        let count = 0;

        socket.on('video_frame', (data) => {
            frame.src = data.frame;
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
    
    # Broadcast frame to all receivers
    emit('video_frame', {'frame': latest_frame}, broadcast=True)
    
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
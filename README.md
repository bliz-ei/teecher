# 📚 AI Math Tutor - Smart Camera-Based Learning Assistant

An intelligent math tutoring application that uses your phone's camera to analyze handwritten math problems and provides Socratic tutoring with optional text-to-speech feedback. Perfect for students who want personalized, step-by-step guidance while learning math!

## ✨ Project Features

### 🎥 **Live Camera Integration**
- Real-time camera feed from your phone or computer
- Capture photos of handwritten math problems
- Automatic image processing and analysis
- Works on both iPhone and desktop browsers

### 🤖 **AI-Powered Tutoring**
- **Gemini Vision AI**: Advanced computer vision to "read" and understand your handwritten work
- **Socratic Method**: Guides you to discover answers rather than just giving them
- **Context-Aware Responses**: Understands if you're asking for hints, checking work, or stuck
- **Adaptive Difficulty**: Adjusts help based on how long you've been working on a problem
- **OCR Fallback**: Uses Tesseract OCR if Gemini is unavailable

### 💬 **Smart Chat Interface**
- Multiple chat sessions - start fresh conversations for different problems
- Session history - review past tutoring sessions
- Persistent storage - all chats saved locally
- Auto-scroll and mobile-optimized UI
- Emoji-rich, friendly responses

### 🧠 **Intelligent Tutoring Logic**
- **Time Tracking**: Monitors how long you work on each problem
- **Hint System**: Progressive hints that get more specific
- **Frustration Detection**: Recognizes when you're stuck and adjusts approach
- **Answer Checking**: Reviews your solutions and guides error correction
- **Practice Problems**: Generates similar problems after showing solutions
- **Encouragement**: Celebrates effort and progress, not just correctness

### 🔊 **Text-to-Speech (TTS) Integration**
- **Fish Audio API**: High-quality voice synthesis
- **Toggle Control**: Easy on/off switch with 🔊/🔇 icons
- **Automatic Playback**: AI responses spoken aloud when enabled
- **Visual Indicators**: See when audio is generating and playing
- **Persistent Settings**: Your preference saved across sessions
- **Smart Controls**: Only one audio plays at a time

### 📱 **Mobile-First Design**
- iPhone-optimized interface
- Responsive layout for all screen sizes
- Touch-friendly controls
- iOS Safari camera support with HTTPS
- Smooth animations and transitions

### 🔒 **Privacy & Security**
- HTTPS/SSL support for secure camera access
- Local session storage
- Environment variable API key management
- No data sent to third parties (except AI APIs)

---

## 🚀 Complete Setup Guide

### Prerequisites

- **Python 3.8+** installed on your system
- **pip** (Python package manager)
- **Tesseract OCR** (for fallback text extraction)
- A **smartphone or webcam** for taking photos
- Internet connection for AI APIs

### Step 1: Install System Dependencies

#### Install Tesseract OCR

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Linux:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

### Step 2: Get API Keys

#### Gemini API Key (Required)
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Get API Key" or "Create API Key"
4. Copy your API key

#### Fish Audio API Key (Optional - for TTS)
1. Visit [Fish Audio](https://fish.audio/)
2. Create an account
3. Navigate to API settings
4. Generate a new API key
5. Copy your API key

### Step 3: Set Up Environment Variables

Choose the method that works for your operating system:

#### macOS/Linux (Temporary - current session only):
```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
export FISH_AUDIO_API_KEY="your-fish-audio-api-key-here"
```

#### macOS/Linux (Permanent):
Add to `~/.bashrc`, `~/.zshrc`, or `~/.bash_profile`:
```bash
echo 'export GEMINI_API_KEY="your-gemini-api-key-here"' >> ~/.bashrc
echo 'export FISH_AUDIO_API_KEY="your-fish-audio-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

#### Windows (Command Prompt):
```cmd
set GEMINI_API_KEY=your-gemini-api-key-here
set FISH_AUDIO_API_KEY=your-fish-audio-api-key-here
```

#### Windows (PowerShell):
```powershell
$env:GEMINI_API_KEY="your-gemini-api-key-here"
$env:FISH_AUDIO_API_KEY="your-fish-audio-api-key-here"
```

#### Windows (Permanent):
1. Search for "Environment Variables" in Windows
2. Click "Edit the system environment variables"
3. Click "Environment Variables" button
4. Under "User variables", click "New"
5. Add each variable name and value

### Step 4: Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `flask` - Web framework
- `flask-cors` - Cross-origin resource sharing
- `opencv-python` - Image processing
- `numpy` - Numerical computing
- `pillow` - Image manipulation
- `pytesseract` - OCR text extraction
- `google-generativeai` - Gemini AI API
- `requests` - HTTP library for Fish Audio API

### Step 5: Set Up SSL (For iPhone Camera Access)

The camera requires HTTPS to work on iPhone. Generate SSL certificates:

#### Option A: Using the provided script
```bash
chmod +x setup_ssl.sh
./setup_ssl.sh
```

#### Option B: Manual setup
```bash
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj "/CN=localhost"
```

### Step 6: Project Structure

Organize your files like this:
```
your-project-folder/
├── app.py                 # Flask backend (main server)
├── templates/
│   └── mobile.html       # Frontend interface
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── setup_ssl.sh         # SSL certificate generator (optional)
├── cert.pem             # SSL certificate (auto-generated)
├── key.pem              # SSL private key (auto-generated)
└── chat_sessions.json   # Session storage (auto-created)
```

**Important:** Place `mobile.html` inside a `templates/` folder!

### Step 7: Run the Application

```bash
python app.py
```

You'll see output like:
```
✅ Gemini configured successfully
✅ Fish Audio API key configured
🔐 Starting with HTTPS (SSL enabled)
📱 Access from iPhone: https://[your-local-ip]:5001
💻 Access from MacBook: https://localhost:5001
```

### Step 8: Access the Application

#### On the Same Computer:
Open your browser and go to:
```
https://localhost:5001
```

#### On iPhone (Same Network):
1. Find your computer's local IP address:
   - **macOS**: System Preferences → Network → Your IP
   - **Windows**: Run `ipconfig` and look for IPv4 Address
   - **Linux**: Run `hostname -I`

2. On your iPhone, open Safari and go to:
   ```
   https://[your-ip-address]:5001
   ```
   Example: `https://192.168.1.100:5001`

3. You'll see a security warning (self-signed certificate)
   - Click "Show Details" → "Visit this website"
   - Confirm you want to proceed

4. Grant camera permissions when prompted

---

## 🎯 How to Use

### Starting a Chat Session

1. **Point Camera**: Aim your camera at a handwritten math problem
2. **Click "Start Chat"**: This captures the image and starts analysis
3. **Get Help**: The AI tutor will analyze your work and respond

### Interacting with the Tutor

**Ask for hints:**
- "Can you give me a hint?"
- "I'm stuck, can you help?"
- "How do I start?"

**Check your work:**
- "Is this correct?"
- "Can you check my answer?"
- "I got 42, is that right?"

**Request the answer:**
- Work on the problem for 2+ minutes, OR
- Ask for 3+ hints
- Say "I give up" or "Just tell me the answer"

### Using Text-to-Speech

1. Click the speaker icon 🔊 in the top-right corner
2. When enabled, all AI responses are read aloud
3. Click again 🔇 to disable
4. Your preference is saved automatically

### Managing Sessions

- **New Chat**: Click "+" or hamburger menu → "New Chat"
- **View History**: Click hamburger menu to see past sessions
- **Continue Session**: Click any previous session to resume

---

## 🔧 API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve main interface |
| `/api/sessions` | GET | Get all chat sessions |
| `/api/session/<id>` | GET | Get specific session |
| `/api/new_session` | POST | Create new chat session |
| `/api/send_message` | POST | Send message with image |
| `/api/tts` | POST | Generate text-to-speech audio |
| `/api/delete_session/<id>` | DELETE | Delete a session |

---

## 🎨 Customization Options

### Change TTS Voice

Edit `app.py`, line ~490:
```python
payload = {
    "text": text,
    "reference_id": "your-custom-voice-id",  # Specify voice ID
    "format": "mp3",
    # ...
}
```

### Adjust TTS Quality

```python
"mp3_bitrate": 192,      # Higher = better quality (64, 128, 192, 256)
"latency": "low"         # "normal" or "low" for faster generation
```

### Modify Tutoring Behavior

Edit prompts in `app.py` around lines 126-198 to change:
- Tone and personality
- Hint progression
- When to reveal answers
- Response format

### Change UI Colors

Edit `mobile.html` CSS around lines 8-400 to customize:
- Background colors
- Button styles
- Message bubbles
- Icon colors

---

## 🐛 Troubleshooting

### Camera Not Working

**Problem**: Camera doesn't start or shows black screen

**Solutions:**
- ✅ Ensure you're using HTTPS (iPhone requires it)
- ✅ Check browser permissions for camera access
- ✅ On iPhone: Settings → Safari → Camera → Allow
- ✅ Try a different browser (Safari for iPhone, Chrome for desktop)
- ✅ Restart the browser

### SSL Certificate Warnings

**Problem**: Browser shows security warning

**Solution:** This is normal for self-signed certificates
- Click "Advanced" → "Proceed anyway"
- On iPhone: "Show Details" → "Visit website"
- The warning appears because the certificate isn't from a trusted authority

### API Errors

**Problem**: "Gemini error" or "TTS unavailable"

**Solutions:**
- ✅ Verify API keys are set correctly: `echo $GEMINI_API_KEY`
- ✅ Check API key has proper permissions
- ✅ Verify internet connection
- ✅ Check API quotas/limits haven't been exceeded
- ✅ Restart the Flask server

### OCR Fallback Only

**Problem**: App uses OCR instead of Gemini

**Solutions:**
- ✅ Ensure `GEMINI_API_KEY` environment variable is set
- ✅ Check Flask startup logs for "✅ Gemini configured"
- ✅ Verify API key is valid
- ✅ OCR fallback is normal if Gemini fails temporarily

### TTS Not Playing

**Problem**: Audio doesn't play after AI response

**Solutions:**
- ✅ Check TTS toggle is enabled (🔊 not 🔇)
- ✅ Verify `FISH_AUDIO_API_KEY` is set
- ✅ Check browser console for errors (F12)
- ✅ Ensure browser supports audio playback
- ✅ Try interacting with page first (browsers block auto-play)
- ✅ Check Fish Audio API quota

### Port Already in Use

**Problem**: Error - port 5001 already in use

**Solutions:**
```bash
# Find process using port 5001
lsof -i :5001

# Kill the process
kill -9 <PID>

# Or use a different port in app.py
app.run(port=5002, ...)
```

---

## 📝 Important Notes

- 🔑 **API Keys**: Keep them secret! Never commit to git
- 💰 **API Costs**: Both Gemini and Fish Audio have usage limits
- 📸 **Image Quality**: Better lighting = better OCR/AI analysis
- 🌐 **Network**: Requires internet for AI features
- 💾 **Storage**: Sessions saved in `chat_sessions.json`
- 🔒 **Privacy**: Images sent to Google (Gemini) and Fish Audio APIs

---

## 🔐 Security Best Practices

1. **Never hardcode API keys** in your code
2. Use **environment variables** for sensitive data
3. Add `.env` files to `.gitignore` if using python-dotenv
4. **Rotate API keys** periodically
5. Use **HTTPS** for production deployments
6. Don't commit `cert.pem` or `key.pem` to version control
7. Consider rate limiting for production use

---

## 📚 Helpful Resources

- [Gemini API Documentation](https://ai.google.dev/docs)
- [Fish Audio API Docs](https://fish.audio/docs/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [OpenCV Python Docs](https://docs.opencv.org/)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

---

## 🤝 Contributing

Contributions welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Improve documentation

---

## 📄 License

This project is open source and available under the MIT License.

---

## 💡 Tips for Best Results

1. **Good Lighting**: Ensure paper is well-lit and visible
2. **Clear Writing**: Write legibly for better OCR accuracy
3. **Be Patient**: AI analysis takes a few seconds
4. **Ask Questions**: The tutor responds better to specific questions
5. **Try First**: The AI gives better hints when you show effort
6. **Practice**: Use the generated practice problems to reinforce learning

---

**Happy Learning! 📚✨**
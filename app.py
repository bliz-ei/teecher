from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS
import cv2
import numpy as np
import base64
from datetime import datetime
import json
import os
import pytesseract
from PIL import Image
import io
import time
import google.generativeai as genai
import requests

app = Flask(__name__)
CORS(app)

# Configure Gemini
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    print("✅ Gemini configured successfully")
else:
    model = None
    print("⚠️  GEMINI_API_KEY not found - using OCR fallback only")

# Configure Fish Audio API
FISH_AUDIO_API_KEY = os.environ.get('FISH_AUDIO_API_KEY')
if FISH_AUDIO_API_KEY:
    print("✅ Fish Audio API key configured")
else:
    print("⚠️  FISH_AUDIO_API_KEY not found - TTS will be disabled")

# Storage for chat sessions
SESSIONS_FILE = 'chat_sessions.json'
sessions = []

# Track problem start times for each session
problem_tracking = {}

def load_sessions():
    global sessions
    if os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, 'r') as f:
            sessions = json.load(f)
    else:
        sessions = []

def save_sessions():
    with open(SESSIONS_FILE, 'w') as f:
        json.dump(sessions, f, indent=2)

load_sessions()


def get_time_on_problem(session_id):
    """Calculate how long user has been working on current problem"""
    if session_id not in problem_tracking:
        problem_tracking[session_id] = {
            'start_time': time.time(),
            'hint_count': 0,
            'problem_text': None
        }
        return 0
    
    elapsed = time.time() - problem_tracking[session_id]['start_time']
    return elapsed


def reset_problem_timer(session_id, problem_text=None):
    """Reset timer when starting a new problem"""
    problem_tracking[session_id] = {
        'start_time': time.time(),
        'hint_count': 0,
        'problem_text': problem_text
    }


def increment_hint_count(session_id):
    """Track how many hints given"""
    if session_id in problem_tracking:
        problem_tracking[session_id]['hint_count'] += 1
        return problem_tracking[session_id]['hint_count']
    return 0


def analyze_with_gemini(image_data, question, session_id, is_first_message):
    """
    Use Gemini Vision to analyze the student's work and provide tutoring.
    This is the primary analysis method.
    """
    if not model:
        return None
    
    try:
        # Get session context
        time_elapsed = get_time_on_problem(session_id)
        hint_count = problem_tracking.get(session_id, {}).get('hint_count', 0)
        should_give_answer = time_elapsed > 120 or hint_count >= 3
        
        # Check what type of help they're asking for (only if not first message)
        asking_for_answer = False
        expressing_frustration = False
        asking_for_help = False
        asking_to_check = False
        giving_answer = False
        
        if not is_first_message and question:
            question_lower = question.lower()
            
            # Check if they're giving an answer (numbers, "is it", "i think", etc.)
            giving_answer = any(word in question_lower for word in [
                'is it', 'i think', 'i got', 'my answer is', 'the answer is',
                '=', 'equals'
            ]) or any(char.isdigit() for char in question_lower)
            
            asking_for_answer = any(word in question_lower for word in [
                'answer', 'solution', 'what is', "what's", 'tell me', 'give me', 'just tell'
            ])
            expressing_frustration = any(word in question_lower for word in [
                'stuck', 'confused', "don't get", "dont get", 'frustrated', 
                'give up', 'too hard', "can't do", "cant do", 'still stuck'
            ])
            asking_for_help = any(word in question_lower for word in [
                'help', 'hint', 'clue', 'how do', 'how to', 'explain'
            ])
            asking_to_check = any(word in question_lower for word in [
                'check', 'correct', 'right', 'wrong', 'grade', 'review'
            ])
        
        # Build context-aware prompt for Gemini
        if is_first_message:
            prompt = f"""You are a Socratic math tutor helping a student learn. The student just took a photo of their work and wants help.

**Session Context:**
- This is the FIRST time you're seeing this problem
- Time working on this problem: {int(time_elapsed)}s
- Number of hints already given: {hint_count}
- Should reveal answer: {'YES' if should_give_answer else 'NO'}

**Default Intent (First Photo):**
The student is implicitly asking: "Can you help me with this problem?"

            """
        else:
            prompt = f"""You are a Socratic math tutor helping a student learn. The student is continuing to work on a problem.

**Session Context:**
- Student follow-up: {question}
- Time working on this problem: {int(time_elapsed)}s
- Number of hints already given: {hint_count}
- Should reveal answer: {'YES' if should_give_answer else 'NO'}

**Student Intent:**
- Giving an answer to check: {'YES' if giving_answer else 'NO'}
- Asking for direct answer: {'YES' if asking_for_answer else 'NO'}
- Expressing frustration: {'YES' if expressing_frustration else 'NO'}
- Asking for help/hint: {'YES' if asking_for_help else 'NO'}
- Asking to check work: {'YES' if asking_to_check else 'NO'}

**Your Tutoring Approach:**

1. **If should reveal answer = YES** (worked 2+ min OR 3+ hints OR very frustrated):
   - Start with: "I can see you've been working hard on this! Let me show you the answer and we'll work backwards to understand it."
   - Give the answer clearly: "✅ **The answer is: [ANSWER]**"
   - Explain step-by-step how to get there
   - Generate a similar practice problem for them to try
   - End with encouragement to try the practice problem

2. **If asking to check their work:**
   - Acknowledge their work positively
   - DO NOT immediately say if it is right or wrong
   - Ask them to explain their thinking first
   - Guide them to find their own errors if any

3. **If asking for help (first time):**
   - Give a gentle hint about what type of problem it is
   - Ask guiding questions about the first step
   - Encourage them to try
   - Do not give away the answer

4. **If asking for help (2nd-3rd hint):**
   - Be more specific in your hints
   - Break down the first step more clearly
   - Still encourage them to do the calculation themselves

5. **General inquiry:**
   - Describe what you see in their work
   - Ask how you can help
   - Offer options: hint, check work, explain concept, etc.

**Tone & Style:**
- Use emoji for engagement (📝, 🤔, 💡, ✅, 🎯)
- Be warm, encouraging, patient
- Celebrate effort, not just correctness
- Keep responses conversational and clear
- Format with markdown for readability

**IMPORTANT:**
- Focus on teaching, not just giving answers
- Build confidence through guided discovery
- Make learning feel like a conversation, not a lecture

Now analyze the image and respond appropriately:"""

        # Convert base64 image to PIL Image for Gemini
        img_data = base64.b64decode(image_data.split(',')[1])
        pil_image = Image.open(io.BytesIO(img_data))
        
        # Call Gemini Vision API
        response = model.generate_content([prompt, pil_image])
        
        # Update hint count if we gave a hint (only if not first message)
        if not is_first_message and (asking_for_help or expressing_frustration):
            increment_hint_count(session_id)
        
        # Reset timer if we gave the answer
        if should_give_answer:
            reset_problem_timer(session_id, None)
        
        return {
            "success": True,
            "response": response.text,
            "method": "gemini",
            "should_restart": False
        }
        
    except Exception as e:
        print(f"Gemini error: {e}")
        return None


def preprocess_image_for_ocr(image):
    """Preprocess image to improve OCR accuracy"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    results = []
    
    # Try multiple preprocessing techniques
    configs = [
        ('original', gray),
        ('threshold', cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),
        ('adaptive', cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY, 11, 2)),
    ]
    
    for name, processed in configs:
        text = pytesseract.image_to_string(processed, config='--psm 6')
        if text.strip():
            results.append((name, text.strip(), len(text.strip())))
    
    if results:
        results.sort(key=lambda x: x[2], reverse=True)
        return results[0][1]
    
    return ""


def extract_text_from_image(image_data):
    """Extract text from base64 image using OCR (fallback method)"""
    try:
        img_data = base64.b64decode(image_data.split(',')[1])
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return None
        
        text = preprocess_image_for_ocr(frame)
        return text
        
    except Exception as e:
        print(f"OCR error: {e}")
        return None


def generate_tutoring_response_fallback(extracted_text, question, session_id):
    """
    Generate a tutoring response using OCR text (fallback when Gemini fails).
    This is a simplified fallback that doesn't use vision.
    """
    time_elapsed = get_time_on_problem(session_id)
    hint_count = problem_tracking.get(session_id, {}).get('hint_count', 0)
    
    # Build response based on what we see
    response = ""
    
    # Check if this looks like a new problem
    if any(symbol in extracted_text for symbol in ['=', '+', '-', '×', '÷', '/', '*']):
        # Looks like a math problem
        reset_problem_timer(session_id, extracted_text)
        
        response = f"📸 I can see your math problem:\n\n"
        response += f"**{extracted_text}**\n\n"
        
        if question and any(word in question.lower() for word in ['help', 'hint', 'stuck']):
            increment_hint_count(session_id)
            response += "💡 **Here's a hint:** Start by identifying what type of problem this is. "
            response += "What operation do you need to use?\n\n"
        
        response += "Show me what you try next!"
    
    else:
        response = f"I can see your work:\n\n📝 {extracted_text}\n\n"
        response += "How can I help? You can:\n"
        response += "• Show me your attempt and I'll guide you\n"
        response += "• Ask for a hint\n"
        response += "• Tell me where you're stuck\n\n"
        response += "I'm here to help you learn! 🎓"
    
    return response


def analyze_written_work(image_data, question, session_id):
    """
    Main analysis function - tries Gemini first, falls back to OCR if needed.
    """
    try:
        # Decode image for basic validation
        img_data = base64.b64decode(image_data.split(',')[1])
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return {
                "success": False,
                "response": "❌ I couldn't process that image. The file might be corrupted.\n\nPlease start a new chat and try taking another photo!",
                "should_restart": True
            }
        
        # Determine if this is the first message in the session
        session = next((s for s in sessions if s['id'] == session_id), None)
        is_first_message = True
        if session and len(session.get('messages', [])) > 0:
            # Check if there are any previous assistant messages
            assistant_messages = [m for m in session['messages'] if m.get('role') == 'assistant']
            is_first_message = len(assistant_messages) == 0
        
        # Try Gemini first (primary method)
        if model:
            print(f"🤖 Analyzing with Gemini Vision... (first_message: {is_first_message})")
            gemini_result = analyze_with_gemini(image_data, question, session_id, is_first_message)
            
            if gemini_result and gemini_result.get('success'):
                print("✅ Gemini analysis successful")
                return gemini_result
            else:
                print("⚠️  Gemini failed, falling back to OCR...")
        
        # Fallback to OCR method
        print("📝 Using OCR fallback...")
        extracted_text = extract_text_from_image(image_data)
        
        if extracted_text and len(extracted_text.strip()) > 1:
            response_text = generate_tutoring_response_fallback(
                extracted_text, 
                question, 
                session_id
            )
            
            return {
                "success": True,
                "response": response_text,
                "method": "ocr",
                "extracted_text": extracted_text,
                "should_restart": False
            }
        
        else:
            # Couldn't read the text
            response = "😕 I'm having trouble reading what's on the paper. "
            response += "The image might be:\n"
            response += "• Too blurry or out of focus\n"
            response += "• Too far away from the camera\n"
            response += "• Not enough lighting\n"
            response += "• Text is too light or faint\n\n"
            response += "💡 **Please try again:**\n"
            response += "• Move the camera closer to the paper\n"
            response += "• Make sure it's in focus (tap on the screen)\n"
            response += "• Use better lighting\n"
            response += "• Write darker/clearer\n\n"
            response += "🔄 **Start a new chat** and take a clearer photo!"
            
            return {
                "success": False,
                "response": response,
                "extracted_text": None,
                "should_restart": True
            }
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return {
            "success": False,
            "error": str(e),
            "response": "❌ Something went wrong processing your image.\n\nPlease start a new chat and try again!",
            "should_restart": True
        }


@app.route('/')
def index():
    """Serve the iPhone interface"""
    return render_template('mobile.html')


@app.route('/api/sessions')
def get_sessions():
    """Get all chat sessions"""
    return jsonify({"sessions": sessions})


@app.route('/api/session/<session_id>')
def get_session(session_id):
    """Get a specific session"""
    session = next((s for s in sessions if s['id'] == session_id), None)
    if session:
        return jsonify(session)
    return jsonify({"error": "Session not found"}), 404


@app.route('/api/new_session', methods=['POST'])
def new_session():
    """Create a new chat session"""
    session = {
        "id": f"session_{int(datetime.now().timestamp() * 1000)}",
        "timestamp": datetime.now().isoformat(),
        "messages": []
    }
    sessions.insert(0, session)
    save_sessions()
    return jsonify(session)


@app.route('/api/send_message', methods=['POST'])
def send_message():
    """Process a user message with image of written work"""
    data = request.json
    session_id = data.get('session_id')
    message = data.get('message', '').strip()
    image = data.get('image')
    
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400
    
    session = next((s for s in sessions if s['id'] == session_id), None)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    # If no message provided but image exists, use default prompt
    if not message and image:
        message = "Can you help me with this?"
    
    if not message:
        return jsonify({"error": "Missing message"}), 400
    
    # Add user message
    user_msg = {
        "role": "user",
        "content": message,
        "timestamp": datetime.now().isoformat(),
        "has_image": image is not None
    }
    session['messages'].append(user_msg)
    
    # Analyze the written work if image provided
    should_restart = False
    if image:
        result = analyze_written_work(image, message, session_id)
        response_text = result['response']
        should_restart = result.get('should_restart', False)
    else:
        response_text = "Please take a photo of your work so I can help you with it!"
    
    # Add assistant response
    assistant_msg = {
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now().isoformat()
    }
    session['messages'].append(assistant_msg)
    
    save_sessions()
    
    return jsonify({
        "session": session,
        "success": True,
        "should_restart": should_restart
    })


@app.route('/api/tts', methods=['POST'])
def generate_tts():
    """Generate TTS audio using Fish Audio API"""
    if not FISH_AUDIO_API_KEY:
        return jsonify({"error": "Fish Audio API key not configured"}), 500
    
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({"error": "Missing text"}), 400
    
    try:
        url = "https://api.fish.audio/v1/tts"
        
        # FIXED: Added 'model' header as shown in curl
        headers = {
            "Authorization": f"Bearer {FISH_AUDIO_API_KEY}",
            "Content-Type": "application/json",
            "model": "fishaudio-tts-1"  # Add the model header (check Fish Audio docs for correct model name)
        }
        
        # FIXED: Updated payload structure to match curl example
        payload = {
            "text": text,
            "reference_id": "8ef4a238714b45718ce04243307c57a7",  # Keep your voice ID
            "format": "mp3",
            "mp3_bitrate": 128,
            "normalize": True,
            "latency": "normal",
            "chunk_length": 200
        }
        
        # Optional: If you need custom references
        # payload["references"] = [{"text": "reference text here"}]
        
        print(f"📢 TTS Request: {text[:50]}..." if len(text) > 50 else f"📢 TTS Request: {text}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            if len(response.content) == 0:
                print("⚠️ Empty audio response from Fish Audio")
                return jsonify({"error": "Empty audio response"}), 500
            
            print(f"✅ TTS Success: {len(response.content)} bytes")
            print(f"🎵 First 20 bytes (hex): {response.content[:20].hex()}")
            
            audio_base64 = base64.b64encode(response.content).decode('utf-8')
            return jsonify({
                "success": True,
                "audio": f"data:audio/mp3;base64,{audio_base64}"
            })
        else:
            error_msg = f"Fish Audio API error: {response.status_code}"
            try:
                error_detail = response.json()
                print(f"❌ {error_msg} - Details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"❌ {error_msg} - Response: {response.text}")
            
            return jsonify({
                "error": error_msg,
                "details": response.text[:500]
            }), response.status_code
            
    except requests.exceptions.Timeout:
        print("⏱️ TTS timeout - request took too long")
        return jsonify({"error": "TTS request timeout"}), 504
    except requests.exceptions.ConnectionError as e:
        print(f"🔌 Connection error to Fish Audio: {e}")
        return jsonify({"error": "Failed to connect to Fish Audio API"}), 503
    except Exception as e:
        print(f"❌ Unexpected TTS error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/delete_session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session"""
    global sessions
    sessions = [s for s in sessions if s['id'] != session_id]
    save_sessions()
    return jsonify({"success": True})


if __name__ == '__main__':
    import sys
    
    if os.path.exists('cert.pem') and os.path.exists('key.pem'):
        print("🔐 Starting with HTTPS (SSL enabled)")
        print("📱 Access from iPhone: https://[your-local-ip]:5001")
        print("💻 Access from MacBook: https://localhost:5001")
        app.run(
            host='0.0.0.0', 
            port=5001, 
            ssl_context=('cert.pem', 'key.pem'),
            debug=True, 
            threaded=True
        )
    else:
        print("⚠️  SSL certificates not found!")
        print("🔧 Run this command first: bash setup_ssl.sh")
        print("   Or: chmod +x setup_ssl.sh && ./setup_ssl.sh")
        print("")
        print("📖 Alternative: Start without SSL (camera won't work on iPhone)")
        response = input("Start anyway? (y/n): ")
        
        if response.lower() == 'y':
            print("🚀 Starting without HTTPS...")
            print("💻 Access from MacBook only: http://localhost:5001")
            app.run(host='0.0.0.0', port=5001, debug=True, threaded=True)
        else:
            print("👋 Exiting. Run setup_ssl.sh first!")
            sys.exit(1)
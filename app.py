from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS
import cv2
import numpy as np
import base64
from datetime import datetime
import json
import os

app = Flask(__name__)
CORS(app)

# Storage for chat sessions
SESSIONS_FILE = 'chat_sessions.json'
sessions = []

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


def analyze_written_work(image_data, question):
    """
    Analyze the written work in the image based on the user's question.
    This is where you would integrate OCR, handwriting recognition, 
    or AI vision models to understand what's written.
    """
    try:
        # Decode base64 image
        img_data = base64.b64decode(image_data.split(',')[1])
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Basic image analysis (you can expand this)
        height, width = frame.shape[:2]
        brightness = np.mean(frame)
        
        # For now, return a helpful response based on common questions
        # TODO: Integrate OCR (like pytesseract) or AI vision (like GPT-4 Vision)
        
        analysis = {
            "image_received": True,
            "image_size": f"{width}x{height}",
            "brightness": round(brightness, 2),
            "question": question
        }
        
        # Generate contextual response based on question keywords
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['help', 'check', 'correct', 'right', 'wrong']):
            response = "I can see your work! To help you better, I would need OCR integration to read the text. "
            response += "For now, I can see the image clearly. "
            response += "\n\nTo improve this app, you can:\n"
            response += "• Add pytesseract for OCR text extraction\n"
            response += "• Integrate GPT-4 Vision API for detailed analysis\n"
            response += "• Use mathpix for math equation recognition\n"
            response += "\nWhat specific help do you need with your work?"
        
        elif any(word in question_lower for word in ['math', 'equation', 'problem', 'solve']):
            response = "I can see you're working on a math problem! "
            response += "Once OCR is integrated, I'll be able to:\n"
            response += "• Read your equations\n"
            response += "• Check your work step-by-step\n"
            response += "• Explain where to improve\n"
            response += "\nCan you describe what you're working on?"
        
        elif any(word in question_lower for word in ['write', 'writing', 'handwriting', 'letter']):
            response = "I can see your handwriting practice! "
            response += "With computer vision analysis, I could help with:\n"
            response += "• Letter formation feedback\n"
            response += "• Spacing and alignment\n"
            response += "• Consistency across letters\n"
            response += "\nWhat specific aspect would you like help with?"
        
        elif any(word in question_lower for word in ['read', 'what', 'see', 'this']):
            response = f"I've captured an image ({width}x{height} pixels) of your work. "
            response += "The lighting looks good. "
            response += "\n\nTo read the actual text, you'll need to integrate:\n"
            response += "• Tesseract OCR (pip install pytesseract)\n"
            response += "• Or use GPT-4 Vision API for AI-powered analysis\n"
            response += "\nCan you tell me what you'd like me to focus on?"
        
        else:
            response = "I've received your image! I can see your work clearly. "
            response += "Right now, I'm set up to capture and analyze images. "
            response += "\n\nTo fully analyze your written work, you can integrate:\n"
            response += "• OCR for text recognition\n"
            response += "• AI vision models for understanding\n"
            response += "• Math recognition for equations\n"
            response += "\nHow can I help you with what you've written?"
        
        return {
            "success": True,
            "response": response,
            "analysis": analysis
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "response": f"Sorry, I couldn't process the image: {str(e)}"
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
    sessions.insert(0, session)  # Add to beginning
    save_sessions()
    return jsonify(session)


@app.route('/api/send_message', methods=['POST'])
def send_message():
    """Process a user message with image of written work"""
    data = request.json
    session_id = data.get('session_id')
    message = data.get('message')
    image = data.get('image')
    
    if not session_id or not message:
        return jsonify({"error": "Missing session_id or message"}), 400
    
    session = next((s for s in sessions if s['id'] == session_id), None)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    # Add user message
    user_msg = {
        "role": "user",
        "content": message,
        "timestamp": datetime.now().isoformat(),
        "has_image": image is not None
    }
    session['messages'].append(user_msg)
    
    # Analyze the written work if image provided
    if image:
        result = analyze_written_work(image, message)
        response_text = result['response']
    else:
        response_text = "Please take a photo of your written work so I can help you with it!"
    
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
        "success": True
    })


@app.route('/api/delete_session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session"""
    global sessions
    sessions = [s for s in sessions if s['id'] != session_id]
    save_sessions()
    return jsonify({"success": True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
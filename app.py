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
    
    # Method 1: Simple threshold
    _, thresh1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(thresh1)
    
    # Method 2: Adaptive threshold
    thresh2 = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    results.append(thresh2)
    
    # Method 3: Invert if dark background
    inverted = cv2.bitwise_not(gray)
    _, thresh3 = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(thresh3)
    
    # Method 4: Increase contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    _, thresh4 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(thresh4)
    
    return results


def extract_text_from_image(image_data):
    """Extract text from image using OCR with multiple methods"""
    try:
        img_data = base64.b64decode(image_data.split(',')[1])
        nparr = np.frombuffer(img_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return None
        
        processed_images = preprocess_image_for_ocr(image)
        
        all_texts = []
        
        configs = [
            r'--oem 3 --psm 6',  # Uniform block of text
            r'--oem 3 --psm 7',  # Single line
            r'--oem 3 --psm 11', # Sparse text
            r'--oem 3 --psm 13', # Raw line
        ]
        
        for processed in processed_images:
            pil_image = Image.fromarray(processed)
            for config in configs:
                try:
                    text = pytesseract.image_to_string(pil_image, config=config)
                    if text and len(text.strip()) > 0:
                        all_texts.append(text.strip())
                except:
                    continue
        
        # Also try with original color image
        try:
            original_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            for config in configs:
                text = pytesseract.image_to_string(original_pil, config=config)
                if text and len(text.strip()) > 0:
                    all_texts.append(text.strip())
        except:
            pass
        
        if not all_texts:
            return ""
        
        best_text = max(all_texts, key=len)
        best_text = best_text.replace('\n\n', '\n').strip()
        
        return best_text
    
    except Exception as e:
        print(f"OCR Error: {e}")
        return None


def solve_and_explain(extracted_text):
    """
    Solve the problem and explain the solution step-by-step.
    Fallback method when Gemini is not available.
    """
    try:
        import re
        
        text = extracted_text.replace('x', '×').replace('X', '×')
        text = text.replace('^', '**')
        
        patterns = [
            r'(\d+\.?\d*)\s*([+\-×÷*/])\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*[\^*]{1,2}\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*[/÷]\s*(\d+\.?\d*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) == 2:  # Exponent pattern
                    base = float(match.group(1))
                    exponent = float(match.group(2))
                    result = base ** exponent
                    return {
                        'answer': result,
                        'operation': 'exponentiation',
                        'explanation': f"When we raise {base} to the power of {exponent}, we multiply {base} by itself {int(exponent)} times",
                        'num1': base,
                        'num2': exponent,
                        'operator': '^',
                        'problem': f"{base}^{int(exponent)}"
                    }
                elif len(match.groups()) == 3:
                    num1 = float(match.group(1))
                    operator = match.group(2)
                    num2 = float(match.group(3))
                    
                    if operator in ['+']:
                        result = num1 + num2
                        operation_name = "addition"
                        explanation = f"When we add {num1} and {num2}, we combine them together"
                        practice_op = "+"
                    elif operator in ['-']:
                        result = num1 - num2
                        operation_name = "subtraction"
                        explanation = f"When we subtract {num2} from {num1}, we're finding the difference"
                        practice_op = "-"
                    elif operator in ['×', '*']:
                        result = num1 * num2
                        operation_name = "multiplication"
                        explanation = f"When we multiply {num1} by {num2}, we're adding {num1} to itself {int(num2)} times"
                        practice_op = "×"
                    elif operator in ['÷', '/']:
                        if num2 == 0:
                            return None
                        result = num1 / num2
                        operation_name = "division"
                        explanation = f"When we divide {num1} by {num2}, we're splitting {num1} into {int(num2)} equal parts"
                        practice_op = "÷"
                    else:
                        continue
                    
                    return {
                        'answer': result,
                        'operation': operation_name,
                        'explanation': explanation,
                        'num1': num1,
                        'num2': num2,
                        'operator': practice_op,
                        'problem': f"{num1} {operator} {num2}"
                    }
        
        return None
    except Exception as e:
        print(f"Solving error: {e}")
        return None


def generate_tutoring_response_fallback(extracted_text, question, session_id):
    """
    OCR-based fallback tutoring response when Gemini is not available.
    """
    question_lower = question.lower()
    
    time_elapsed = get_time_on_problem(session_id)
    hint_count = problem_tracking.get(session_id, {}).get('hint_count', 0)
    
    should_give_answer = time_elapsed > 120 or hint_count >= 3
    
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
    
    response = ""
    
    if should_give_answer or (expressing_frustration and hint_count >= 2):
        solution = solve_and_explain(extracted_text)
        
        if solution:
            response = "I can see you've been working hard on this! Let me show you the answer and we'll work backwards to understand it.\n\n"
            response += f"✅ **The answer is: {solution['answer']}**\n\n"
            response += f"📚 **Here's how we got there:**\n\n"
            response += f"**Step 1: Identify what we have**\n"
            response += f"• First number: {solution['num1']}\n"
            response += f"• Operation: {solution['operation']}\n"
            response += f"• Second number: {solution['num2']}\n\n"
            response += f"**Step 2: Understand the operation**\n"
            response += f"{solution['explanation']}.\n\n"
            response += f"**Step 3: Calculate**\n"
            response += f"{solution['num1']} {solution['operator']} {solution['num2']} = {solution['answer']}\n\n"
            response += f"🎯 **Now let's practice!**\n"
            response += f"Try a similar problem to make sure you understand:\n"
            
            if solution['operation'] == 'addition':
                response += f"What is {int(solution['num1']) + 1} + {int(solution['num2']) + 1}?\n\n"
            elif solution['operation'] == 'subtraction':
                response += f"What is {int(solution['num1']) + 2} - {int(solution['num2'])}?\n\n"
            elif solution['operation'] == 'multiplication':
                response += f"What is {int(solution['num1'])} × {int(solution['num2']) + 1}?\n\n"
            elif solution['operation'] == 'division':
                response += f"What is {int(solution['num1']) + int(solution['num2'])} ÷ {int(solution['num2'])}?\n\n"
            
            response += "Take a photo when you're ready and I'll help you work through it! 📸"
            reset_problem_timer(session_id, None)
        else:
            response = "I can see you've been struggling with this. Let me help break it down differently.\n\n"
            response += f"I see: {extracted_text}\n\n"
            response += "Let's approach this step by step:\n"
            response += "1. What are you trying to find?\n"
            response += "2. What information do you have?\n"
            response += "3. What's the first small step you could take?\n\n"
            response += "Or describe the problem in your own words and I'll guide you through it!"
    
    elif asking_for_answer and not asking_to_check:
        increment_hint_count(session_id)
        response = "I believe in you! Let's work through this together instead of me just giving the answer. "
        response += f"\n\nYou've got this! 💪 (Hint #{hint_count + 1})\n\n"
        
        if any(char in extracted_text for char in ['+', '-', '×', '÷', '=', '*', '/']):
            response += "🤔 Think about:\n"
            response += "• What operation do you see? (+, -, ×, ÷)\n"
            response += "• What's the first step in solving it?\n"
            response += "• Can you do that first step?\n\n"
            response += "Give it a try and show me what you get!"
        else:
            response += "🤔 Let's break it down:\n"
            response += "• What do you understand so far?\n"
            response += "• What's confusing you?\n"
            response += "• What's one small thing you could figure out?\n\n"
            response += "Start with what you know!"
    
    elif asking_to_check:
        response = "Great! Let's review your work together. "
        response += f"\n\n📝 I can see:\n{extracted_text}\n\n"
        
        if any(char in extracted_text for char in ['=', '+', '-', '×', '÷', '*', '/']):
            response += "🤔 Before I tell you if it's right:\n"
            response += "• Walk me through how you solved it\n"
            response += "• Which step did you do first?\n"
            response += "• Does your answer seem reasonable?\n\n"
            response += "Explain your thinking!"
    
    elif asking_for_help or expressing_frustration:
        hint_count = increment_hint_count(session_id)
        
        response = f"Don't worry, we'll figure this out together! (Hint #{hint_count})\n\n"
        response += f"📝 Looking at: {extracted_text}\n\n"
        
        if hint_count == 1:
            response += "💡 **First hint:**\n"
            response += "• What type of problem is this?\n"
            response += "• What operation(s) do you need to use?\n"
            response += "• What's the very first calculation you could do?\n\n"
        elif hint_count == 2:
            response += "💡 **Second hint (more specific):**\n"
            response += "• Look at the numbers you have\n"
            response += "• Think about what the operation means\n"
            response += "• Try to calculate just the first step\n\n"
        else:
            response += "💡 **Third hint (very specific):**\n"
            response += "You're working hard on this! "
            response += "Try breaking it into the smallest possible step. "
            response += "If you're still stuck after this, I'll show you the full solution.\n\n"
        
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
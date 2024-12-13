from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import openai
import uuid
import pytesseract
import speech_recognition as sr
from PIL import Image
from textblob import TextBlob#sentiment analysis

#initialize FastAPI app
app = FastAPI()

#CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#key setup
client = openai.OpenAI(api_key="") 

#in-memory user sessions
user_sessions = {}

#Constants
MAX_HISTORY_LENGTH = 20  #limit session history for better performance

#helper function to get or create a user session
def get_user_session(session_id):
    if session_id not in user_sessions:
        user_sessions[session_id] = {
            "history": [],
            "puzzle_history": [],
            "current_state": "chat",  #default state==chat
            "last_sentiment": "neutral",
            "last_puzzle": None,  #track the last puzzle
            "expected_answer": None,  #store the answer to the last puzzle
        }
    return user_sessions[session_id]

#sentiment analysis using TextBlob
def analyze_sentiment(text):
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    if polarity > 0.1:
        return "positive"
    elif polarity < -0.1:
        return "negative"
    else:
        return "neutral"

#generate system prompt based on state
def generate_system_prompt(state):
    if state == "puzzle":
        return (
            "You are now in puzzle mode. Offer engaging memory-boosting puzzles, "
            "such as word recall, fill-in-the-blanks, or simple logic puzzles and maintain continuity. "
            "Adjust the difficulty based on the user's sentiment, and make it fun and interactive but make sure that the puzzles are conversations and boost memory reinforcement.Try not to include math problems. Puzzles should be stritcly conversational."
        )
    return (
        "You are a supportive assistant designed for individuals with neurodegenerative diseases. "
        "Engage in empathetic and warm conversations, and respond thoughtfully to the user's input. "
        "After replying to three user messages or if the users mentions playing a game or puzzles, suggest a memory-boosting activity and mention clicking the puzzles button, if and only if the user is enthusiastic and willing to participate. Ensure your suggestions are natural and conversational whilst maintaining continuity."
        "Avoid being repetitive in your responses and keep the user engaged with meaningful conversation. Don't force the user to have a conversation if the user seems low and does not want to talk. In such cases, tell the user to have a good day and say bye."
    )

#generate puzzle prompt based on sentiment
def generate_question_prompt(sentiment):
    if sentiment == "negative":
        return "Generate a simple word recall puzzle with helpful hints for a disengaged user."
    elif sentiment == "neutral":
        return "Generate a medium-difficulty memory recall exercise with 2-3 words."
    elif sentiment == "positive":
        return "Generate a challenging multi-turn logic puzzle or word association game."

#unified GPT call function
def gpt_call(messages):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
    )
    return response.choices[0].message.content

#chatendpoint 
@app.post("/chat/")
async def chat(request: Request):
    data = await request.json()
    input_text = data.get("input_text", "")
    session_id = data.get("session_id", str(uuid.uuid4()))
    trigger = data.get("trigger", None)  #Detect trigger (puzzles button)

    session = get_user_session(session_id)

    try:
        #state is updated only on valid triggers
        if trigger == "puzzles" and session["current_state"] != "puzzle":
            session["current_state"] = "puzzle"
        elif input_text.lower() in ["exit puzzle", "back to chat"] and session["current_state"] != "chat":
            session["current_state"] = "chat"

        #log current state for debugging
        print(f"Current State: {session['current_state']}")

        #inject system prompt if and only if history is empty
        if session["current_state"] == "chat" and not session["history"]:
            session["history"].append({"role": "system", "content": generate_system_prompt("chat")})
        elif session["current_state"] == "puzzle" and not session["puzzle_history"]:
            session["puzzle_history"].append({"role": "system", "content": generate_system_prompt("puzzle")})

        #add user input to the appropriate history
        if session["current_state"] == "chat":
            session["history"].append({"role": "user", "content": input_text})
            messages = session["history"]
        elif session["current_state"] == "puzzle":
            session["puzzle_history"].append({"role": "user", "content": input_text})
            messages = session["puzzle_history"]

        #truncate history if it exceeds the limit and reinject the system prompt
        if len(messages) > MAX_HISTORY_LENGTH:
            system_prompt = generate_system_prompt(session["current_state"])
            messages = messages[-(MAX_HISTORY_LENGTH - 1):]
            messages.insert(0, {"role": "system", "content": system_prompt})

        #GPT response
        assistant_message = gpt_call(messages)

        #add assistant response to the appropriate history
        if session["current_state"] == "chat":
            session["history"].append({"role": "assistant", "content": assistant_message})
        elif session["current_state"] == "puzzle":
            session["puzzle_history"].append({"role": "assistant", "content": assistant_message})

        #log updated history
        print(f"Updated History ({session['current_state']}): {messages}")

        return {"response": assistant_message, "session_id": session_id}

    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return {"error": "An internal error occurred. Please try again."}

#puzzle generation endpoint
@app.post("/generate_puzzle/")
async def generate_puzzle(request: Request):
    data = await request.json()
    session_id = data.get("session_id", str(uuid.uuid4()))
    user_input = data.get("input_text", None)
    is_answer = data.get("is_answer", False)

    session = get_user_session(session_id)

    try:
        #validate input
        if not user_input or user_input.strip() == "":
            if is_answer:
                return {"response": "No answer provided. Please try again.", "session_id": session_id}
            else:
                return {"response": "No input detected. Please provide your input.", "session_id": session_id}

        #validate state and persist puzzle mode
        if session["current_state"] != "puzzle":
            session["current_state"] = "puzzle"

        #handle user answers
        if is_answer:
            expected_answer = session.get("expected_answer")
            if expected_answer and user_input.strip().lower() == expected_answer.strip().lower():
                session["expected_answer"] = None
                session["last_puzzle"] = None
                return {"response": "Correct! Here's the next puzzle.", "session_id": session_id}
            else:
                return {"response": "That's incorrect. Please try again.", "session_id": session_id}

        #generate a new puzzle
        if not session["puzzle_history"]:
            session["puzzle_history"].append({"role": "system", "content": generate_system_prompt("puzzle")})

        session["puzzle_history"].append({"role": "user", "content": user_input})

        #truncate puzzle history if it exceeds the limit and reinject the system prompt
        if len(session["puzzle_history"]) > MAX_HISTORY_LENGTH:
            system_prompt = generate_system_prompt("puzzle")
            session["puzzle_history"] = session["puzzle_history"][-(MAX_HISTORY_LENGTH - 1):]
            session["puzzle_history"].insert(0, {"role": "system", "content": system_prompt})

        print("Sending to GPT:", session["puzzle_history"])  #Debugging
        assistant_message = gpt_call(session["puzzle_history"])

        if "Answer:" in assistant_message:
            try:
                puzzle_text, expected_answer = assistant_message.split("Answer:", 1)
                session["last_puzzle"] = puzzle_text.strip()
                session["expected_answer"] = expected_answer.strip()
            except ValueError:
                session["last_puzzle"] = assistant_message
                session["expected_answer"] = None
        else:
            session["last_puzzle"] = assistant_message
            session["expected_answer"] = None

        session["puzzle_history"].append({"role": "assistant", "content": session["last_puzzle"]})

        return {"response": session["last_puzzle"], "session_id": session_id}

    except Exception as e:
        print(f"Error in generate_puzzle: {e}")
        return {"error": "An internal error occurred. Please try again."}

#voice processing endpoint
@app.post("/process_voice/")
async def process_voice(file: UploadFile):
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(file.file) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
        return {"text": text}
    except Exception as e:
        return {"error": "Failed to process voice input."}


#image processing endpoint with OCR
@app.post("/process_image/")
async def process_image(file: UploadFile):
    try:
        #open the uploaded image
        image = Image.open(file.file)
        
        #perform OCR on the image
        extracted_text = pytesseract.image_to_string(image)
        
        #return the extracted text
        return {
            "message": "Image processed successfully!",
            "extracted_text": extracted_text
        }
    except Exception as e:
        print(f"Error processing image: {e}")
        return {"error": "Failed to process image input."}

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from google import genai
import os
import json
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from tone import app as tone_app
from recommend import app as recommend_app
from performance import app as performance_app
from scrabble import app as scrabble_app
from pymongo import MongoClient

# -------- Load ENV --------
load_dotenv()

# -------- FastAPI --------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow React frontend
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Mount tone API --------
app.mount("/tone", tone_app)

# -------- Mount recommend API --------
app.mount("/recommend", recommend_app)

# -------- Mount performance API --------
app.mount("/performance", performance_app)

# -------- Gemini Client --------
client = genai.Client(
    api_key=os.getenv("GEMINI_KEY")
)

# -------- MongoDB Client --------
mongo_url = os.getenv("MONGO_URL")
if mongo_url:
    try:
        client_db = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        # Test the connection
        client_db.admin.command('ping')
        db = client_db["zhongwen"]
        users_collection = db["users"]
        USE_MONGO = True
        print("Connected to MongoDB")
    except Exception as e:
        print(f"MongoDB connection failed: {e}. Falling back to JSON storage.")
        USE_MONGO = False
else:
    USE_MONGO = False

if not USE_MONGO:
    # -------- User Store (JSON) --------
    USERS_FILE = Path(__file__).parent / "users.json"

    def load_users():
        if not USERS_FILE.exists():
            return {}
        try:
            return json.loads(USERS_FILE.read_text())
        except Exception:
            return {}

    def save_users(users):
        USERS_FILE.write_text(json.dumps(users, indent=2))


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


def verify_password(stored, password):
    try:
        salt, _ = stored.split("$", 1)
    except Exception:
        return False
    return hash_password(password, salt) == stored


# -------- JWT --------
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

security = HTTPBearer()

# -------- Pydantic Models --------
from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class SummaryCreate(BaseModel):
    source: str
    content: str

# -------- AI Tutor Logic --------
def tutor_ai(user_message, history=""):

    prompt = f"""
You are a friendly Chinese language tutor.
Explain concepts simply and kindly.
Respond in short sentences.

Conversation history:
{history}

Student said: {user_message}

Your reply rules:
- Correct Chinese if needed
- Explain meaning in English briefly
- Encourage the student
- Keep reply under 4 sentences

"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text

def summarize_key_points(content: str):
    prompt = f"""
You extract concise key points for media recommendations (dramas, movies, books).
Summarize in 1-2 sentences.
Only include preferences, genres, themes, titles, and dislikes.
If no media preferences are mentioned, reply: "No media preferences mentioned."
Do not include personal data.

Content:
{content}
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()


# -------- ROUTES --------

@app.get("/")
def home():
    return {"message": "Backend running 😊"}

@app.post("/register", response_model=Token)
def register(user: UserCreate):
    print(f"Registering user: {user.username}")
    if USE_MONGO:
        print("Using MongoDB")
        if users_collection.find_one({"username": user.username}):
            raise HTTPException(status_code=400, detail="Username already registered")
        
        hashed = hash_password(user.password)
        user_doc = {
            "username": user.username,
            "email": user.email,
            "password": hashed,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        print(f"Inserting user_doc: {user_doc}")
        users_collection.insert_one(user_doc)
        print("User inserted successfully")
    else:
        users = load_users()
        if user.username in users:
            raise HTTPException(status_code=400, detail="Username already registered")
        
        hashed = hash_password(user.password)
        users[user.username] = {
            "email": user.email,
            "password": hashed,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        save_users(users)
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
def login(user: UserLogin):
    if USE_MONGO:
        user_doc = users_collection.find_one({"username": user.username})
        if not user_doc or not verify_password(user_doc["password"], user.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")
    else:
        users = load_users()
        if user.username not in users or not verify_password(users[user.username]["password"], user.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
def read_users_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    username = verify_token(credentials.credentials)
    if USE_MONGO:
        user_doc = users_collection.find_one({"username": username})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = user_doc.copy()
        del user_data["_id"]
        del user_data["password"]
    else:
        users = load_users()
        if username not in users:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = users[username].copy()
        del user_data["password"]
    return user_data


@app.post("/chat")
def chat(data: dict):

    user_msg = data.get("message", "")
    history = data.get("history", "")

    try:
        reply = tutor_ai(
            user_message=user_msg,
            history=history
        )

        return {"reply": reply}

    except Exception as e:
        print("Tutor error:", e)
        return {
            "reply": "Tutor is temporarily unavailable. Please try again 😊"
        }


@app.get("/recommend/test")
def recommend_test():
    return {
        "recommend":
        "Practice saying ‘Nǐ hǎo’ (Hello) clearly with the third tone on hǎo."
    }

# Mount Scrabble game app
app.mount("/api/game", scrabble_app)

@app.post("/conversation/summary")
def store_conversation_summary(
    data: SummaryCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    username = verify_token(credentials.credentials)

    if not data.content or not data.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")

    summary = summarize_key_points(data.content)
    record = {
        "username": username,
        "source": data.source,
        "summary": summary,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    if USE_MONGO:
        summaries_collection = db["conversation_summaries"]
        summaries_collection.insert_one(record)
    else:
        summaries_file = Path(__file__).parent / "conversation_summaries.json"
        try:
            existing = json.loads(summaries_file.read_text()) if summaries_file.exists() else []
        except Exception:
            existing = []
        existing.append(record)
        summaries_file.write_text(json.dumps(existing, indent=2))

    return {"ok": True, "summary": summary}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

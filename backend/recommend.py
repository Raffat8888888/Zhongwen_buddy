from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import random
import os
import json
from jose import JWTError, jwt
from pymongo import MongoClient
from statistics import mean
from datetime import datetime, timezone

app = FastAPI()

security = HTTPBearer()
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"

mongo_url = os.getenv("MONGO_URL")
USE_MONGO = bool(mongo_url)
if USE_MONGO:
    try:
        client_db = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        client_db.admin.command('ping')
        db = client_db["zhongwen"]
        print("Connected to MongoDB in recommend module")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        USE_MONGO = False


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

class Questionnaire(BaseModel):
    genres: list[str]
    mood: str
    pace: str
    time_commitment: str


def _profile_store_path():
    return os.path.join(os.path.dirname(__file__), "recommendation_profiles.json")


def _load_profiles():
    path = _profile_store_path()
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_profiles(profiles: dict):
    path = _profile_store_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


def get_latest_questionnaire(username: str):
    if USE_MONGO:
        col = db.get_collection("recommendation_profiles")
        doc = col.find_one({"username": username}, sort=[("updated_at", -1)])
        return doc
    profiles = _load_profiles()
    return profiles.get(username)


def load_user_profile(username: str):
    try:
        path = os.path.join(os.path.dirname(__file__), "users.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(username, {})
    except Exception:
        return {}


def get_performance_stats(username: str):
    if USE_MONGO:
        col = db.get_collection("performance_users")
        doc = col.find_one({"username": username}, {"activities": 1})
        docs = doc.get("activities", []) if doc else []
        if not docs:
            legacy = db.get_collection("performance")
            docs = list(legacy.find({"username": username}, {"score": 1, "activity_type": 1}))
    else:
        path = os.path.join(os.path.dirname(__file__), "performance_store.json")
        try:
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                docs = [d for d in json.load(f) if d.get("username") == username]
        except Exception:
            return None
    if not docs:
        return None
    overall = mean(d.get("score", 0) for d in docs)
    by_activity = {}
    for d in docs:
        at = d.get("activity_type", "unknown")
        by_activity.setdefault(at, []).append(d.get("score", 0))
    summary = {k: float(mean(v)) for k, v in by_activity.items()}
    summary["overall_avg"] = float(overall)
    summary["count"] = len(docs)
    return summary


def get_learning_level(username: str):
    perf = get_performance_stats(username)
    if not perf or perf.get("overall_avg") is None:
        return "beginner"
    overall = perf.get("overall_avg", 0)
    if overall < 55:
        return "beginner"
    if overall < 75:
        return "intermediate"
    return "advanced"


def extract_summary_signals(summary_texts: list[str]):
    keywords = {
        "romance", "thriller", "mystery", "fantasy", "sci-fi", "historical",
        "comedy", "slice-of-life", "drama", "action", "family", "crime"
    }
    hits = set()
    for s in summary_texts:
        low = s.lower()
        for k in keywords:
            if k in low:
                hits.add(k)
    return hits


def get_recent_summaries(username: str, limit: int = 10):
    if USE_MONGO:
        col = db.get_collection("conversation_summaries")
        docs = list(col.find({"username": username}).sort("created_at", -1).limit(limit))
        return [d.get("summary", "") for d in docs if d.get("summary")]
    path = os.path.join(os.path.dirname(__file__), "conversation_summaries.json")
    try:
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            docs = json.load(f)
        user_docs = [d for d in docs if d.get("username") == username]
        user_docs = sorted(user_docs, key=lambda d: d.get("created_at", ""), reverse=True)
        return [d.get("summary", "") for d in user_docs[:limit] if d.get("summary")]
    except Exception:
        return []

def get_tone_stats(username: str):
    # Try Mongo first
    if USE_MONGO:
        col = db.get_collection("tone")
        docs = list(col.find({"username": username}, {"toneScore": 1}))
        if docs:
            scores = [d.get("toneScore", 0) for d in docs]
            return {"avg_tone": float(mean(scores)), "count": len(scores)}

    # Fallback to users.json fields if present
    profile = load_user_profile(username)
    tone_history = profile.get("tone_history") or profile.get("toneScores")
    if tone_history and isinstance(tone_history, list):
        return {"avg_tone": float(mean(tone_history)), "count": len(tone_history)}

    return None


@app.get("/")
def recommend_home():
    return {"message": "Recommendation module running"}

@app.post("/questionnaire")
def save_questionnaire(
    data: Questionnaire,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    username = verify_token(credentials.credentials)
    record = {
        "username": username,
        "genres": data.genres,
        "mood": data.mood,
        "pace": data.pace,
        "time_commitment": data.time_commitment,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    if USE_MONGO:
        col = db.get_collection("recommendation_profiles")
        col.update_one({"username": username}, {"$set": record}, upsert=True)
    else:
        profiles = _load_profiles()
        profiles[username] = record
        _save_profiles(profiles)
    return {"ok": True}


@app.get("/get_old")
def get_recommendation(credentials: HTTPAuthorizationCredentials = Depends(security)):
    username = verify_token(credentials.credentials)

    profile = load_user_profile(username)
    likes = profile.get("likes", [])
    dislikes = profile.get("dislikes", [])

    perf = get_performance_stats(username)
    tone = get_tone_stats(username)

    # Base recommendation pool
    pool = [
        {"id": "vocab_basic", "text": "Practice HSK Level 1 vocabulary with flashcards", "tags": ["vocab"]},
        {"id": "tones_drill", "text": "Work on your tones - record yourself saying 'mā má mǎ mà'", "tags": ["tone"]},
        {"id": "radicals", "text": "Learn radicals: start with 人 (rén) meaning person", "tags": ["reading", "radical"]},
        {"id": "writing_chars", "text": "Practice writing characters: begin with 一 (yī)", "tags": ["writing"]},
        {"id": "listen_podcast", "text": "Listen to Chinese podcasts for natural pronunciation", "tags": ["listening"]},
        {"id": "speaking_ex", "text": "Try speaking exercises: describe your daily routine", "tags": ["speaking"]},
        {"id": "measure_words", "text": "Study measure words: use 个 (gè) for general counting", "tags": ["grammar"]},
        {"id": "reading_stories", "text": "Practice reading: start with simple children's stories", "tags": ["reading"]},
        {"id": "phrases", "text": "Learn common phrases: '谢谢' (xièxie) thank you", "tags": ["phrases"]},
        {"id": "scrabble_practice", "text": "Play Scrabble-style character matching to build recall", "tags": ["game", "scrabble"]}
    ]

    scores = {p["id"]: 0.0 for p in pool}

    # Apply performance-driven adjustments
    if perf:
        overall = perf.get("overall_avg", 0)
        # If overall is low, favor fundamentals
        if overall < 60:
            for p in pool:
                if "vocab" in p["tags"] or "writing" in p["tags"] or "grammar" in p["tags"]:
                    scores[p["id"]] += 2.0
        else:
            for p in pool:
                scores[p["id"]] += 0.5

    # Tone adjustments
    if tone:
        avg_tone = tone.get("avg_tone", 0)
        if avg_tone < 65:
            scores["tones_drill"] += 3.0
        else:
            scores["listen_podcast"] += 1.0

    # Likes/dislikes influence
    for like in likes:
        low = like.lower()
        if "speak" in low or "speaking" in low:
            scores["speaking_ex"] += 2.0
        if "game" in low or "scrabble" in low:
            scores["scrabble_practice"] += 2.0
        if "podcast" in low or "listening" in low:
            scores["listen_podcast"] += 1.5
        if "writing" in low:
            scores["writing_chars"] += 1.5

    for dislike in dislikes:
        dlow = dislike.lower()
        if "game" in dlow or "scrabble" in dlow:
            scores["scrabble_practice"] -= 2.0

    # Small randomization and final scoring
    for p in pool:
        scores[p["id"]] += random.random() * 0.5

    # Select top 3 recommendations
    ranked = sorted(pool, key=lambda x: scores[x["id"]], reverse=True)
    chosen = ranked[:3]

    reasons = []
    if perf:
        reasons.append(f"performance_overall_avg={perf.get('overall_avg')}")
    if tone:
        reasons.append(f"avg_tone={tone.get('avg_tone')}")
    if likes:
        reasons.append(f"likes={likes}")

    return {
        "username": username,
        "recommendations": [
            {"text": c["text"], "id": c["id"], "tags": c["tags"]} for c in chosen
        ],
        "explain": reasons,
        "type": "personalized"
    }


@app.get("/get")
def get_media_recommendation(limit: int = 6, credentials: HTTPAuthorizationCredentials = Depends(security)):
    username = verify_token(credentials.credentials)
    limit = max(1, min(limit, 20))

    questionnaire = get_latest_questionnaire(username) or {}
    genres = set([g.lower() for g in questionnaire.get("genres", [])])
    mood = (questionnaire.get("mood") or "").lower()
    pace = (questionnaire.get("pace") or "").lower()
    time_commitment = (questionnaire.get("time_commitment") or "").lower()

    level = get_learning_level(username)
    summary_signals = extract_summary_signals(get_recent_summaries(username))

    pool = [
        {"id": "d1", "type": "drama", "title": "The Untamed", "genres": ["fantasy", "historical"], "pace": "slow", "time": "long", "levels": ["intermediate", "advanced"]},
        {"id": "d2", "type": "drama", "title": "Reset", "genres": ["sci-fi", "thriller"], "pace": "fast", "time": "short", "levels": ["intermediate", "advanced"]},
        {"id": "d3", "type": "drama", "title": "Nirvana in Fire", "genres": ["historical", "drama"], "pace": "slow", "time": "long", "levels": ["intermediate", "advanced"]},
        {"id": "d4", "type": "drama", "title": "Story of Yanxi Palace", "genres": ["historical", "drama"], "pace": "balanced", "time": "long", "levels": ["beginner", "intermediate", "advanced"]},
        {"id": "d5", "type": "drama", "title": "Joy of Life", "genres": ["historical", "comedy"], "pace": "balanced", "time": "long", "levels": ["intermediate", "advanced"]},
        {"id": "m1", "type": "movie", "title": "Crouching Tiger, Hidden Dragon", "genres": ["action", "historical"], "pace": "balanced", "time": "short", "levels": ["intermediate", "advanced"]},
        {"id": "m2", "type": "movie", "title": "Farewell My Concubine", "genres": ["drama", "historical"], "pace": "slow", "time": "long", "levels": ["intermediate", "advanced"]},
        {"id": "m3", "type": "movie", "title": "Infernal Affairs", "genres": ["crime", "thriller"], "pace": "fast", "time": "short", "levels": ["intermediate", "advanced"]},
        {"id": "m4", "type": "movie", "title": "Kung Fu Hustle", "genres": ["action", "comedy"], "pace": "fast", "time": "short", "levels": ["beginner", "intermediate"]},
        {"id": "m5", "type": "movie", "title": "Hero", "genres": ["action", "historical"], "pace": "balanced", "time": "short", "levels": ["intermediate", "advanced"]},
        {"id": "b1", "type": "book", "title": "The Three-Body Problem", "genres": ["sci-fi"], "pace": "slow", "time": "long", "levels": ["intermediate", "advanced"]},
        {"id": "b2", "type": "book", "title": "To Live", "genres": ["drama", "historical"], "pace": "slow", "time": "medium", "levels": ["intermediate", "advanced"]},
        {"id": "b3", "type": "book", "title": "Red Sorghum", "genres": ["drama", "historical"], "pace": "balanced", "time": "medium", "levels": ["intermediate", "advanced"]},
    ]

    mood_to_genres = {
        "cozy": {"slice-of-life", "romance", "family", "drama"},
        "balanced": {"drama", "historical", "fantasy"},
        "tense": {"thriller", "crime", "action"}
    }

    scores = {p["id"]: 0.0 for p in pool}
    for p in pool:
        if level in p["levels"]:
            scores[p["id"]] += 2.0
        if genres and any(g in p["genres"] for g in genres):
            scores[p["id"]] += 3.0
        if mood and mood in mood_to_genres and any(g in p["genres"] for g in mood_to_genres[mood]):
            scores[p["id"]] += 2.0
        if pace and pace == p["pace"]:
            scores[p["id"]] += 1.5
        if time_commitment and time_commitment == p["time"]:
            scores[p["id"]] += 1.5
        if summary_signals and any(g in p["genres"] for g in summary_signals):
            scores[p["id"]] += 1.5
        scores[p["id"]] += random.random() * 0.05

    def matches_preferences(item):
        if genres and not any(g in item["genres"] for g in genres):
            return False
        if pace and pace != item["pace"]:
            return False
        if time_commitment and time_commitment != item["time"]:
            return False
        if mood and mood in mood_to_genres and not any(g in item["genres"] for g in mood_to_genres[mood]):
            return False
        return True

    filtered = [p for p in pool if matches_preferences(p)] or pool
    ranked = sorted(filtered, key=lambda x: scores[x["id"]], reverse=True)
    chosen = ranked[:limit]

    return {
        "username": username,
        "learning_level": level,
        "recommendations": [
            {
                "id": c["id"],
                "title": c["title"],
                "type": c["type"],
                "genres": c["genres"],
                "pace": c["pace"],
                "time_commitment": c["time"]
            } for c in chosen
        ],
        "type": "personalized"
    }

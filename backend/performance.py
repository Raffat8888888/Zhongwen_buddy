from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timezone
import os
from jose import JWTError, jwt
from pymongo import MongoClient
import json

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
        print("Connected to MongoDB in performance module")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        USE_MONGO = False

# Store all performance data for a user in one document
PERF_COLLECTION = "performance_users"
LEGACY_COLLECTION = "performance"

if USE_MONGO:
    try:
        db.get_collection(PERF_COLLECTION).create_index("username")
    except Exception as e:
        print(f"Index creation failed: {e}")

# File fallback when MongoDB not available
import threading
_store_lock = threading.Lock()
STORE_PATH = os.path.join(os.path.dirname(__file__), "performance_store.json")

def _load_store():
    try:
        if not os.path.exists(STORE_PATH):
            return []
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _append_store(doc: dict):
    with _store_lock:
        data = _load_store()
        data.append(doc)
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

class PerformanceData(BaseModel):
    activity_type: str  # e.g., "chat", "tone_practice", "scrabble_game"
    score: float
    details: dict = {}  # Additional data like time_taken, accuracy, etc.


def _get_user_activities_mongo(username: str):
    """Return list of activity docs for a user from Mongo, with legacy fallback."""
    col = db.get_collection(PERF_COLLECTION)
    doc = col.find_one({"username": username}, {"activities": 1})
    if doc and isinstance(doc.get("activities"), list):
        return doc["activities"]

    # Legacy fallback: read from old collection if present
    legacy = db.get_collection(LEGACY_COLLECTION)
    docs = list(legacy.find({"username": username}, {"_id": 0, "username": 0}))
    if docs:
        return docs
    return []


def _normalize_score(value) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return score


def _migrate_legacy_to_user_docs():
    legacy = db.get_collection(LEGACY_COLLECTION)
    target = db.get_collection(PERF_COLLECTION)
    migrated = 0

    cursor = legacy.find({}, {"_id": 0})
    for doc in cursor:
        username = doc.get("username")
        if not username:
            continue
        performance_doc = {
            "activity_type": doc.get("activity_type"),
            "score": _normalize_score(doc.get("score")),
            "details": doc.get("details", {}),
            "timestamp": doc.get("timestamp")
        }
        target.update_one(
            {"username": username},
            {
                "$setOnInsert": {"username": username, "created_at": datetime.now(timezone.utc).isoformat()},
                "$push": {"activities": {"$each": [performance_doc]}},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            },
            upsert=True
        )
        migrated += 1

    return migrated

@app.get("/")
def performance_home():
    return {"message": "Performance tracking module running"}

@app.post("/record")
def record_performance(data: PerformanceData, credentials: HTTPAuthorizationCredentials = Depends(security)):
    username = verify_token(credentials.credentials)

    score_value = _normalize_score(data.score)

    performance_doc = {
        "activity_type": data.activity_type,
        "score": score_value,
        "details": data.details,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if USE_MONGO:
        performance_collection = db.get_collection(PERF_COLLECTION)
        result = performance_collection.update_one(
            {"username": username},
            {
                "$setOnInsert": {"username": username, "created_at": datetime.now(timezone.utc).isoformat()},
                "$push": {
                    "activities": {
                        "$each": [performance_doc],
                        "$slice": -500
                    }
                },
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            },
            upsert=True
        )
        return {"message": "Performance recorded", "matched": result.matched_count, "upserted": bool(result.upserted_id)}
    else:
        # Fallback to file store
        try:
            performance_doc["username"] = username
            _append_store(performance_doc)
            return {"message": "Performance recorded (file store)", "id": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to store performance: {e}")

@app.get("/stats")
def get_performance_stats(credentials: HTTPAuthorizationCredentials = Depends(security)):
    username = verify_token(credentials.credentials)

    if USE_MONGO:
        activities = _get_user_activities_mongo(username)
        if not activities:
            return {"stats": [], "total_activities": 0}

        by_activity = {}
        for d in activities:
            at = d.get("activity_type", "unknown")
            by_activity.setdefault(at, []).append(d.get("score", 0))

        stats = []
        for k, v in by_activity.items():
            stats.append({"_id": k, "avg_score": float(sum(v) / len(v)), "count": len(v), "best_score": max(v)})

        return {"stats": stats, "total_activities": sum(s["count"] for s in stats)}
    else:
        # Read from file store
        docs = _load_store()
        user_docs = [d for d in docs if d.get("username") == username]
        if not user_docs:
            return {"stats": [], "total_activities": 0}

        by_activity = {}
        for d in user_docs:
            at = d.get("activity_type", "unknown")
            by_activity.setdefault(at, []).append(d.get("score", 0))

        stats = []
        for k, v in by_activity.items():
            stats.append({"_id": k, "avg_score": float(sum(v) / len(v)), "count": len(v), "best_score": max(v)})

        return {"stats": stats, "total_activities": len(user_docs)}


@app.get("/level")
def get_learning_level(credentials: HTTPAuthorizationCredentials = Depends(security)):
    username = verify_token(credentials.credentials)

    overall = None
    if USE_MONGO:
        activities = _get_user_activities_mongo(username)
        if activities:
            overall = sum(d.get("score", 0) for d in activities) / len(activities)
    else:
        docs = _load_store()
        user_docs = [d for d in docs if d.get("username") == username]
        if user_docs:
            overall = sum(d.get("score", 0) for d in user_docs) / len(user_docs)

    if overall is None:
        return {"level": "beginner", "overall_avg": None}
    if overall < 55:
        return {"level": "beginner", "overall_avg": overall}
    if overall < 75:
        return {"level": "intermediate", "overall_avg": overall}
    return {"level": "advanced", "overall_avg": overall}


@app.get("/history")
def get_performance_history(limit: int = 30, credentials: HTTPAuthorizationCredentials = Depends(security)):
    username = verify_token(credentials.credentials)
    limit = max(1, min(limit, 200))

    if USE_MONGO:
        activities = _get_user_activities_mongo(username)
        if not activities:
            return {"history": []}
        def _ts(d):
            try:
                return datetime.fromisoformat(d.get("timestamp", ""))
            except Exception:
                return datetime.min
        activities_sorted = sorted(activities, key=_ts, reverse=True)
        trimmed = []
        for d in activities_sorted[:limit]:
            score_value = _normalize_score(d.get("score", 0))
            trimmed.append({
                "activity_type": d.get("activity_type"),
                "score": score_value,
                "details": d.get("details", {}),
                "timestamp": d.get("timestamp")
            })
        return {"history": trimmed}
    else:
        docs = _load_store()
        user_docs = [d for d in docs if d.get("username") == username]
        if not user_docs:
            return {"history": []}

        def _ts(d):
            try:
                return datetime.fromisoformat(d.get("timestamp", ""))
            except Exception:
                return datetime.min

        activities_sorted = sorted(user_docs, key=_ts, reverse=True)
        trimmed = []
        for d in activities_sorted[:limit]:
            score_value = _normalize_score(d.get("score", 0))
            trimmed.append({
                "activity_type": d.get("activity_type"),
                "score": score_value,
                "details": d.get("details", {}),
                "timestamp": d.get("timestamp")
            })
        return {"history": trimmed}


@app.post("/migrate")
def migrate_legacy(credentials: HTTPAuthorizationCredentials = Depends(security)):
    verify_token(credentials.credentials)
    if not USE_MONGO:
        raise HTTPException(status_code=500, detail="MongoDB not available")
    migrated = _migrate_legacy_to_user_docs()
    return {"migrated": migrated}

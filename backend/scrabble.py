from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple
import random
import os
from jose import JWTError, jwt
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

load_dotenv()
try:
    from .game_logic import create_level_tiles, validate_sentence_order, calculate_level_stars
except Exception:
    from game_logic import create_level_tiles, validate_sentence_order, calculate_level_stars
from fastapi import APIRouter


app = FastAPI()

# Create a router (mounted under `/api/game` by main.py)
router = APIRouter()

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
        print("Connected to MongoDB in scrabble module")
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

class Tile(BaseModel):
    pinyin: str
    hanyu: str
    english: str
    points: int
    id: Optional[str] = None

class SentenceLevel(BaseModel):
    level: int
    phase: int
    sentence_length: int
    sentence: List[Dict]  # Each dict: {hanyu, pinyin, english, role}
    available_tiles: List[Tile]
    example_english: str
    show_english: bool
    show_verb_hint: bool

# ==================== LEVEL DATA ====================
# 25 levels divided into 5 phases
# Phase 1 (Levels 1-5): Single words
# Phase 2 (Levels 6-10): 2-word sentences (Subject + Verb)
# Phase 3 (Levels 11-15): 3-word sentences (Subject + Verb + Object)
# Phase 4 (Levels 16-20): Sentence variation (different word orders, tenses)
# Phase 5 (Levels 21-25): Reduced hints (hidden English, increased difficulty)

LEVEL_SENTENCES = [
    # Phase 1: Single words (1 tile)
    {"level": 1, "phase": 1, "tiles": [{"hanyu": "我", "pinyin": "wǒ", "english": "I", "role": "subject"}], "example": "I (myself)"},
    {"level": 2, "phase": 1, "tiles": [{"hanyu": "吃", "pinyin": "chī", "english": "eat", "role": "verb"}], "example": "eat"},
    {"level": 3, "phase": 1, "tiles": [{"hanyu": "有", "pinyin": "yǒu", "english": "have", "role": "verb"}], "example": "have"},
    {"level": 4, "phase": 1, "tiles": [{"hanyu": "好", "pinyin": "hǎo", "english": "good", "role": "adjective"}], "example": "good"},
    {"level": 5, "phase": 1, "tiles": [{"hanyu": "人", "pinyin": "rén", "english": "person", "role": "noun"}], "example": "person"},
    
    # Phase 2: 2-word sentences (Subject + Verb)
    {"level": 6, "phase": 2, "tiles": [{"hanyu": "我", "pinyin": "wǒ", "english": "I", "role": "subject"}, {"hanyu": "吃", "pinyin": "chī", "english": "eat", "role": "verb"}], "example": "I eat"},
    {"level": 7, "phase": 2, "tiles": [{"hanyu": "他", "pinyin": "tā", "english": "he", "role": "subject"}, {"hanyu": "有", "pinyin": "yǒu", "english": "have", "role": "verb"}], "example": "He has"},
    {"level": 8, "phase": 2, "tiles": [{"hanyu": "她", "pinyin": "tā", "english": "she", "role": "subject"}, {"hanyu": "好", "pinyin": "hǎo", "english": "good", "role": "adjective"}], "example": "She is good"},
    {"level": 9, "phase": 2, "tiles": [{"hanyu": "你", "pinyin": "nǐ", "english": "you", "role": "subject"}, {"hanyu": "吃", "pinyin": "chī", "english": "eat", "role": "verb"}], "example": "You eat"},
    {"level": 10, "phase": 2, "tiles": [{"hanyu": "人", "pinyin": "rén", "english": "person", "role": "subject"}, {"hanyu": "有", "pinyin": "yǒu", "english": "have", "role": "verb"}], "example": "Person has"},
    
    # Phase 3: 3-word sentences (Subject + Verb + Object)
    {"level": 11, "phase": 3, "tiles": [{"hanyu": "我", "pinyin": "wǒ", "english": "I", "role": "subject"}, {"hanyu": "吃", "pinyin": "chī", "english": "eat", "role": "verb"}, {"hanyu": "饭", "pinyin": "fàn", "english": "rice", "role": "object"}], "example": "I eat rice"},
    {"level": 12, "phase": 3, "tiles": [{"hanyu": "他", "pinyin": "tā", "english": "he", "role": "subject"}, {"hanyu": "有", "pinyin": "yǒu", "english": "have", "role": "verb"}, {"hanyu": "书", "pinyin": "shū", "english": "book", "role": "object"}], "example": "He has a book"},
    {"level": 13, "phase": 3, "tiles": [{"hanyu": "你", "pinyin": "nǐ", "english": "you", "role": "subject"}, {"hanyu": "看", "pinyin": "kàn", "english": "look", "role": "verb"}, {"hanyu": "我", "pinyin": "wǒ", "english": "me", "role": "object"}], "example": "You look at me"},
    {"level": 14, "phase": 3, "tiles": [{"hanyu": "她", "pinyin": "tā", "english": "she", "role": "subject"}, {"hanyu": "喜欢", "pinyin": "xǐhuān", "english": "like", "role": "verb"}, {"hanyu": "茶", "pinyin": "chá", "english": "tea", "role": "object"}], "example": "She likes tea"},
    {"level": 15, "phase": 3, "tiles": [{"hanyu": "人", "pinyin": "rén", "english": "person", "role": "subject"}, {"hanyu": "说", "pinyin": "shuō", "english": "speak", "role": "verb"}, {"hanyu": "话", "pinyin": "huà", "english": "words", "role": "object"}], "example": "People speak words"},
    
    # Phase 4: Sentence variation (different structures, no English hints)
    {"level": 16, "phase": 4, "tiles": [{"hanyu": "我", "pinyin": "wǒ", "english": "I", "role": "subject"}, {"hanyu": "喜欢", "pinyin": "xǐhuān", "english": "like", "role": "verb"}, {"hanyu": "苹果", "pinyin": "píngguǒ", "english": "apple", "role": "object"}], "example": "I like apples"},
    {"level": 17, "phase": 4, "tiles": [{"hanyu": "他", "pinyin": "tā", "english": "he", "role": "subject"}, {"hanyu": "学习", "pinyin": "xuéxí", "english": "study", "role": "verb"}, {"hanyu": "中文", "pinyin": "zhōngwén", "english": "Chinese", "role": "object"}], "example": "He studies Chinese"},
    {"level": 18, "phase": 4, "tiles": [{"hanyu": "你", "pinyin": "nǐ", "english": "you", "role": "subject"}, {"hanyu": "买", "pinyin": "mǎi", "english": "buy", "role": "verb"}, {"hanyu": "水", "pinyin": "shuǐ", "english": "water", "role": "object"}], "example": "You buy water"},
    {"level": 19, "phase": 4, "tiles": [{"hanyu": "她", "pinyin": "tā", "english": "she", "role": "subject"}, {"hanyu": "做", "pinyin": "zuò", "english": "make", "role": "verb"}, {"hanyu": "饭", "pinyin": "fàn", "english": "rice", "role": "object"}], "example": "She makes rice"},
    {"level": 20, "phase": 4, "tiles": [{"hanyu": "我们", "pinyin": "wǒmen", "english": "we", "role": "subject"}, {"hanyu": "去", "pinyin": "qù", "english": "go", "role": "verb"}, {"hanyu": "学校", "pinyin": "xuéxiào", "english": "school", "role": "object"}], "example": "We go to school"},
    
    # Phase 5: Reduced hints (most difficult, minimal English, complex grammar)
    {"level": 21, "phase": 5, "tiles": [{"hanyu": "他们", "pinyin": "tāmen", "english": "they", "role": "subject"}, {"hanyu": "不", "pinyin": "bù", "english": "not", "role": "negation"}, {"hanyu": "喜欢", "pinyin": "xǐhuān", "english": "like", "role": "verb"}], "example": "They don't like"},
    {"level": 22, "phase": 5, "tiles": [{"hanyu": "我", "pinyin": "wǒ", "english": "I", "role": "subject"}, {"hanyu": "已经", "pinyin": "yǐjīng", "english": "already", "role": "adverb"}, {"hanyu": "学过", "pinyin": "xuéguò", "english": "studied", "role": "verb"}], "example": "I already studied"},
    {"level": 23, "phase": 5, "tiles": [{"hanyu": "你", "pinyin": "nǐ", "english": "you", "role": "subject"}, {"hanyu": "会", "pinyin": "huì", "english": "can", "role": "auxiliary"}, {"hanyu": "说", "pinyin": "shuō", "english": "speak", "role": "verb"}], "example": "You can speak"},
    {"level": 24, "phase": 5, "tiles": [{"hanyu": "她", "pinyin": "tā", "english": "she", "role": "subject"}, {"hanyu": "正在", "pinyin": "zhèngzài", "english": "currently", "role": "adverb"}, {"hanyu": "看", "pinyin": "kàn", "english": "watch", "role": "verb"}], "example": "She is currently watching"},
    {"level": 25, "phase": 5, "tiles": [{"hanyu": "我们", "pinyin": "wǒmen", "english": "we", "role": "subject"}, {"hanyu": "应该", "pinyin": "yīnggāi", "english": "should", "role": "auxiliary"}, {"hanyu": "去", "pinyin": "qù", "english": "go", "role": "verb"}], "example": "We should go"},
]

def create_level_tiles(level_num: int) -> Tuple[List[Dict], List[Dict], bool, bool]:
    """
    Get tiles and configuration for a specific level.
    Returns: (sentence_tiles, available_tiles_shuffled, show_english, show_verb_hint)
    """
    level_data = LEVEL_SENTENCES[level_num - 1]
    phase = level_data["phase"]
    tiles = level_data["tiles"]
    
    # Difficulty scaling based on phase
    # Keep English hidden by default so the hint is meaningful.
    show_english = False
    show_verb_hint = phase <= 2  # Show verb hints in phases 1-2
    
    # Add extra shuffle tiles for confusion
    available_tiles = tiles.copy()
    if phase >= 2:
        # Add 1-2 distractor tiles
        num_distractors = min(phase - 1, 2)
        distractor_tiles = get_distractor_tiles(level_num, num_distractors)
        available_tiles.extend(distractor_tiles)
    
    random.shuffle(available_tiles)
    return tiles, available_tiles, show_english, show_verb_hint

def get_distractor_tiles(level_num: int, count: int) -> List[Dict]:
    """Get random distractor tiles to increase difficulty."""
    all_possible_tiles = [
        {"hanyu": "是", "pinyin": "shì", "english": "is", "role": "verb"},
        {"hanyu": "的", "pinyin": "de", "english": "of", "role": "particle"},
        {"hanyu": "在", "pinyin": "zài", "english": "at", "role": "preposition"},
        {"hanyu": "和", "pinyin": "hé", "english": "and", "role": "conjunction"},
        {"hanyu": "一", "pinyin": "yī", "english": "one", "role": "number"},
        {"hanyu": "大", "pinyin": "dà", "english": "big", "role": "adjective"},
        {"hanyu": "小", "pinyin": "xiǎo", "english": "small", "role": "adjective"},
        {"hanyu": "生", "pinyin": "shēng", "english": "birth", "role": "noun"},
    ]
    selected = random.sample(all_possible_tiles, min(count, len(all_possible_tiles)))
    return selected

# ==================== VALIDATION ====================
def validate_sentence_order(selected_tiles: List[Dict], correct_order: List[Dict]) -> bool:
    """
    Rule-based validation: Check if selected tiles match the correct order.
    Tiles must be in left-to-right order: Subject → Verb → Object
    """
    if len(selected_tiles) != len(correct_order):
        return False
    
    for i, selected in enumerate(selected_tiles):
        if selected.get("hanyu") != correct_order[i].get("hanyu"):
            return False
    
    return True

def calculate_level_stars(level_num: int, first_try: bool, used_hints: int) -> int:
    """
    Calculate stars earned for completing a level.
    Max 3 stars: 1 base + 1 if first try + 1 if no hints used
    """
    stars = 1  # Base star
    if first_try:
        stars += 1
    if used_hints == 0:
        stars += 1
    return min(stars, 3)

# ==================== GAME STATE ====================
@app.get("/")
def scrabble_home():
    return {"message": "Chinese Sentence Scrabble - 25 Levels for Beginners"}

@router.post("/new")
def start_new_game(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Start a new game at level 1."""
    username = verify_token(credentials.credentials)
    
    level_num = 1
    sentence_tiles, available_tiles, show_english, show_verb_hint = create_level_tiles(level_num)
    level_data = LEVEL_SENTENCES[level_num - 1]
    
    game_state = {
        "username": username,
        "level": level_num,
        "phase": level_data["phase"],
        "current_stars": 0,
        "total_stars": 0,
        "correct_sentence": sentence_tiles,
        "available_tiles": available_tiles,
        "show_english": show_english,
        "show_verb_hint": show_verb_hint,
        "example": level_data["example"],
        "attempts": 0,
        "hints_used": 0,
        "completed_levels": [],
        "level_stars": {}  # { level: stars_count }
    }
    
    if USE_MONGO:
        games_collection = db["scrabble_games"]
        result = games_collection.insert_one(game_state)
        game_id = str(result.inserted_id)
    else:
        game_id = f"game_{random.randint(100000, 999999)}"
    
    return {
        "game_id": game_id,
        "level": level_num,
        "phase": level_data["phase"],
        "available_tiles": available_tiles,
        "show_english": show_english,
        "show_verb_hint": show_verb_hint,
        "example": level_data["example"],
        "current_stars": 0,
        "total_stars": 0
    }

@app.get("/{game_id}")
def get_game_state(game_id: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current game state."""
    username = verify_token(credentials.credentials)
    
    if not USE_MONGO:
        raise HTTPException(status_code=500, detail="Database not available")
    
    games_collection = db["scrabble_games"]
    game = games_collection.find_one({"_id": ObjectId(game_id), "username": username})
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    level = game["level"]
    level_data = LEVEL_SENTENCES[level - 1]
    
    return {
        "level": level,
        "phase": game["phase"],
        "available_tiles": game["available_tiles"],
        "show_english": game["show_english"],
        "show_verb_hint": game["show_verb_hint"],
        "example": game["example"],
        "current_stars": game["current_stars"],
        "total_stars": game["total_stars"],
        "completed_levels": game["completed_levels"],
        "level_stars": game.get("level_stars", {})
    }

@app.post("/{game_id}/submit")
def submit_sentence(game_id: str, submission: Dict, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Submit a sentence for validation.
    submission = { "tiles": [{"hanyu": "...", ...}, ...] }
    """
    username = verify_token(credentials.credentials)
    
    if not USE_MONGO:
        raise HTTPException(status_code=500, detail="Database not available")
    
    games_collection = db["scrabble_games"]
    game = games_collection.find_one({"_id": ObjectId(game_id), "username": username})
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    submitted_tiles = submission.get("tiles", [])
    correct_tiles = game["correct_sentence"]
    attempts = game.get("attempts", 0) + 1
    hints_used = game.get("hints_used", 0)
    
    # Validate sentence
    is_correct = validate_sentence_order(submitted_tiles, correct_tiles)
    
    if is_correct:
        # Calculate stars (first try = no attempts before this one)
        first_try = attempts == 1
        stars_earned = calculate_level_stars(game["level"], first_try, hints_used)
        
        new_total_stars = game["total_stars"] + stars_earned
        level_stars = game.get("level_stars", {})
        level_stars[str(game["level"])] = stars_earned
        
        # Check if all 25 levels completed
        completed = game.get("completed_levels", []) + [game["level"]]
        next_level = game["level"] + 1
        is_game_complete = next_level > 25
        
        # If not complete, load next level
        if not is_game_complete:
            next_sentence_tiles, next_available_tiles, next_show_english, next_show_verb_hint = create_level_tiles(next_level)
            next_level_data = LEVEL_SENTENCES[next_level - 1]
            
            games_collection.update_one(
                {"_id": ObjectId(game_id)},
                {"$set": {
                    "level": next_level,
                    "phase": next_level_data["phase"],
                    "current_stars": stars_earned,
                    "total_stars": new_total_stars,
                    "correct_sentence": next_sentence_tiles,
                    "available_tiles": next_available_tiles,
                    "show_english": next_show_english,
                    "show_verb_hint": next_show_verb_hint,
                    "example": next_level_data["example"],
                    "attempts": 0,
                    "hints_used": 0,
                    "completed_levels": completed,
                    "level_stars": level_stars
                }}
            )
        else:
            games_collection.update_one(
                {"_id": ObjectId(game_id)},
                {"$set": {
                    "completed_levels": completed,
                    "level_stars": level_stars,
                    "total_stars": new_total_stars,
                    "game_complete": True
                }}
            )
        
        return {
            "correct": True,
            "stars_earned": stars_earned,
            "total_stars": new_total_stars,
            "next_level": next_level if not is_game_complete else None,
            "game_complete": is_game_complete
        }
    else:
        # Incorrect attempt
        games_collection.update_one(
            {"_id": ObjectId(game_id)},
            {"$set": {"attempts": attempts}}
        )
        
        return {
            "correct": False,
            "attempts": attempts,
            "message": "Incorrect order. Try again! Remember: Subject → Verb → Object"
        }

@app.post("/{game_id}/hint")
def use_hint(game_id: str, hint_type: Dict, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Use a star-based hint.
    hint_type = { "type": "english" | "verb" | "auto_place" | "example", "tile_index": optional }
    Costs: english=1, verb=1, auto_place=2, example=1
    """
    username = verify_token(credentials.credentials)
    
    if not USE_MONGO:
        raise HTTPException(status_code=500, detail="Database not available")
    
    games_collection = db["scrabble_games"]
    game = games_collection.find_one({"_id": ObjectId(game_id), "username": username})
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    hint_category = hint_type.get("type")
    tile_index = hint_type.get("tile_index")
    
    current_stars = game["current_stars"]
    hint_cost = 0
    hint_result = {}
    
    # Hint costs
    if hint_category == "english":
        hint_cost = 1
        hint_result = {"type": "english", "shown": True}
    elif hint_category == "verb":
        hint_cost = 1
        # Find verb position in correct sentence
        verb_pos = None
        for i, tile in enumerate(game["correct_sentence"]):
            if tile.get("role") == "verb":
                verb_pos = i
                break
        hint_result = {"type": "verb", "position": verb_pos}
    elif hint_category == "auto_place":
        hint_cost = 2
        if tile_index is not None:
            hint_result = {"type": "auto_place", "tile_index": tile_index, "correct_position": tile_index}
    elif hint_category == "example":
        hint_cost = 1
        hint_result = {"type": "example", "example": game["example"]}
    
    # Check if enough stars
    if current_stars < hint_cost:
        return {
            "success": False,
            "message": f"Not enough stars. Need {hint_cost}, have {current_stars}"
        }
    
    # Deduct stars and increment hints_used counter
    new_stars = current_stars - hint_cost
    new_hints_used = game.get("hints_used", 0) + 1
    
    games_collection.update_one(
        {"_id": ObjectId(game_id)},
        {"$set": {
            "current_stars": new_stars,
            "hints_used": new_hints_used
        }}
    )
    
    return {
        "success": True,
        "hint": hint_result,
        "remaining_stars": new_stars
    }

@app.post("/{game_id}/level/{level_num}")
def jump_to_level(game_id: str, level_num: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Jump to a specific level (for testing or level selection)."""
    username = verify_token(credentials.credentials)
    
    if level_num < 1 or level_num > 25:
        raise HTTPException(status_code=400, detail="Level must be between 1 and 25")
    
    if not USE_MONGO:
        raise HTTPException(status_code=500, detail="Database not available")
    
    games_collection = db["scrabble_games"]
    game = games_collection.find_one({"_id": ObjectId(game_id), "username": username})
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    sentence_tiles, available_tiles, show_english, show_verb_hint = create_level_tiles(level_num)
    level_data = LEVEL_SENTENCES[level_num - 1]
    
    games_collection.update_one(
        {"_id": ObjectId(game_id)},
        {"$set": {
            "level": level_num,
            "phase": level_data["phase"],
            "correct_sentence": sentence_tiles,
            "available_tiles": available_tiles,
            "show_english": show_english,
            "show_verb_hint": show_verb_hint,
            "example": level_data["example"],
            "attempts": 0,
            "hints_used": 0,
            "current_stars": game.get("current_stars", 0)
        }}
    )
    
    return {
        "level": level_num,
        "phase": level_data["phase"],
        "available_tiles": available_tiles,
        "show_english": show_english,
        "show_verb_hint": show_verb_hint,
        "example": level_data["example"]
    }

# Include the router in the FastAPI app
app.include_router(router)

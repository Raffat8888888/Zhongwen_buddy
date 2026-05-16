import random
from typing import List, Dict, Tuple

# ==================== LEVEL DATA ====================
LEVEL_SENTENCES = [
    # ... (same level data as in scrabble.py) ...
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
    show_english = phase <= 3  # Hide English after phase 3
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
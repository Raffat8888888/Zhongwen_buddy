import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from './AuthContext';
import './Scrabble.css';

function Scrabble() {
  const { token } = useContext(AuthContext);
  const [gameId, setGameId] = useState(null);
  const [level, setLevel] = useState(1);
  const [phase, setPhase] = useState(1);
  const [currentStars, setCurrentStars] = useState(0);
  const [totalStars, setTotalStars] = useState(0);
  const [availableTiles, setAvailableTiles] = useState([]);
  const [selectedTiles, setSelectedTiles] = useState([]);
  const [showEnglish, setShowEnglish] = useState(true);
  const [showVerbHint, setShowVerbHint] = useState(true);
  const [example, setExample] = useState('');
  const [attempts, setAttempts] = useState(0);
  const [message, setMessage] = useState('');
  const [gameComplete, setGameComplete] = useState(false);
  const [levelStars, setLevelStars] = useState({});
  const [completedLevels, setCompletedLevels] = useState([]);
  const [loading, setLoading] = useState(true);

  // Hint reveal state
  const [showHintEnglish, setShowHintEnglish] = useState(false);
  const [revealedVerbPos, setRevealedVerbPos] = useState(null);
  const [showExampleHint, setShowExampleHint] = useState(false);

  const recordPerformance = async (activityType, score, details = {}) => {
    if (!token) return;
    try {
      await fetch('http://localhost:8000/performance/record', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          activity_type: activityType,
          score,
          details
        })
      });
    } catch (error) {
      console.warn("Failed to record performance:", error);
    }
  };

  useEffect(() => {
    if (token) {
      startNewGame();
    }
  }, [token]);

  const startNewGame = async () => {
    if (!token) {
      setMessage('Please login to play');
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/game/new', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      setGameId(data.game_id);
      setLevel(data.level || 1);
      setPhase(data.phase || 1);
      setAvailableTiles(data.available_tiles || []);
      setShowEnglish(data.show_english !== undefined ? data.show_english : true);
      setShowVerbHint(data.show_verb_hint !== undefined ? data.show_verb_hint : true);
      setExample(data.example || '');
      setCurrentStars(data.current_stars || 0);
      setTotalStars(data.total_stars || 0);
      setSelectedTiles([]);
      setAttempts(0);
      setMessage('');
      setShowHintEnglish(false);
      setRevealedVerbPos(null);
      setShowExampleHint(false);
      setLoading(false);
    } catch (error) {
      console.error('Error starting game:', error);
      setMessage(`Error: ${error.message}`);
      setLoading(false);
    }
  };

  const handleTileClick = (index) => {
    // Toggle tile selection
    const newSelected = [...selectedTiles];
    const existingIndex = newSelected.indexOf(index);
    
    if (existingIndex > -1) {
      newSelected.splice(existingIndex, 1);
    } else {
      newSelected.push(index);
    }
    
    setSelectedTiles(newSelected);
  };

  const submitSentence = async () => {
    if (selectedTiles.length === 0) {
      setMessage('Please select tiles in order');
      return;
    }

    if (!gameId || !token) {
      setMessage('Session lost. Please start a new game.');
      return;
    }

    try {
      const tiles = selectedTiles.map(i => availableTiles[i]);
      const response = await fetch(`http://localhost:8000/api/game/${gameId}/submit`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ tiles })
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();

      if (data.correct) {
        setMessage(`✓ Correct! You earned ${data.stars_earned} stars!`);
        setCurrentStars(data.stars_earned);
        setTotalStars(data.total_stars);
        setLevelStars({ ...levelStars, [level]: data.stars_earned });
        setSelectedTiles([]);
        setAttempts(0);
        const stars = typeof data.stars_earned === "number" ? data.stars_earned : 0;
        const score = Math.min(100, Math.round(stars * 33.3));
        recordPerformance("scrabble_game", score, {
          level,
          stars_earned: stars,
          total_stars: data.total_stars,
          attempts: data.attempts
        });

        if (data.game_complete) {
          setGameComplete(true);
          setMessage('🎉 Congratulations! You completed all 25 levels!');
        } else {
          setTimeout(() => {
            loadLevel(data.next_level);
          }, 2000);
        }
      } else {
        setAttempts(data.attempts);
        setMessage(`✗ ${data.message} (Attempt ${data.attempts})`);
      }
    } catch (error) {
      console.error('Error submitting:', error);
      setMessage('Error submitting sentence');
    }
  };

  const loadLevel = async (levelNum) => {
    if (!gameId || !token) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/game/${gameId}/level/${levelNum}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();
      setLevel(levelNum || 1);
      setPhase(data.phase || 1);
      setAvailableTiles(data.available_tiles || []);
      setShowEnglish(data.show_english !== undefined ? data.show_english : true);
      setShowVerbHint(data.show_verb_hint !== undefined ? data.show_verb_hint : true);
      setExample(data.example || '');
      setSelectedTiles([]);
      setAttempts(0);
      setMessage('');
      setShowHintEnglish(false);
      setRevealedVerbPos(null);
      setShowExampleHint(false);
    } catch (error) {
      console.error('Error loading level:', error);
      setMessage('Error loading level');
    }
  };

  // Define a wrapper function for hints
  const handleHint = async (type) => {
    if (!gameId || !token) {
      setMessage('Session lost. Please start a new game.');
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/game/${gameId}/hint`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ type })
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();
      if (!data.success) {
        setMessage(data.message || 'Not enough stars for this hint.');
        return;
      }

      setCurrentStars(data.remaining_stars ?? currentStars);

      const hint = data.hint || {};
      if (hint.type === 'english') {
        setShowHintEnglish(true);
      } else if (hint.type === 'verb') {
        setRevealedVerbPos(hint.position ?? null);
      } else if (hint.type === 'example') {
        if (hint.example) {
          setExample(hint.example);
        }
        setShowExampleHint(true);
      }
    } catch (error) {
      console.error('Error using hint:', error);
      setMessage('Error using hint');
    }
  };

  const renderTile = (tile, index, isAvailable = true) => {
    const isSelected = selectedTiles.includes(index);
    const verbHintActive = revealedVerbPos !== null && tile.role === 'verb';
    const tileClass = `tile ${isSelected ? 'selected' : ''} ${!isAvailable ? 'used' : ''} ${verbHintActive ? 'verb-hint' : ''}`;
    
    return (
      <div
        key={index}
        className={tileClass}
        onClick={() => isAvailable && handleTileClick(index)}
      >
        <div className="hanyu">{tile.hanyu}</div>
        <div className="pinyin">{tile.pinyin}</div>
        {(showEnglish || showHintEnglish) && (
          <div className="english">{tile.english}</div>
        )}
      </div>
    );
  };

  const renderPhaseIndicator = () => {
    const phases = [
      { num: 1, name: 'Single Words', levels: '1-5' },
      { num: 2, name: '2-Word Sentences', levels: '6-10' },
      { num: 3, name: '3-Word Sentences', levels: '11-15' },
      { num: 4, name: 'Sentence Variation', levels: '16-20' },
      { num: 5, name: 'Reduced Hints', levels: '21-25' }
    ];

    if (!phase || phase < 1 || phase > 5 || !phases[phase - 1]) {
      return null;
    }

    return (
      <div className="phase-indicator">
        <div className="phase-title">Phase {phase}: {phases[phase - 1].name}</div>
        <div className="phase-progress">
          {[1, 2, 3, 4, 5].map(p => (
            <div
              key={p}
              className={`phase-dot ${p === phase ? 'active' : ''} ${p < phase ? 'completed' : ''}`}
            />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="scrabble-game">
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner">Loading game...</div>
        </div>
      )}
      {!loading && (
        <>
      <div className="header">
        <h1>Chinese Sentence Scrabble</h1>
        <div className="header-stats">
          <div className="level-info">
            <span>Level {level}/25</span>
            <div className="stars-display">
              <span className="current-stars">★ {currentStars}</span>
              <span className="total-stars">(Total: {totalStars})</span>
            </div>
          </div>
        </div>
      </div>

      {renderPhaseIndicator()}

      <div className="game-container">
        <div className="instructions">
          <div className="instruction-box">
            <p><strong>Arrange the tiles to form a correct sentence:</strong></p>
            <p className="sentence-order">Subject → Verb → Object</p>
            {(showExampleHint && example) && <p className="example">Example: <em>"{example}"</em></p>}
          </div>
        </div>

        <div className="tiles-container">
          <h3>Available Tiles (click in order):</h3>
          <div className="tiles-grid">
            {availableTiles.map((tile, index) => renderTile(tile, index, true))}
          </div>
        </div>

        {selectedTiles.length > 0 && (
          <div className="selected-tiles">
            <h3>Your Selection (in order):</h3>
            <div className="selected-grid">
              {selectedTiles.map((tileIndex, posIndex) => (
                <div
                  key={posIndex}
                  className="position-marker"
                  onClick={() => {
                    const newSelected = selectedTiles.filter((_, i) => i !== posIndex);
                    setSelectedTiles(newSelected);
                  }}
                >
                  <div className="position-number">{posIndex + 1}</div>
                  {renderTile(availableTiles[tileIndex], `selected-${posIndex}`, true)}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="controls">
          <button
            className="btn btn-submit"
            onClick={submitSentence}
            disabled={selectedTiles.length === 0}
          >
            Submit Sentence
          </button>
          <button className="btn btn-clear" onClick={() => setSelectedTiles([])}>
            Clear Selection
          </button>
        </div>

        {message && (
          <div className={`message ${message.includes('✓') ? 'success' : message.includes('✗') ? 'error' : 'info'}`}>
            {message}
          </div>
        )}

        <div className="hints-section">
          <h4>Use Stars for Hints:</h4>
          <div className="hints-grid">
            <button
              className="hint-btn"
              onClick={() => handleHint('english')}
              disabled={currentStars < 1 || showHintEnglish || showEnglish}
              title="Reveal English meanings (costs 1 star)"
            >
              📖 Show English (1 ★)
            </button>
            {showVerbHint && (
              <button
                className="hint-btn"
                onClick={() => handleHint('verb')}
                disabled={currentStars < 1 || revealedVerbPos !== null}
                title="Highlight the verb position (costs 1 star)"
              >
                🎯 Highlight Verb (1 ★)
              </button>
            )}
            <button
              className="hint-btn"
              onClick={() => handleHint('example')}
              disabled={currentStars < 1 || showExampleHint}
              title="Show example sentence (costs 1 star)"
            >
              📝 Example (1 ★)
            </button>
          </div>
        </div>

        {gameComplete && (
          <div className="game-complete-modal">
            <div className="modal-content">
              <h2>🎉 Game Complete!</h2>
              <p>You've successfully completed all 25 levels!</p>
              <p className="final-stars">Total Stars Earned: {totalStars}</p>
              <button className="btn btn-primary" onClick={startNewGame}>
                Play Again
              </button>
            </div>
          </div>
        )}
      </div>
        </>
      )}
    </div>
  );
}

export default Scrabble;

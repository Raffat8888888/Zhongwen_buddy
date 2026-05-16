import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from './AuthContext';
import './Recommendations.css';

function Recommendations() {
  const { token } = useContext(AuthContext);
  const [recommendations, setRecommendations] = useState([]);
  const [learningLevel, setLearningLevel] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const [genres, setGenres] = useState([]);
  const [mood, setMood] = useState('cozy');
  const [pace, setPace] = useState('balanced');
  const [timeCommitment, setTimeCommitment] = useState('medium');

  const getRecommendation = async () => {
    if (!token) {
      setError('Please log in to get personalized recommendations.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await fetch('http://localhost:8000/recommend/get?limit=6', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }
      const data = await response.json();
      setRecommendations(Array.isArray(data.recommendations) ? data.recommendations : []);
      setLearningLevel(data.learning_level || '');
    } catch (error) {
      console.error('Error getting recommendation:', error);
      setError('Unable to get recommendation at this time.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      getRecommendation();
    }
  }, [token]);

  const toggleGenre = (g) => {
    setGenres((prev) => (
      prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g]
    ));
  };

  const submitQuestionnaire = async () => {
    if (!token) {
      setError('Please log in to save your preferences.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const response = await fetch('http://localhost:8000/recommend/questionnaire', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          genres,
          mood,
          pace,
          time_commitment: timeCommitment
        })
      });
      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }
      await getRecommendation();
    } catch (err) {
      console.error('Error saving questionnaire:', err);
      setError('Unable to save your preferences.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="recommendations">
      <div className="rec-hero">
        <div>
          <h2>Media Recommendations</h2>
          <p className="rec-subtitle">Movies, dramas, and books tailored to your level.</p>
        </div>
        {learningLevel && (
          <div className="level-badge">Level: {learningLevel}</div>
        )}
      </div>

      <div className="questionnaire-card">
        <h3>Quick Preference Check</h3>
        <p className="card-hint">Pick a few signals so we can personalize the list.</p>
        <div className="genre-grid">
          {['romance', 'thriller', 'fantasy', 'sci-fi', 'historical', 'comedy', 'slice-of-life', 'action', 'family'].map(g => (
            <button
              key={g}
              type="button"
              className={`chip ${genres.includes(g) ? 'active' : ''}`}
              onClick={() => toggleGenre(g)}
            >
              {g}
            </button>
          ))}
        </div>

        <div className="select-row">
          <label>
            Mood
            <select value={mood} onChange={(e) => setMood(e.target.value)}>
              <option value="cozy">Cozy / soft</option>
              <option value="balanced">Balanced</option>
              <option value="tense">Fast / intense</option>
            </select>
          </label>
          <label>
            Pace
            <select value={pace} onChange={(e) => setPace(e.target.value)}>
              <option value="slow">Slow</option>
              <option value="balanced">Balanced</option>
              <option value="fast">Fast</option>
            </select>
          </label>
          <label>
            Time
            <select value={timeCommitment} onChange={(e) => setTimeCommitment(e.target.value)}>
              <option value="short">Short</option>
              <option value="medium">Medium</option>
              <option value="long">Long</option>
            </select>
          </label>
        </div>

        <button className="save-btn" onClick={submitQuestionnaire} disabled={saving}>
          {saving ? 'Saving...' : 'Save Preferences'}
        </button>
      </div>

      <div className="recommendation-card">
        <h3>Top Picks</h3>
        {loading ? (
          <p>Loading recommendations...</p>
        ) : error ? (
          <p className="recommendation-text">{error}</p>
        ) : recommendations.length === 0 ? (
          <p className="recommendation-text">No recommendations available yet.</p>
        ) : (
          <div className="rec-list">
            {recommendations.map((r) => (
              <div key={r.id} className="rec-item">
                <div className="rec-type">{r.type}</div>
                <div className="rec-title">{r.title}</div>
                <div className="rec-meta">{r.genres.join(', ')} • {r.pace} • {r.time_commitment}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <button onClick={getRecommendation} disabled={loading} className="recommendation-btn">
        Refresh Recommendations
      </button>
    </div>
  );
}

export default Recommendations;

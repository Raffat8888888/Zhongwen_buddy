import React, { useState, useEffect, useContext, useCallback } from 'react';
import { AuthContext } from './AuthContext';
import './Performance.css';

function Performance() {
  const { token } = useContext(AuthContext);
  const [authError, setAuthError] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [levelInfo, setLevelInfo] = useState({ level: "unknown", overall_avg: null });

  const activityLabels = {
    chat: "Chat",
    tone_practice: "Tone Practice",
    scrabble_game: "Scrabble Game",
    video_call: "Video Call"
  };

  const activityOrder = ["chat", "tone_practice", "scrabble_game", "video_call"];

  const getHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      if (!token) {
        setHistory([]);
        return;
      }
      const response = await fetch('http://localhost:8000/performance/history?limit=60', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (response.status === 401) {
        setAuthError(true);
        setHistory([]);
        return;
      }
      if (!response.ok) {
        setHistory([]);
        return;
      }
      const data = await response.json();
      setHistory(Array.isArray(data.history) ? data.history : []);
    } catch (error) {
      console.error('Error getting history:', error);
    } finally {
      setHistoryLoading(false);
    }
  }, [token]);

  const getLevel = useCallback(async () => {
    try {
      if (!token) {
        setLevelInfo({ level: "unknown", overall_avg: null });
        return;
      }
      const response = await fetch('http://localhost:8000/performance/level', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (response.status === 401) {
        setAuthError(true);
        setLevelInfo({ level: "unknown", overall_avg: null });
        return;
      }
      if (!response.ok) {
        setLevelInfo({ level: "unknown", overall_avg: null });
        return;
      }
      const data = await response.json();
      setLevelInfo({
        level: data.level || "unknown",
        overall_avg: typeof data.overall_avg === "number" ? data.overall_avg : null
      });
    } catch (error) {
      console.error('Error getting level:', error);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      getHistory();
      getLevel();
    }
  }, [getHistory, getLevel, token]);

  const historyByActivity = history.reduce((acc, item) => {
    const key = item.activity_type || "unknown";
    if (!acc[key]) acc[key] = [];
    const scoreNum = typeof item.score === "number" ? item.score : Number(item.score);
    if (!Number.isNaN(scoreNum)) {
      acc[key].push({ score: scoreNum, timestamp: item.timestamp });
    }
    return acc;
  }, {});

  const formatTimestamp = (value) => {
    if (!value) return "N/A";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "N/A";
    return date.toLocaleString();
  };

  const activityStats = activityOrder
    .map((key) => {
      const points = historyByActivity[key] || [];
      if (points.length === 0) return null;
      const scores = points.map((p) => p.score);
      const total = scores.reduce((sum, v) => sum + v, 0);
      const avg = total / scores.length;
      const best = Math.max(...scores);
      const recent = points.reduce((latest, item) => {
        if (!latest) return item;
        const latestTime = new Date(latest.timestamp || 0).getTime();
        const itemTime = new Date(item.timestamp || 0).getTime();
        return itemTime >= latestTime ? item : latest;
      }, null);
      return {
        key,
        label: activityLabels[key] || key,
        count: points.length,
        avg,
        best,
        recentScore: recent ? recent.score : null,
        recentTime: recent ? formatTimestamp(recent.timestamp) : "N/A"
      };
    })
    .filter(Boolean);

  return (
    <div className="performance">
      <h2>Your Learning Performance</h2>

      <div className="level-card">
        <h3>Overall Level</h3>
        <p className="stat-number">{levelInfo.level}</p>
        {levelInfo.overall_avg !== null ? (
          <p className="stat-sub">Avg Score: {levelInfo.overall_avg.toFixed(1)}</p>
        ) : (
          <p className="stat-sub">Avg Score: N/A</p>
        )}
        <p className="level-note">
          Based on your overall average score across all activities.
        </p>
      </div>

      <div className="activity-stats">
        <h3>Your Activity Stats</h3>
        {authError ? (
          <div>
            <p>Unauthorized - please log in to view your performance.</p>
            <button onClick={() => window.location.href = '/login'}>Go to Login</button>
          </div>
        ) : historyLoading ? (
          <p>Loading history...</p>
        ) : activityStats.length === 0 ? (
          <p>No performance records yet.</p>
        ) : (
          <div className="stats-grid">
            {activityStats.map((stat) => (
              <div key={stat.key} className="stat-item">
                <h4>{stat.label}</h4>
                <div className="stat-details">
                  <p>Total Attempts: {stat.count}</p>
                  <p>Average Score: {stat.avg.toFixed(1)}</p>
                  <p>Best Score: {stat.best.toFixed(1)}</p>
                  <p>Most Recent: {stat.recentScore !== null ? stat.recentScore.toFixed(1) : "N/A"}</p>
                  <p>Last Played: {stat.recentTime}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}

export default Performance;


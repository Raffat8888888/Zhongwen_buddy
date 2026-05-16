import { useContext, useEffect, useMemo, useState } from "react";
import { AuthContext } from './AuthContext';
import './Dashboard.css'; // Add a CSS file for styling

const ACTIVITY_META = {
  chat: { label: "AI Chat Tutor", route: "/chat" },
  video_call: { label: "Video Call Practice", route: "/videocall" },
  scrabble_game: { label: "Chinese Scrabble", route: "/scrabble" },
  tone_practice: { label: "Tone Practice", route: "/tone-practice" },
};

const HEATMAP_DAYS = 28;

const formatDateKey = (date) => date.toISOString().slice(0, 10);

const toDisplayDate = (value) => {
  if (!value) return "N/A";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "N/A";
  return parsed.toLocaleString();
};

export default function Dashboard(){

  const { logout, token, user } = useContext(AuthContext);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [noteSaved, setNoteSaved] = useState(false);

  const todayKey = useMemo(() => formatDateKey(new Date()), []);
  const reflectionStorageKey = useMemo(
    () => `reflection_note_${user?.username || "learner"}_${todayKey}`,
    [todayKey, user?.username]
  );
  const [reflectionNote, setReflectionNote] = useState(() => localStorage.getItem(reflectionStorageKey) || "");

  useEffect(() => {
    setReflectionNote(localStorage.getItem(reflectionStorageKey) || "");
  }, [reflectionStorageKey]);

  useEffect(() => {
    const fetchHistory = async () => {
      if (!token) {
        setHistory([]);
        return;
      }
      setHistoryLoading(true);
      setHistoryError("");
      try {
        const response = await fetch("http://localhost:8000/performance/history?limit=120", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          throw new Error("Unable to load recent activity");
        }
        const data = await response.json();
        setHistory(Array.isArray(data.history) ? data.history : []);
      } catch (error) {
        setHistory([]);
        setHistoryError(error.message || "Unable to load recent activity");
      } finally {
        setHistoryLoading(false);
      }
    };

    fetchHistory();
  }, [token]);

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  const saveReflectionNote = () => {
    localStorage.setItem(reflectionStorageKey, reflectionNote.trim());
    setNoteSaved(true);
    setTimeout(() => setNoteSaved(false), 1500);
  };

  const continueCard = useMemo(() => {
    if (!history.length) return null;
    const recent = history[0];
    if (!recent) return null;

    const meta = ACTIVITY_META[recent.activity_type] || { label: "Learning Module", route: "/performance" };
    const score = typeof recent.score === "number" ? recent.score.toFixed(0) : "N/A";
    return {
      label: meta.label,
      route: meta.route,
      score,
      timestamp: toDisplayDate(recent.timestamp),
    };
  }, [history]);

  const heatmapDays = useMemo(() => {
    const countsByDate = {};
    // also keep breakdown by activity type per day
    history.forEach((item) => {
      const key = item?.timestamp ? formatDateKey(new Date(item.timestamp)) : null;
      if (!key) return;
      countsByDate[key] = countsByDate[key] || { total: 0, byType: {} };
      countsByDate[key].total += 1;
      const t = item.activity_type || 'other';
      countsByDate[key].byType[t] = (countsByDate[key].byType[t] || 0) + 1;
    });

    const output = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let lastMonth = null;
    for (let offset = HEATMAP_DAYS - 1; offset >= 0; offset--) {
      const day = new Date(today);
      day.setDate(today.getDate() - offset);
      const key = formatDateKey(day);
      const info = countsByDate[key] || { total: 0, byType: {} };
      const count = info.total;
      let intensity = 0;
      if (count >= 5) intensity = 4;
      else if (count >= 3) intensity = 3;
      else if (count >= 2) intensity = 2;
      else if (count >= 1) intensity = 1;
      const monthName = day.toLocaleDateString(undefined, { month: 'short' });
      const showMonth = monthName !== lastMonth;
      if (showMonth) lastMonth = monthName;
      output.push({
        key,
        count,
        intensity,
        breakdown: info.byType,
        label: day.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
        monthLabel: showMonth ? monthName : '',
      });
    }
    return output;
  }, [history]);

  // totals and current streak for header summary
  const heatmapSummary = useMemo(() => {
    const totals = heatmapDays.reduce((s, d) => s + d.count, 0);
    // current streak: consecutive non-zero days ending today
    let streak = 0;
    for (let i = heatmapDays.length - 1; i >= 0; i--) {
      if (heatmapDays[i].count > 0) streak += 1;
      else break;
    }
    return { totals, streak };
  }, [heatmapDays]);

  return(
    <div className="dashboard">
      <div className="dashboard-hero">
        <div>
          <h2>Welcome to Zhongwen</h2>
          <p className="dashboard-subtitle">A calm, focused space to build daily Chinese fluency.</p>
        </div>
      </div>

      <div className="insights-grid">
        <div className="insight-card">
          <h4>Continue Where You Left Off</h4>
          {historyLoading ? (
            <p className="insight-muted">Loading recent session...</p>
          ) : historyError ? (
            <p className="insight-muted">{historyError}</p>
          ) : continueCard ? (
            <>
              <p className="insight-strong">{continueCard.label}</p>
              <p className="insight-muted">Last score: {continueCard.score}</p>
              <p className="insight-muted">Last activity: {continueCard.timestamp}</p>
              <button className="primary-btn" onClick={() => window.location.href = continueCard.route}>
                Resume
              </button>
            </>
          ) : (
            <>
              <p className="insight-muted">No recent sessions yet.</p>
              <button className="primary-btn" onClick={() => window.location.href = '/chat'}>
                Start First Session
              </button>
            </>
          )}
        </div>

        <div className="insight-card">
          <h4>Reflection Note</h4>
          <p className="insight-muted">What felt difficult today, and what will you focus on next?</p>
          <textarea
            className="reflection-input"
            value={reflectionNote}
            onChange={(e) => setReflectionNote(e.target.value)}
            placeholder="Example: I flatten tone 4 in quick speech. Tomorrow I will slow down and hold the fall."
            rows={4}
          />
          <div className="reflection-actions">
            <button className="primary-btn" onClick={saveReflectionNote}>Save Note</button>
            <button className="ghost-btn" onClick={() => (window.location.href = "/journal")}>Open Journal</button>
            {noteSaved ? <span className="saved-badge">Saved</span> : null}
          </div>
        </div>
      </div>

      <div className="heatmap-card">
        <div className="heatmap-head">
            <h4>Learning Heatmap (Last 4 Weeks)</h4>
            <p className="insight-muted">Practice consistency by day</p>
            <div className="insight-muted" style={{marginTop:8,fontSize:13}}>
              Total activities: {heatmapSummary.totals} · Current streak: {heatmapSummary.streak} day{heatmapSummary.streak === 1 ? '': 's'}
            </div>
        </div>
        <div className="heatmap-grid">
            {heatmapDays.map((day) => {
              const breakdownLines = Object.entries(day.breakdown || {}).map(([k,v]) => `${k}: ${v}`).join('\n');
              const title = `${day.label}: ${day.count} activity${day.count===1?'':'ies'}${breakdownLines? '\n' + breakdownLines : ''}`;
              return (
                <div
                  key={day.key}
                  className={`heatmap-cell l${day.intensity}`}
                  title={title}
                  aria-label={title}
                  onClick={() => { window.location.href = `/performance?date=${day.key}` }}
                  role="button"
                  style={{cursor: 'pointer'}}
                >
                  <span className="day-label">{new Date(day.key).getDate()}</span>
                  {day.monthLabel ? <span className="month-label">{day.monthLabel}</span> : null}
                </div>
              )
            })}
        </div>
          <div className="heatmap-legend">
            <span>0</span>
            <span className="heatmap-cell l1" />
            <span>1</span>
            <span className="heatmap-cell l2" />
            <span>2–3</span>
            <span className="heatmap-cell l3" />
            <span>4+</span>
            <span className="heatmap-cell l4" />
          </div>
      </div>

      <div className="features-grid">
        <div className="feature-card">
          <h4>AI Chat Tutor</h4>
          <p>Practice conversation with our AI tutor</p>
          <button className="primary-btn" onClick={() => window.location.href = '/chat'}>Start Chat</button>
        </div>

        <div className="feature-card">
          <h4>Video Call Practice</h4>
          <p>Practice speaking with video feedback</p>
          <button className="primary-btn" onClick={() => window.location.href = '/videocall'}>Start Video Call</button>
        </div>

        <div className="feature-card">
          <h4>Chinese Scrabble</h4>
          <p>Learn characters through word games</p>
          <button className="primary-btn" onClick={() => window.location.href = '/scrabble'}>Play Scrabble</button>
        </div>

        <div className="feature-card">
          <h4>Personalized Recommendations</h4>
          <p>Get tailored learning suggestions</p>
          <button className="primary-btn" onClick={() => window.location.href = '/recommendations'}>View Recommendations</button>
        </div>

        <div className="feature-card">
          <h4>Performance Tracking</h4>
          <p>Monitor your learning progress</p>
          <button className="primary-btn" onClick={() => window.location.href = '/performance'}>View Stats</button>
        </div>

        <div className="feature-card">
          <h4>Tone Practice</h4>
          <p>Record one syllable and score tone confidence</p>
          <button className="primary-btn" onClick={() => window.location.href = '/tone-practice'}>Practice Tones</button>
        </div>

        <div className="feature-card">
          <h4>Reflection Journal</h4>
          <p>Review all your saved reflection notes by date</p>
          <button className="primary-btn" onClick={() => window.location.href = '/journal'}>Open Journal</button>
        </div>

        <div className="feature-card">
          <h4>How to Use Guide</h4>
          <p>Quick tips to get the most from each module</p>
          <button className="primary-btn" onClick={() => window.location.href = '/guide'}>Open Guide</button>
        </div>
      </div>

      <button className="logout-btn" onClick={handleLogout}>Logout</button>
    </div>
  )
}

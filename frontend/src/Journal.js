import { useContext, useMemo, useState } from "react";
import { AuthContext } from "./AuthContext";
import "./Journal.css";

const REFLECTION_PREFIX = "reflection_note_";

const parseDateFromKey = (key) => {
  const parts = key.split("_");
  const datePart = parts[parts.length - 1];
  const parsed = new Date(`${datePart}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return datePart;
  return parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
};

export default function Journal() {
  const { user } = useContext(AuthContext);
  const username = user?.username || "learner";
  const [refreshTick, setRefreshTick] = useState(0);

  const entries = useMemo(() => {
    const prefix = `${REFLECTION_PREFIX}${username}_`;
    const output = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key || !key.startsWith(prefix)) continue;
      const value = (localStorage.getItem(key) || "").trim();
      if (!value) continue;
      output.push({
        key,
        dateLabel: parseDateFromKey(key),
        note: value,
      });
    }

    output.sort((a, b) => (a.key < b.key ? 1 : -1));
    return output;
  }, [refreshTick, username]);

  const deleteEntry = (key) => {
    localStorage.removeItem(key);
    setRefreshTick((prev) => prev + 1);
  };

  const clearAll = () => {
    entries.forEach((entry) => localStorage.removeItem(entry.key));
    setRefreshTick((prev) => prev + 1);
  };

  return (
    <div className="journal-page">
      <div className="journal-header">
        <div>
          <h2>Reflection Journal</h2>
          <p className="journal-subtitle">Your saved reflection notes across days.</p>
        </div>
        <div className="journal-actions">
          <button className="ghost-btn" onClick={() => (window.location.href = "/")}>Back</button>
          {entries.length > 0 ? (
            <button className="danger-btn" onClick={clearAll}>Clear All</button>
          ) : null}
        </div>
      </div>

      <div className="journal-list">
        {entries.length === 0 ? (
          <div className="journal-empty">No reflection notes yet. Save one from the dashboard.</div>
        ) : (
          entries.map((entry) => (
            <div className="journal-card" key={entry.key}>
              <div className="journal-meta">{entry.dateLabel}</div>
              <div className="journal-note">{entry.note}</div>
              <button className="ghost-btn small" onClick={() => deleteEntry(entry.key)}>
                Delete
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

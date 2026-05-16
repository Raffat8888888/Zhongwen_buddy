import "./Guide.css";

export default function Guide() {
  return (
    <div className="guide-page">
      <header className="guide-hero">
        <div>
          <h2>How to Use Zhongwen</h2>
          <p className="guide-subtitle">
            What each module does, its scope, and how to get help.
          </p>
        </div>
        <div className="guide-badge">Quick Guide</div>
      </header>

      <section className="guide-section">
        <h3>Modules and Scope</h3>
        <div className="guide-grid">
          <div className="guide-card">
            <h4>AI Chat Tutor</h4>
            <p>
              Practice short conversations. Best for daily fluency, vocabulary
              recall, and basic tone awareness.
            </p>
            <div className="guide-scope">Scope: Text chat</div>
          </div>
          <div className="guide-card">
            <h4>Video Call Practice</h4>
            <p>
              Speak aloud with live transcription and AI replies. Ideal for
              pronunciation and speaking confidence.
            </p>
            <div className="guide-scope">Scope: Speech to text + AI response</div>
          </div>
          <div className="guide-card">
            <h4>Chinese Scrabble</h4>
            <p>
              Arrange tiles to build correct sentences. Great for grammar
              structure and word order.
            </p>
            <div className="guide-scope">Scope: Sentence building game</div>
          </div>
          <div className="guide-card">
            <h4>Recommendations</h4>
            <p>
              Personalized media picks based on your learning level and
              preferences.
            </p>
            <div className="guide-scope">Scope: Dramas, movies, and books</div>
          </div>
          <div className="guide-card">
            <h4>Performance</h4>
            <p>
              Tracks activity stats to show improvement over time and current
              level.
            </p>
            <div className="guide-scope">Scope: Activity stats only</div>
          </div>
        </div>
      </section>

      <section className="guide-section">
        <h3>Contact</h3>
        <div className="contact-card">
          <div className="contact-item">
            <div className="contact-label">Email</div>
            <div className="contact-value">contact@zhongwenbuddy.com</div>
          </div>
          <div className="contact-item">
            <div className="contact-label">Social</div>
            <div className="social-row">
              <div className="social-icon" aria-label="Facebook">
                <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                  <path d="M12 2.04c-5.5 0-9.96 4.46-9.96 9.96 0 4.98 3.66 9.1 8.44 9.85v-6.97H7.9v-2.88h2.58V9.41c0-2.55 1.52-3.96 3.85-3.96 1.12 0 2.29.2 2.29.2v2.52h-1.29c-1.27 0-1.66.79-1.66 1.6v1.93h2.82l-.45 2.88h-2.37v6.97c4.78-.75 8.44-4.87 8.44-9.85 0-5.5-4.46-9.96-9.96-9.96z" />
                </svg>
              </div>
              <div className="social-icon" aria-label="Instagram">
                <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                  <path d="M7 2.5h10A4.5 4.5 0 0 1 21.5 7v10A4.5 4.5 0 0 1 17 21.5H7A4.5 4.5 0 0 1 2.5 17V7A4.5 4.5 0 0 1 7 2.5zm0 1.8A2.7 2.7 0 0 0 4.3 7v10A2.7 2.7 0 0 0 7 19.7h10a2.7 2.7 0 0 0 2.7-2.7V7A2.7 2.7 0 0 0 17 4.3H7zm5 3a4.7 4.7 0 1 1-4.7 4.7A4.7 4.7 0 0 1 12 7.3zm0 1.8a2.9 2.9 0 1 0 2.9 2.9A2.9 2.9 0 0 0 12 9.1zm5.2-2.4a1.1 1.1 0 1 1-1.1 1.1 1.1 1.1 0 0 1 1.1-1.1z" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

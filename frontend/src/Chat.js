import { useState, useRef, useContext } from "react";
import { AuthContext } from "./AuthContext";
import "./Chat.css";

export default function Chat(){

  const { token } = useContext(AuthContext);
  const [msg,setMsg]=useState("");
  const [chat,setChat]=useState([]);
  const [sending, setSending] = useState(false);
  const chatEndRef = useRef(null);

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

  async function send(){
    try {
      if (!msg.trim()) return;
      setSending(true);
      const history = chat.map(c => `You: ${c.me}\nTutor: ${c.bot}`).join('\n');
      const res = await fetch("http://localhost:8000/chat",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          message: msg,
          history: history
        })
      });

      if (!res.ok) throw new Error("Failed to get response");

      const data = await res.json();

      setChat([...chat,{me:msg,bot:data.reply}]);
      const baseScore = Math.min(100, Math.max(20, msg.length * 2));
      recordPerformance("chat", baseScore, { message_length: msg.length });
      if (token) {
        try {
          await fetch("http://localhost:8000/conversation/summary", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
              source: "chat",
              content: `User: ${msg}\nTutor: ${data.reply}`
            })
          });
        } catch (err) {
          console.warn("Summary save failed:", err);
        }
      }
      setMsg("");
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (error) {
      alert("Error sending message: " + error.message);
    } finally {
      setSending(false);
    }
  }

  return(
    <div className="chat-page">
      <div className="chat-header">
        <div>
          <h2>Chat with Tutor</h2>
          <p className="chat-subtitle">Short, focused replies to build confidence.</p>
        </div>
      </div>

      <div className="chat-layout">
        <div className="chat-thread">
          {chat.length === 0 && (
            <div className="chat-empty">
              <div className="chat-empty-title">Start your first exchange</div>
              <div className="chat-empty-text">Ask a question or practice a sentence.</div>
            </div>
          )}
          {chat.map((c, i)=>(
            <div key={i} className="chat-pair">
              <div className="bubble user">
                <div className="bubble-label">You</div>
                <div className="bubble-text">{c.me}</div>
              </div>
              <div className="bubble bot">
                <div className="bubble-label">Tutor</div>
                <div className="bubble-text">{c.bot}</div>
              </div>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        <div className="chat-controls">
          <div className="control-card">
            <div className="control-title">Send Message</div>
            <div className="control-desc">Keep it short for crisp feedback.</div>
            <textarea
              className="chat-input"
              value={msg}
              onChange={e=>setMsg(e.target.value)}
              placeholder="Type your sentence or question..."
              rows={4}
            />
            <button className="send-btn" onClick={send} disabled={sending || !msg.trim()}>
              {sending ? "Sending..." : "Send"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

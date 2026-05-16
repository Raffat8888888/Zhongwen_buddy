import { useEffect, useRef, useState, useContext } from "react";
import { AuthContext } from "./AuthContext";
import "./VideoCall.css";

export default function VideoCall(){
  const { token } = useContext(AuthContext);
  const myVideo = useRef();
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [aiReply, setAiReply] = useState("");
  const [status, setStatus] = useState("Idle");
  const recognitionRef = useRef();
  const isRecognizingRef = useRef(false);
  const isSpeakingRef = useRef(false);

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

  useEffect(()=>{
    navigator.mediaDevices.getUserMedia({video:true,audio:true})
    .then(stream=>{
      myVideo.current.srcObject = stream;
    });

    // Initialize speech recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'zh-CN'; // Assuming Chinese, change if needed

      recognitionRef.current.onstart = () => {
        isRecognizingRef.current = true;
        setStatus("Listening");
      };

      recognitionRef.current.onend = () => {
        isRecognizingRef.current = false;
        setStatus(isRecording ? "Paused" : "Idle");
      };

      recognitionRef.current.onresult = (event) => {
        let finalTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          }
        }
        if (finalTranscript) {
          setTranscript(prev => prev + finalTranscript);
          sendToAI(finalTranscript);
        }
      };

      recognitionRef.current.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        setStatus("Error");
      };
    } else {
      alert("Speech recognition not supported in this browser.");
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        isRecognizingRef.current = false;
      }
    };
  },[]);

  const sendToAI = async (message) => {
    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      });
      const data = await response.json();
      setAiReply(data.reply);
      if (isRecording) {
        const charCount = (message || "").trim().length;
        const score = Math.min(100, Math.max(20, charCount * 2));
        recordPerformance("video_call", score, {
          input_chars: charCount,
          reply_chars: (data.reply || "").length
        });
      }
      if (token) {
        try {
          await fetch("http://localhost:8000/conversation/summary", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
              source: "video",
              content: `User: ${message}\nTutor: ${data.reply}`
            })
          });
        } catch (err) {
          console.warn("Summary save failed:", err);
        }
      }
      speakReply(data.reply);
    } catch (error) {
      console.error("Error sending to AI:", error);
      setAiReply("Sorry, I couldn't connect to the tutor.");
    }
  };

  const speakReply = (text) => {
    // Stop speech recognition while AI is speaking to prevent feedback loop
    if (recognitionRef.current && isRecognizingRef.current) {
      recognitionRef.current.stop();
    }

    // Cancel any queued speech so replies don't stack up
    window.speechSynthesis.cancel();
    isSpeakingRef.current = true;

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'zh-CN'; // Assuming Chinese

    const handleSpeechEnd = () => {
      isSpeakingRef.current = false;
      // Restart speech recognition after AI finishes speaking
      if (isRecording && !isRecognizingRef.current) {
        recognitionRef.current.start();
      }
    };
    utterance.onend = handleSpeechEnd;
    utterance.onerror = handleSpeechEnd;

    window.speechSynthesis.speak(utterance);
  };

  const startCall = () => {
    if (recognitionRef.current && !isRecognizingRef.current) {
      recognitionRef.current.start();
      setIsRecording(true);
      setStatus("Listening");
    }
  };

  const stopCall = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setIsRecording(false);
      setStatus("Idle");
    }
    if (isSpeakingRef.current) {
      window.speechSynthesis.cancel();
      isSpeakingRef.current = false;
    }
  };

  return(
    <div className="video-page">
      <div className="video-header">
        <div>
          <h2>AI Tutor Video Call</h2>
          <p className="video-subtitle">Speak naturally, get immediate feedback.</p>
        </div>
        <div className={`status-pill ${status.toLowerCase()}`}>{status}</div>
      </div>

      <div className="video-grid">
        <div className="video-card">
          <div className="video-frame">
            <video autoPlay muted ref={myVideo} />
          </div>
          <div className="video-actions">
            {!isRecording ? (
              <button className="primary-btn" onClick={startCall}>Start Talking</button>
            ) : (
              <button className="secondary-btn" onClick={stopCall}>Stop</button>
            )}
          </div>
        </div>

        <div className="insight-card">
          <div className="insight-block">
            <div className="insight-title">You said</div>
            <div className="insight-text">{transcript || "No transcript yet."}</div>
          </div>
          <div className="insight-divider" />
          <div className="insight-block">
            <div className="insight-title">AI Tutor</div>
            <div className="insight-text">{aiReply || "Waiting for your voice..."}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

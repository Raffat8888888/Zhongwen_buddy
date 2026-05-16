import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { AuthContext } from "./AuthContext";
import "./TonePractice.css";

const PROMPTS = [
  { hanzi: "妈", pinyin: "ma1", tone: 1, meaning: "mother" },
  { hanzi: "麻", pinyin: "ma2", tone: 2, meaning: "hemp" },
  { hanzi: "马", pinyin: "ma3", tone: 3, meaning: "horse" },
  { hanzi: "骂", pinyin: "ma4", tone: 4, meaning: "to scold" },
  { hanzi: "高", pinyin: "gao1", tone: 1, meaning: "high" },
  { hanzi: "来", pinyin: "lai2", tone: 2, meaning: "come" },
  { hanzi: "好", pinyin: "hao3", tone: 3, meaning: "good" },
  { hanzi: "去", pinyin: "qu4", tone: 4, meaning: "go" },
];

export default function TonePractice() {
  const { token } = useContext(AuthContext);
  const [promptIndex, setPromptIndex] = useState(0);
  const [status, setStatus] = useState("Idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);

  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);

  const prompt = useMemo(() => PROMPTS[promptIndex], [promptIndex]);
  const isRecording = status === "Recording";

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const recordPerformance = async (score, payload) => {
    if (!token) return;
    try {
      await fetch("http://localhost:8000/performance/record", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          activity_type: "tone_practice",
          score,
          details: payload,
        }),
      });
    } catch (recordError) {
      console.warn("Failed to record tone performance:", recordError);
    }
  };

  const startRecording = async () => {
    setError("");
    setResult(null);
    try {
      if (!streamRef.current) {
        streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      }

      const recorder = new MediaRecorder(streamRef.current);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        await submitForScoring(blob);
      };

      recorder.start();
      setStatus("Recording");
    } catch (startError) {
      setStatus("Idle");
      setError("Microphone access failed. Please allow mic permission.");
    }
  };

  const stopRecording = () => {
    if (!mediaRecorderRef.current) return;
    if (mediaRecorderRef.current.state === "inactive") return;
    setStatus("Scoring");
    mediaRecorderRef.current.stop();
  };

  const floatTo16BitPCM = (view, offset, input) => {
    let writeOffset = offset;
    for (let i = 0; i < input.length; i++) {
      const sample = Math.max(-1, Math.min(1, input[i]));
      view.setInt16(writeOffset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      writeOffset += 2;
    }
  };

  const writeWavHeader = (view, numChannels, sampleRate, dataLength) => {
    const writeString = (offset, value) => {
      for (let i = 0; i < value.length; i++) {
        view.setUint8(offset + i, value.charCodeAt(i));
      }
    };

    writeString(0, "RIFF");
    view.setUint32(4, 36 + dataLength, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numChannels * 2, true);
    view.setUint16(32, numChannels * 2, true);
    view.setUint16(34, 16, true);
    writeString(36, "data");
    view.setUint32(40, dataLength, true);
  };

  const convertBlobToWav = async (inputBlob) => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    try {
      const buffer = await inputBlob.arrayBuffer();
      const decoded = await audioContext.decodeAudioData(buffer);

      const numChannels = 1;
      const sampleRate = decoded.sampleRate;
      const channelData = decoded.getChannelData(0);
      const dataLength = channelData.length * 2;
      const wavBuffer = new ArrayBuffer(44 + dataLength);
      const view = new DataView(wavBuffer);

      writeWavHeader(view, numChannels, sampleRate, dataLength);
      floatTo16BitPCM(view, 44, channelData);

      return new Blob([wavBuffer], { type: "audio/wav" });
    } finally {
      await audioContext.close();
    }
  };

  const submitForScoring = async (blob) => {
    try {
      const wavBlob = await convertBlobToWav(blob);
      const formData = new FormData();
      formData.append("file", wavBlob, "attempt.wav");
      formData.append("expected_tone", String(prompt.tone));

      const response = await fetch("http://localhost:8000/tone/score", {
        method: "POST",
        body: formData,
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Tone scoring failed");
      }

      const attempt = {
        ...data,
        prompt_hanzi: prompt.hanzi,
        prompt_pinyin: prompt.pinyin,
      };

      setResult(attempt);
      setHistory((prev) => [attempt, ...prev].slice(0, 8));
      await recordPerformance(data.score, {
        prompt: prompt.pinyin,
        expected_tone: prompt.tone,
        predicted_tone: data.predicted_tone,
      });
      setStatus("Idle");
    } catch (submitError) {
      setStatus("Idle");
      setError(submitError.message || "Unable to score this recording.");
    }
  };

  const nextPrompt = () => {
    setResult(null);
    setError("");
    setPromptIndex((prev) => (prev + 1) % PROMPTS.length);
  };

  return (
    <div className="tone-page">
      <div className="tone-header">
        <div>
          <h2>Tone Practice</h2>
          <p className="tone-subtitle">
            Speak the target syllable and get a tone-confidence score.
          </p>
        </div>
        <div className={`tone-status ${status.toLowerCase()}`}>{status}</div>
      </div>

      <div className="tone-card">
        <div className="tone-target">
          <div className="hanzi">{prompt.hanzi}</div>
          <div className="pinyin">{prompt.pinyin}</div>
          <div className="meaning">{prompt.meaning}</div>
        </div>

        <div className="tone-actions">
          {!isRecording ? (
            <button className="primary-btn" onClick={startRecording}>Start Recording</button>
          ) : (
            <button className="secondary-btn" onClick={stopRecording}>Stop & Score</button>
          )}
          <button className="ghost-btn" onClick={nextPrompt}>Next Prompt</button>
        </div>

        {error ? <div className="tone-error">{error}</div> : null}

        {result ? (
          <div className="result-box">
            <div><strong>Score:</strong> {result.score}/100</div>
            <div><strong>Expected:</strong> Tone {result.expected_tone}</div>
            <div><strong>Predicted:</strong> Tone {result.predicted_tone}</div>
          </div>
        ) : null}
      </div>

      <div className="tone-history">
        <h3>Recent Attempts</h3>
        {history.length === 0 ? (
          <p className="history-empty">No attempts yet.</p>
        ) : (
          <div className="history-list">
            {history.map((item, idx) => (
              <div className="history-item" key={`${item.prompt_pinyin}-${idx}`}>
                <span>{item.prompt_hanzi} {item.prompt_pinyin}</span>
                <span>T{item.predicted_tone} / {item.score}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

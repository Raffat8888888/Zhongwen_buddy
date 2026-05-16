import os
import tempfile
import io
import time

import librosa
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
import soundfile as sf
from scipy.signal import resample_poly

app = FastAPI()


def _safe_mean(values: np.ndarray) -> float:
    if len(values) == 0:
        return 0.0
    return float(np.mean(values))


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def classify_and_score(f0_hz: np.ndarray, expected_tone: int) -> dict:
    # Keep only plausible voiced F0 values.
    voiced = f0_hz[np.isfinite(f0_hz) & (f0_hz > 60) & (f0_hz < 450)]
    if len(voiced) < 20:
        raise HTTPException(
            status_code=400,
            detail="Not enough voiced audio detected. Speak a little longer and clearly.",
        )

    # Normalize pitch to semitone offsets to reduce speaker variance.
    median_f0 = float(np.median(voiced))
    st = 12.0 * np.log2(voiced / median_f0)

    n = len(st)
    first = st[: n // 3]
    second = st[n // 3 : (2 * n) // 3]
    third = st[(2 * n) // 3 :]

    start = _safe_mean(first)
    mid = _safe_mean(second)
    end = _safe_mean(third)

    total_slope = end - start
    slope_1 = mid - start
    slope_2 = end - mid
    flatness = float(np.std(st))

    # Heuristic confidence for each Mandarin tone.
    conf_t1 = np.exp(-abs(total_slope)) * np.exp(-flatness)
    conf_t2 = _sigmoid(total_slope * 2.2)
    conf_t4 = _sigmoid(-total_slope * 2.2)
    conf_t3 = _sigmoid(-slope_1 * 3.0) * _sigmoid(slope_2 * 3.0)

    conf = {
        1: float(conf_t1),
        2: float(conf_t2),
        3: float(conf_t3),
        4: float(conf_t4),
    }

    predicted = max(conf, key=conf.get)
    expected_confidence = conf.get(expected_tone, 0.0)

    score = int(round(100 * expected_confidence))
    if predicted != expected_tone:
        score = max(0, score - 20)

    return {
        "expected_tone": expected_tone,
        "predicted_tone": predicted,
        "score": score,
        "confidence_by_tone": {str(k): round(v, 3) for k, v in conf.items()},
        "features": {
            "start": round(start, 3),
            "mid": round(mid, 3),
            "end": round(end, 3),
            "total_slope": round(total_slope, 3),
            "flatness": round(flatness, 3),
        },
    }


@app.post("/score")
async def score_tone(
    file: UploadFile = File(...),
    expected_tone: int = Form(...),
):
    if expected_tone not in {1, 2, 3, 4}:
        raise HTTPException(status_code=400, detail="expected_tone must be one of 1,2,3,4")

    t0 = time.perf_counter()

    try:
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # Fast path: frontend uploads WAV, decode in-memory to avoid disk/ffmpeg overhead.
        try:
            audio, sr = sf.read(io.BytesIO(raw_bytes), dtype="float32", always_2d=False)
            if isinstance(audio, np.ndarray) and audio.ndim > 1:
                audio = np.mean(audio, axis=1)
        except Exception:
            # Fallback for non-WAV uploads.
            suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(raw_bytes)
                temp_path = temp_file.name
            audio, sr = librosa.load(temp_path, sr=None, mono=True)
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

        if len(audio) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # Normalize sample rate once, then trim to the active speech region.
        target_sr = 16000
        if sr != target_sr:
            audio = resample_poly(audio, target_sr, sr).astype(np.float32)
            sr = target_sr

        audio, _ = librosa.effects.trim(audio, top_db=28)
        if len(audio) == 0:
            raise HTTPException(status_code=400, detail="No speech detected")

        # Keep only a short window to reduce pyin latency with minimal quality loss.
        max_samples = int(1.6 * sr)
        if len(audio) > max_samples:
            audio = audio[:max_samples]

        f0, _, _ = librosa.pyin(
            audio,
            sr=sr,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C6"),
            frame_length=1024,
            hop_length=256,
        )
        if f0 is None or not np.isfinite(f0).any():
            raise HTTPException(
                status_code=400,
                detail="No clear pitch detected. Try a quieter room and speak longer.",
            )
        result = classify_and_score(f0, expected_tone)
        result["processing_ms"] = int((time.perf_counter() - t0) * 1000)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        error_text = str(exc)
        if "audioread" in error_text.lower() or "ffmpeg" in error_text.lower():
            raise HTTPException(
                status_code=500,
                detail="Audio decode backend unavailable. Install FFmpeg or upload WAV audio.",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Tone scoring failed: {error_text}") from exc

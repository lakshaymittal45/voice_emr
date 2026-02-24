"use client";

import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_BASE || "ws://127.0.0.1:8000";

export default function LiveRecorder({
  patientId,
  clinician,
  role,
  onComplete,
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [statusMsg, setStatusMsg] = useState("Ready to record");
  const [transcript, setTranscript] = useState([]);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const [finishing, setFinishing] = useState(false);
  const [audioId, setAudioId] = useState(null);
  const [volumeLevel, setVolumeLevel] = useState(0);

  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const analyserRef = useRef(null);
  const animFrameRef = useRef(null);

  // ----------------------------------------------------------
  // Helpers
  // ----------------------------------------------------------

  const cleanup = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
  }, []);

  useEffect(() => {
    return cleanup; // cleanup on unmount
  }, [cleanup]);

  // ----------------------------------------------------------
  // Volume meter
  // ----------------------------------------------------------
  function startVolumeMeter(stream) {
    try {
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const data = new Uint8Array(analyser.frequencyBinCount);

      function tick() {
        analyser.getByteFrequencyData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) sum += data[i];
        setVolumeLevel(Math.min(100, Math.round((sum / data.length / 255) * 100 * 3)));
        animFrameRef.current = requestAnimationFrame(tick);
      }
      tick();
    } catch {
      // AudioContext may not be available
    }
  }

  // ----------------------------------------------------------
  // Start recording
  // ----------------------------------------------------------
  async function handleStart() {
    setError(null);
    setTranscript([]);
    setElapsed(0);
    setStatusMsg("Connecting…");
    setAudioId(null);
    setFinishing(false);

    // 1. Open WebSocket
    const wsUrl = `${WS_URL}/ws/live-record`;
    console.log("🔌 Connecting to WebSocket:", wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = async () => {
      console.log("✅ WebSocket opened, sending start message...");
      // Send start control message
      ws.send(
        JSON.stringify({
          type: "start",
          patient_id: patientId,
          clinician: clinician,
        })
      );
      console.log("📤 Sent start message:", { patient_id: patientId, clinician: clinician });

      // 2. Get mic access
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            sampleRate: 16000,
          },
        });
        streamRef.current = stream;
        startVolumeMeter(stream);

        // 3. MediaRecorder – send chunks every 1 second
        const recorder = new MediaRecorder(stream, {
          mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : "audio/webm",
        });
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            console.log(`🎤 Sending audio chunk: ${e.data.size} bytes`);
            ws.send(e.data);
          } else if (e.data.size > 0) {
            console.warn("⚠️ WebSocket not open, cannot send audio chunk");
          }
        };

        recorder.start(1000); // timeslice = 1s
        setIsRecording(true);
        setStatusMsg("🔴 Recording…");

        // Start elapsed timer
        const start = Date.now();
        timerRef.current = setInterval(() => {
          setElapsed(Math.floor((Date.now() - start) / 1000));
        }, 500);
      } catch (micErr) {
        setError("Microphone access denied: " + micErr.message);
        ws.close();
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === "connected") {
          // WebSocket connection confirmed
          console.log("✅ WebSocket connected:", msg.message);
        } else if (msg.type === "transcript") {
          setTranscript(msg.data);
          console.log("📝 Received transcript update:", msg.data.length, "segments");
        } else if (msg.type === "status") {
          setStatusMsg(msg.message);
          console.log("📊 Status:", msg.message);
        } else if (msg.type === "done") {
          setAudioId(msg.audio_id);
          setStatusMsg("✅ Processing complete!");
          setFinishing(false);
          console.log("✅ Processing complete! Audio ID:", msg.audio_id);
        } else if (msg.type === "error") {
          setError(msg.message);
          setFinishing(false);
          console.error("❌ Error:", msg.message);
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("❌ WebSocket error:", err);
      setError("WebSocket connection failed. Is the backend running?");
    };

    ws.onclose = (event) => {
      console.log("🔌 WebSocket closed:", event.code, event.reason);
      if (isRecording) {
        setIsRecording(false);
        setStatusMsg("Connection closed");
      }
    };
  }

  // ----------------------------------------------------------
  // Pause / Resume
  // ----------------------------------------------------------
  function handlePause() {
    if (!mediaRecorderRef.current) return;
    if (mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.pause();
      setIsPaused(true);
      setStatusMsg("⏸️ Paused");
    }
  }

  function handleResume() {
    if (!mediaRecorderRef.current) return;
    if (mediaRecorderRef.current.state === "paused") {
      mediaRecorderRef.current.resume();
      setIsPaused(false);
      setStatusMsg("🔴 Recording…");
    }
  }

  // ----------------------------------------------------------
  // Stop recording
  // ----------------------------------------------------------
  function handleStop() {
    setIsRecording(false);
    setIsPaused(false);
    setFinishing(true);
    setStatusMsg("Stopping recording & processing…");

    if (timerRef.current) clearInterval(timerRef.current);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

    const recorder = mediaRecorderRef.current;
    const ws = wsRef.current;

    // Request a final data flush from MediaRecorder, then send "stop"
    if (recorder && recorder.state !== "inactive") {
      // When requestData fires ondataavailable with the remaining buffer,
      // we catch the "stop" event right after to send the control message.
      recorder.onstop = () => {
        // All buffered data has been flushed via ondataavailable.
        // Now tell the backend we are done.
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "stop" }));
        }
      };
      // Flush remaining data then stop
      recorder.requestData();
      recorder.stop();
    } else {
      // No recorder running, just tell backend
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "stop" }));
      }
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
  }

  // ----------------------------------------------------------
  // Format mm:ss
  // ----------------------------------------------------------
  function fmtTime(sec) {
    const m = Math.floor(sec / 60)
      .toString()
      .padStart(2, "0");
    const s = (sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }

  // ----------------------------------------------------------
  // Render
  // ----------------------------------------------------------
  return (
    <div className="live-recorder">
      {/* Header card */}
      <div className="live-header-card">
        <div className="live-meta">
          <span className="live-meta-item">
            <strong>Patient:</strong> {patientId}
          </span>
          <span className="live-meta-item">
            <strong>Clinician:</strong> {clinician}
          </span>
        </div>

        {/* Status & timer */}
        <div className="live-status-row">
          <span className={`live-status-badge ${isRecording ? "recording" : finishing ? "finishing" : audioId ? "done" : ""}`}>
            {statusMsg}
          </span>
          <span className="live-timer">{fmtTime(elapsed)}</span>
        </div>

        {/* Volume meter */}
        {isRecording && (
          <div className="live-volume-bar-wrapper">
            <div
              className="live-volume-bar"
              style={{ width: `${volumeLevel}%` }}
            />
          </div>
        )}

        {/* Controls */}
        <div className="live-controls">
          {!isRecording && !finishing && !audioId && (
            <button className="live-btn start" onClick={handleStart}>
              🎙️ Start Recording
            </button>
          )}

          {isRecording && !isPaused && (
            <>
              <button className="live-btn pause" onClick={handlePause}>
                ⏸️ Pause
              </button>
              <button className="live-btn stop" onClick={handleStop}>
                ⏹️ Stop & Process
              </button>
            </>
          )}

          {isRecording && isPaused && (
            <>
              <button className="live-btn resume" onClick={handleResume}>
                ▶️ Resume
              </button>
              <button className="live-btn stop" onClick={handleStop}>
                ⏹️ Stop & Process
              </button>
            </>
          )}

          {finishing && (
            <div className="live-finishing">
              <div className="processing-spinner" />
              <span>Running full ML pipeline…</span>
            </div>
          )}

          {audioId && (
            <button
              className="live-btn view-result"
              onClick={() => onComplete(audioId)}
            >
              📋 View Consultation Result
            </button>
          )}
        </div>

        {error && <p className="live-error">❌ {error}</p>}
      </div>

      {/* Live transcript panel */}
      <div className="live-transcript-panel">
        <h3 className="live-transcript-title">
          📝 Live Transcript
          {transcript.length > 0 && (
            <span className="live-segment-count">
              {transcript.length} segment{transcript.length !== 1 ? "s" : ""}
            </span>
          )}
        </h3>

        {transcript.length === 0 ? (
          <div className="live-transcript-empty">
            {isRecording
              ? "Listening… transcript will appear here as you speak."
              : "No transcript yet."}
          </div>
        ) : (
          <div className="live-transcript-list">
            {transcript.map((seg, idx) => (
              <div
                key={idx}
                className={`transcript-line-enhanced ${
                  seg.speaker === "Doctor"
                    ? "speaker-doctor"
                    : "speaker-patient"
                }`}
              >
                <div className="transcript-header-enhanced">
                  <div className="speaker-info">
                    <span className="speaker-badge">
                      {seg.speaker === "Doctor" ? "🩺" : "🧑"}
                    </span>
                    <span className="speaker-name">{seg.speaker}</span>
                  </div>
                  {seg.start !== undefined && (
                    <span className="timestamp-badge">
                      {fmtTime(Math.round(seg.start))} –{" "}
                      {fmtTime(Math.round(seg.end))}
                    </span>
                  )}
                </div>
                <p className="transcript-text-enhanced">{seg.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

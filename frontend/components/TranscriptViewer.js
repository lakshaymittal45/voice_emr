"use client";

export default function TranscriptViewer({ transcript }) {
  // No transcript
  if (!transcript || transcript.length === 0) {
    return (
      <div className="transcript-box">
        <p className="empty-text">No transcript available.</p>
      </div>
    );
  }

  // Speaker-wise transcript (expected case)
  if (Array.isArray(transcript)) {
    return (
      <div className="transcript-box">
        {transcript.map((seg, index) => (
          <div
            key={index}
            className={`transcript-line ${
              seg.speaker === "Doctor"
                ? "speaker-doctor"
                : "speaker-patient"
            }`}
          >
            {/* Header */}
            <div className="transcript-header">
              <span className="transcript-speaker">
                {seg.speaker || "Speaker"}
              </span>

              {seg.start != null && seg.end != null && (
                <span className="transcript-time">
                  [{formatTime(seg.start)} – {formatTime(seg.end)}]
                </span>
              )}
            </div>

            {/* Text */}
            <p className="transcript-text">
              {seg.text || "—"}
            </p>

            {/* Confidence */}
            {typeof seg.confidence === "number" && (
              <p className="transcript-confidence">
                Confidence: {(seg.confidence * 100).toFixed(1)}%
              </p>
            )}
          </div>
        ))}
      </div>
    );
  }

  // Fallback: plain string
  if (typeof transcript === "string") {
    return (
      <div className="transcript-box">
        <pre className="transcript-raw">{transcript}</pre>
      </div>
    );
  }

  return (
    <div className="transcript-box">
      <p className="empty-text">Unsupported transcript format.</p>
    </div>
  );
}

/* ---------------- Helpers ---------------- */

function formatTime(seconds = 0) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

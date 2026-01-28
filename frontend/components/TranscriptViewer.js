"use client";

import { useRouter } from "next/navigation";

export default function TranscriptViewer({ transcript }) {
  const router = useRouter();

  // 🔴 No transcript at all
  if (!transcript) {
    return (
      <section>
        <BackButton />
        <p>No transcript available.</p>
      </section>
    );
  }

  // ✅ Case 1: Speaker-wise transcript (EXPECTED)
  if (Array.isArray(transcript)) {
    return (
      <section>
        <BackButton />
        <h2 style={{ marginTop: 12 }}>🗣️ Consultation Transcript</h2>

        {transcript.map((seg, index) => (
          <div
            key={index}
            style={{
              marginBottom: 14,
              padding: 12,
              borderRadius: 8,
              backgroundColor:
                seg.speaker === "Doctor" ? "#eef6ff" : "#f9f9f9",
              borderLeft:
                seg.speaker === "Doctor"
                  ? "4px solid #3b82f6"
                  : "4px solid #10b981",
            }}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontWeight: "bold",
              }}
            >
              <span>{seg.speaker || "Speaker"}</span>

              {seg.start != null && seg.end != null && (
                <span style={{ fontSize: 12, color: "#666" }}>
                  [{formatTime(seg.start)} – {formatTime(seg.end)}]
                </span>
              )}
            </div>

            {/* Text */}
            <p style={{ marginTop: 6 }}>{seg.text || "—"}</p>

            {/* Confidence (optional) */}
            {typeof seg.confidence === "number" && (
              <p style={{ fontSize: 12, color: "#777" }}>
                Confidence: {(seg.confidence * 100).toFixed(1)}%
              </p>
            )}
          </div>
        ))}
      </section>
    );
  }

  // ✅ Case 2: Plain string transcript (fallback)
  if (typeof transcript === "string") {
    return (
      <section>
        <BackButton />
        <h2>🗣️ Consultation Transcript</h2>
        <pre style={{ whiteSpace: "pre-wrap" }}>{transcript}</pre>
      </section>
    );
  }

  // ❌ Unknown format
  return (
    <section>
      <BackButton />
      <p>Unsupported transcript format.</p>
    </section>
  );
}

/* -------------------------------------------------- */
/* Helpers                                            */
/* -------------------------------------------------- */

function BackButton() {
  const router = useRouter();

  return (
    <button
      onClick={() => router.push("/upload")}
      style={{
        padding: "6px 12px",
        borderRadius: 6,
        border: "1px solid #ccc",
        background: "#fff",
        cursor: "pointer",
        marginBottom: 8,
      }}
    >
      ⬅️ Back to Upload
    </button>
  );
}

function formatTime(seconds = 0) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
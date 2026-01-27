import Link from "next/link";

export default function Home() {
  return (
    <main style={{ padding: 32, maxWidth: 900, margin: "auto" }}>
      
      <h1>🎙 Voice-Based EMR System</h1>

      <p style={{ marginTop: 12, fontSize: 18 }}>
        An AI-powered system that converts doctor–patient conversations
        into structured clinical notes automatically.
      </p>

      <hr style={{ margin: "24px 0" }} />

      <h2>⚙️ How It Works</h2>

      <ol style={{ fontSize: 16, lineHeight: 1.8 }}>
        <li>Upload doctor–patient consultation audio</li>
        <li>Speaker diarization (Doctor / Patient)</li>
        <li>Speech-to-text transcription</li>
        <li>AI-generated clinical notes</li>
        <li>Secure storage in EMR database</li>
      </ol>

      <hr style={{ margin: "24px 0" }} />

      <h2>🚀 Get Started</h2>

      <p>
        Upload a consultation audio file to generate transcript and
        structured medical notes.
      </p>

      <Link href="/upload">
        <button
          style={{
            marginTop: 12,
            padding: "10px 18px",
            fontSize: 16,
            cursor: "pointer"
          }}
        >
          ➕ Upload Consultation
        </button>
      </Link>

      <hr style={{ margin: "32px 0" }} />

      <p style={{ color: "#666", fontSize: 14 }}>
        Built using Whisper, PyAnnote, LLMs, and FastAPI.
      </p>
    </main>
  );
}

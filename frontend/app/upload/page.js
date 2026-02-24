"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function UploadPage() {
  const router = useRouter();
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

  const [audio, setAudio] = useState(null);
  const [patientId, setPatientId] = useState("");
  const [clinician, setClinician] = useState("");
  const [role, setRole] = useState("doctor");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [qualityWarning, setQualityWarning] = useState(null);

async function handleAudioChange(e) {
  const file = e.target.files[0];
  if (!file) {
    setAudio(null);
    setQualityWarning(null);
    return;
  }

  setAudio(file);
  
  // Quality validation: Check if file might be too compressed/low quality
  const fileSize = file.size;
  
  // Create audio element to get duration
  const audioElement = document.createElement('audio');
  audioElement.src = URL.createObjectURL(file);
  
  audioElement.onloadedmetadata = () => {
    const duration = audioElement.duration;
    URL.revokeObjectURL(audioElement.src);
    
    // Calculate expected minimum size (32 kbps = 4 KB/s is bare minimum)
    const minExpectedSize = duration * 4 * 1024; // 4 KB/second
    
    // Calculate bitrate estimate
    const estimatedBitrate = (fileSize * 8) / duration / 1000; // kbps
    
    if (fileSize < minExpectedSize) {
      setQualityWarning(
        `⚠️ Low quality audio detected (${estimatedBitrate.toFixed(0)} kbps). ` +
        `For best results, use at least 64 kbps. Transcription quality may be affected.`
      );
    } else if (estimatedBitrate < 64) {
      setQualityWarning(
        `⚠️ Audio quality is moderate (${estimatedBitrate.toFixed(0)} kbps). ` +
        `Consider recording at higher quality for best results.`
      );
    } else {
      setQualityWarning(null); // Good quality
    }
  };
  
  audioElement.onerror = () => {
    URL.revokeObjectURL(audioElement.src);
    // If we can't read duration, just check file size
    if (fileSize < 50000) { // Less than 50KB
      setQualityWarning(
        `⚠️ Very small audio file (${(fileSize/1024).toFixed(1)} KB). ` +
        `Transcription quality may be affected.`
      );
    }
  };
}

async function handleSubmit(e) {
  e.preventDefault();

  if (!audio || !patientId || !clinician) {
    setError("All fields are required");
    return;
  }

  try {
    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("audio", audio);

    const res = await fetch(
      `${API_BASE}/upload-consultation-audio?patient_id=${encodeURIComponent(patientId)}&clinician=${encodeURIComponent(clinician)}`,
      { method: "POST", body: formData }
    );

    if (!res.ok) throw new Error("Upload failed");

    // ✅ READ RESPONSE
    const data = await res.json();

    if (!data.audio_id) {
      throw new Error("No audio_id returned from server");
    }

    // ✅ PASS audio_id
    router.push(
      `/processing?audio_id=${data.audio_id}&role=${role}`
    );
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
}

  return (
    <>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-inner">
          <button
            className="nav-back"
            onClick={() => router.push("/")}
          >
            ← Home
          </button>

          <div className="navbar-title">
            Upload Consultation
          </div>
        </div>
      </nav>

      {/* Page */}
      <div className="page-wrapper">
        <div style={{ 
          padding: '12px 16px', 
          background: '#eff6ff', 
          borderRadius: '8px',
          marginBottom: '16px',
          border: '1px solid #bfdbfe',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span style={{ fontSize: '14px', color: '#1e40af' }}>
            💡 Need to upload multiple files?
          </span>
          <button
            onClick={() => router.push("/upload-bulk")}
            style={{
              padding: '6px 16px',
              background: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            Use Bulk Upload
          </button>
        </div>

        <div className="card">
          <form className="form" onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Patient ID</label>
              <input
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                placeholder="e.g. 1234"
              />
            </div>

            <div className="form-group">
              <label>Clinician Name</label>
              <input
                value={clinician}
                onChange={(e) => setClinician(e.target.value)}
                placeholder="e.g. Dr. Sharma"
              />
            </div>

            <div className="form-group">
              <label>Access Role</label>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="doctor">Doctor</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            <div className="form-group">
              <label>Consultation Audio</label>
              <input
                type="file"
                accept="audio/*"
                onChange={handleAudioChange}
              />
              {qualityWarning && (
                <div style={{
                  marginTop: '8px',
                  padding: '10px 12px',
                  background: '#fef3c7',
                  border: '1px solid #fbbf24',
                  borderRadius: '6px',
                  fontSize: '13px',
                  color: '#92400e',
                  lineHeight: '1.4'
                }}>
                  {qualityWarning}
                  <div style={{ marginTop: '6px', fontSize: '12px', color: '#78350f' }}>
                    💡 Tip: Recording at higher quality (64+ kbps) improves transcription accuracy.
                    Our system will automatically enhance the audio, but better input = better results.
                  </div>
                </div>
              )}
            </div>

            <button className="button-primary" disabled={loading}>
              {loading ? "Uploading…" : "Upload Consultation"}
            </button>

            {error && <p className="status-error">❌ {error}</p>}
          </form>
        </div>
      </div>
    </>
  );
}

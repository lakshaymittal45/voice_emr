"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function UploadPage() {
  const router = useRouter();

  const [audio, setAudio] = useState(null);
  const [patientId, setPatientId] = useState("");
  const [clinician, setClinician] = useState("");
  const [role, setRole] = useState("doctor");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
      `http://127.0.0.1:8000/upload-consultation-audio?patient_id=${patientId}&clinician=${clinician}`,
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
                onChange={(e) => setAudio(e.target.files[0])}
              />
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

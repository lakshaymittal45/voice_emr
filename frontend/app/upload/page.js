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

      const result = await res.json();
      router.push(`/consultation/${result.audio_id}?role=${role}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ padding: 24 }}>
      <h1>➕ Upload Consultation</h1>

      <form onSubmit={handleSubmit}>
        <input placeholder="Patient ID" value={patientId}
          onChange={(e) => setPatientId(e.target.value)} />

        <br /><br />

        <input placeholder="Clinician Name" value={clinician}
          onChange={(e) => setClinician(e.target.value)} />

        <br /><br />

        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="doctor">Doctor</option>
          <option value="admin">Admin</option>
        </select>

        <br /><br />

        <input type="file" accept="audio/*"
          onChange={(e) => setAudio(e.target.files[0])} />

        <br /><br />

        <button disabled={loading}>
          {loading ? "Uploading..." : "Upload"}
        </button>

        {error && <p style={{ color: "red" }}>❌ {error}</p>}
      </form>
    </main>
  );
}
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import LiveRecorder from "@/components/LiveRecorder";

export default function LiveRecordPage() {
  const router = useRouter();

  const [patientId, setPatientId] = useState("");
  const [clinician, setClinician] = useState("");
  const [role, setRole] = useState("doctor");
  const [sessionStarted, setSessionStarted] = useState(false);

  function handleStartSession(e) {
    e.preventDefault();
    if (!patientId || !clinician) return;
    setSessionStarted(true);
  }

  return (
    <>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-inner">
          <button className="nav-back" onClick={() => router.push("/")}>
            ← Home
          </button>
          <div className="navbar-title">🎙️ Live Recording</div>
        </div>
      </nav>

      {/* Page */}
      <div className="page-wrapper">
        {!sessionStarted ? (
          <div className="card">
            <h2>Start Live Session</h2>
            <p>
              Record a doctor–patient conversation in real time. The system
              will transcribe and diarize as you speak.
            </p>

            <form className="form" onSubmit={handleStartSession}>
              <div className="form-group">
                <label>Patient ID</label>
                <input
                  value={patientId}
                  onChange={(e) => setPatientId(e.target.value)}
                  placeholder="e.g. 1234"
                  required
                />
              </div>

              <div className="form-group">
                <label>Clinician Name</label>
                <input
                  value={clinician}
                  onChange={(e) => setClinician(e.target.value)}
                  placeholder="e.g. Dr. Sharma"
                  required
                />
              </div>

              <div className="form-group">
                <label>Access Role</label>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="doctor">Doctor</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <button className="button-primary" type="submit">
                Begin Recording Session
              </button>
            </form>
          </div>
        ) : (
          <LiveRecorder
            patientId={patientId}
            clinician={clinician}
            role={role}
            onComplete={(audioId) =>
              router.push(`/consultation/${audioId}?role=${role}`)
            }
          />
        )}
      </div>
    </>
  );
}

"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";

import TranscriptViewer from "@/components/TranscriptViewer";
import ClinicalNotes from "@/components/ClinicalNotes";

export default function ConsultationPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  const audioId = params?.audioId;
  const role = searchParams.get("role") || "doctor";

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchedRef = useRef(false);

  useEffect(() => {
    if (!audioId || fetchedRef.current) return;
    fetchedRef.current = true;

    async function fetchConsultation() {
      try {
        setLoading(true);
        const res = await fetch(
          `http://127.0.0.1:8000/consultation/${audioId}?role=${role}`
        );
        if (!res.ok) throw new Error("Failed to fetch consultation");
        setData(await res.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchConsultation();
  }, [audioId, role]);

  return (
    <>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-inner">
          <button
            className="nav-back"
            onClick={() => router.push("/upload")}
          >
            ← Back to Upload
          </button>
        </div>
      </nav>

      {/* App Heading */}
      <header className="app-heading">
        <h1 className="app-title">🩺 Consultation View</h1>
        <p className="app-tagline">Audio-based clinical consultation</p>
      </header>

      {/* Page Content */}
      <main className="page-wrapper">
        {loading && (
          <p className="status-text">⏳ Loading consultation…</p>
        )}

        {error && (
          <p className="status-error">❌ {error}</p>
        )}

        {data && (
          <>
            {/* Consultation Metadata */}
            <section className="info-card">
              <div>
                <span className="label">Patient ID</span>
                <span>{data.patient_id}</span>
              </div>
              <div>
                <span className="label">Clinician</span>
                <span>{data.clinician}</span>
              </div>
            </section>

            {/* Transcript */}
            <section className="section">
              <h2 className="section-title">Conversation Transcript</h2>
              <TranscriptViewer transcript={data.transcript} />
            </section>

            {/* Clinical Notes */}
            <section className="section">
              <h2 className="section-title">Clinical Notes</h2>
              <ClinicalNotes notes={data.clinical_notes} />
            </section>
          </>
        )}
      </main>
    </>
  );
}

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
  const [activeTab, setActiveTab] = useState("transcript");
  const [showBackToTop, setShowBackToTop] = useState(false);

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

  // Back to top button visibility
  useEffect(() => {
    const handleScroll = () => {
      setShowBackToTop(window.scrollY > 400);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

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
            📋 Consultation #{audioId}
          </div>
        </div>
      </nav>

      {/* Page Content */}
      <main className="page-wrapper">
        {loading && (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading consultation data...</p>
          </div>
        )}

        {error && (
          <div className="error-state">
            <span className="error-icon">⚠️</span>
            <p className="error-message">{error}</p>
            <button onClick={() => router.push("/")} className="button-primary">
              Go Home
            </button>
          </div>
        )}

        {data && (
          <>
            {/* Consultation Metadata Card */}
            <section className="info-card-enhanced">
              <div className="info-row">
                <div className="info-item">
                  <span className="info-label">👤 Patient ID</span>
                  <span className="info-value">{data.patient_id}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">👨‍⚕️ Clinician</span>
                  <span className="info-value">{data.clinician}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">🔒 Access Role</span>
                  <span className="info-value">{role}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">📊 Status</span>
                  <span className="status-badge-success">✓ Processed</span>
                </div>
              </div>
            </section>

            {/* Tab Navigation */}
            <div className="tab-navigation">
              <button
                className={`tab-button ${activeTab === "transcript" ? "active" : ""}`}
                onClick={() => setActiveTab("transcript")}
              >
                🎙️ Transcript
                {data.transcript && ` (${data.transcript.length})`}
              </button>
              <button
                className={`tab-button ${activeTab === "notes" ? "active" : ""}`}
                onClick={() => setActiveTab("notes")}
              >
                📝 Clinical Notes
              </button>
              <button
                className={`tab-button ${activeTab === "both" ? "active" : ""}`}
                onClick={() => setActiveTab("both")}
              >
                📋 Both
              </button>
            </div>

            {/* Tab Content */}
            {(activeTab === "transcript" || activeTab === "both") && (
              <section className="section">
                {activeTab === "both" && <h2 className="section-title">Conversation Transcript</h2>}
                <TranscriptViewer transcript={data.transcript} />
              </section>
            )}

            {(activeTab === "notes" || activeTab === "both") && (
              <section className="section">
                {activeTab === "both" && <h2 className="section-title">Clinical Notes</h2>}
                <ClinicalNotes notes={data.clinical_notes} />
              </section>
            )}
          </>
        )}

        {/* Back to Top Button */}
        {showBackToTop && (
          <button
            className="back-to-top"
            onClick={scrollToTop}
            title="Back to top"
          >
            ↑
          </button>
        )}
      </main>
    </>
  );
}

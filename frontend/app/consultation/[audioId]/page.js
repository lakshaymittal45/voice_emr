"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";

import TranscriptViewer from "@/components/TranscriptViewer";
import ClinicalNotes from "@/components/ClinicalNotes";

export default function ConsultationPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

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
          `${API_BASE}/consultation/${audioId}?role=${encodeURIComponent(role)}`
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
  }, [API_BASE, audioId, role]);

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

  const generatedAt = useMemo(
    () =>
      new Date().toLocaleString("en-IN", {
        dateStyle: "long",
        timeStyle: "short",
        timeZone: "Asia/Kolkata",
      }),
    []
  );

  const transcript = data?.transcript || [];
  const notes = data?.clinical_notes || {};
  const printableNotes = PRINT_NOTE_FIELDS.filter((field) => {
    const value = notes[field.key];
    return typeof value === "string" && value.trim() !== "";
  });

  return (
    <>
      <div className="print-fixed-header">
        <div className="print-fixed-header-inner">
          <div className="print-fixed-title">
            Homi Bhabha Cancer Hospital &amp; Research Centre, Punjab
          </div>
          <div className="print-fixed-meta">
            <span>CONS-{audioId}</span>
            <span>{data?.patient_id || "-"}</span>
          </div>
        </div>
      </div>

      <div className="print-report-shell">
        <div className="print-report-masthead">
          <div className="print-report-logo">
            <img
              src="/hbch-logo.png"
              alt="Homi Bhabha Cancer Hospital logo"
              className="print-report-logo-image"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          </div>

          <div className="print-report-center">
            <h1>HOMI BHABHA CANCER HOSPITAL &amp; RESEARCH CENTRE, PUNJAB</h1>
            <p>होमी भाभा कैंसर अस्पताल एवं अनुसंधान केंद्र, पंजाब</p>
            <p>A Unit of TATA MEMORIAL CENTRE / टाटा स्मारक केंद्र की एक इकाई</p>
            <p>DEPARTMENT OF ATOMIC ENERGY / परमाणु ऊर्जा विभाग</p>
            <p>GOVT. OF INDIA / भारत सरकार</p>
          </div>

          <div className="print-report-logo">
            <img
              src="/tmc-logo.png"
              alt="Tata Memorial Centre logo"
              className="print-report-logo-image"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
            />
          </div>
        </div>

        <div className="print-report-titlebar">
          <div className="print-report-title">Medical Consultation Report</div>
          <div className="print-report-subtitle">Confidential Hospital Record</div>
        </div>

        <div className="print-report-summary">
          <div className="print-summary-grid">
            <div className="print-summary-item">
              <span className="print-summary-label">Document ID</span>
              <span className="print-summary-value">CONS-{audioId}</span>
            </div>
            <div className="print-summary-item">
              <span className="print-summary-label">Generated</span>
              <span className="print-summary-value">{generatedAt}</span>
            </div>
            <div className="print-summary-item">
              <span className="print-summary-label">Patient ID</span>
              <span className="print-summary-value">{data?.patient_id || "-"}</span>
            </div>
            <div className="print-summary-item">
              <span className="print-summary-label">Clinician</span>
              <span className="print-summary-value">{data?.clinician || "-"}</span>
            </div>
          </div>
        </div>

        {printableNotes.length > 0 && (
          <section className="print-report-section print-report-section-compact">
            <div className="print-section-heading">Clinical Documentation</div>
            <div className="print-notes-grid">
              {printableNotes.map((field) => (
                <div key={field.key} className="print-note-card">
                  <div className="print-note-label">{field.label}</div>
                  <div className="print-note-value">{notes[field.key]}</div>
                </div>
              ))}
            </div>
          </section>
        )}

        {transcript.length > 0 && (
          <section className="print-report-section">
            <div className="print-section-heading">Conversation Transcript</div>
            <div className="print-transcript-list">
              {transcript.map((segment, index) => (
                <div key={`${segment.start}-${segment.end}-${index}`} className="print-transcript-item">
                  <div className="print-transcript-meta">
                    <span className="print-transcript-speaker">{segment.speaker || "Speaker"}</span>
                    <span className="print-transcript-time">
                      {formatTime(segment.start)} - {formatTime(segment.end)}
                    </span>
                    {typeof segment.confidence === "number" && (
                      <span className="print-transcript-confidence">
                        {Math.round(segment.confidence * 100)}% confidence
                      </span>
                    )}
                  </div>
                  <div className="print-transcript-text">
                    {getDisplayText(segment)}
                  </div>
                  {segment.text_native && segment.text_native !== getDisplayText(segment) && (
                    <div className="print-transcript-native">{segment.text_native}</div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="print-signature-block">
          <div className="print-signature-row">
            <div className="print-signature-col">
              <div className="print-signature-line" />
              <div className="print-signature-label">Prepared By</div>
            </div>
            <div className="print-signature-col">
              <div className="print-signature-line" />
              <div className="print-signature-label">Reviewed By</div>
            </div>
            <div className="print-signature-col">
              <div className="print-signature-line" />
              <div className="print-signature-label">Authorized Signatory</div>
            </div>
          </div>
        </section>
      </div>

      <nav className="navbar">
        <div className="navbar-inner">
          <button className="nav-back" onClick={() => router.push("/")}>
            ← Home
          </button>
          <div className="navbar-title">Consultation #{audioId}</div>
        </div>
      </nav>

      <main className="page-wrapper consultation-report-page screen-report-content">
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
            <section className="info-card-enhanced consultation-summary-card">
              <div className="info-row">
                <div className="info-item">
                  <span className="info-label">Patient ID</span>
                  <span className="info-value">{data.patient_id}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Clinician</span>
                  <span className="info-value">{data.clinician}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Access Role</span>
                  <span className="info-value">{role}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Status</span>
                  <span className="status-badge-success">✓ Processed</span>
                </div>
              </div>
            </section>

            <div className="tab-navigation">
              <button
                className={`tab-button ${activeTab === "transcript" ? "active" : ""}`}
                onClick={() => setActiveTab("transcript")}
              >
                Transcript
                {data.transcript && ` (${data.transcript.length})`}
              </button>
              <button
                className={`tab-button ${activeTab === "notes" ? "active" : ""}`}
                onClick={() => setActiveTab("notes")}
              >
                Clinical Notes
              </button>
              <button
                className={`tab-button ${activeTab === "both" ? "active" : ""}`}
                onClick={() => setActiveTab("both")}
              >
                Both
              </button>
            </div>

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

        {showBackToTop && (
          <button className="back-to-top" onClick={scrollToTop} title="Back to top">
            ↑
          </button>
        )}
      </main>
    </>
  );
}

const PRINT_NOTE_FIELDS = [
  { key: "chief_complaint", label: "Chief Complaint" },
  { key: "history_of_present_illness", label: "History of Present Illness" },
  { key: "associated_diseases", label: "Associated Diseases" },
  { key: "past_medical_history", label: "Past Medical History" },
  { key: "drug_history", label: "Drug History" },
  { key: "allergies", label: "Allergies" },
  { key: "assessment", label: "Assessment" },
  { key: "treatment_plan", label: "Treatment Plan" },
];

function getDisplayText(segment) {
  return segment?.text_romanized || segment?.text || "-";
}

function formatTime(seconds = 0) {
  const mins = Math.floor(Number(seconds || 0) / 60);
  const secs = Math.floor(Number(seconds || 0) % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

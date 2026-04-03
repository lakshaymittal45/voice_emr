"use client";

import Link from "next/link";

export default function Home() {
  return (
    <>
      <nav className="navbar">
        <div className="navbar-inner" />
      </nav>

      <div className="app-heading">
        <img
          src="/hbch-logo.png"
          alt="HBCH Punjab logo"
          style={{
            width: "84px",
            height: "84px",
            objectFit: "contain",
            margin: "0 auto 14px",
            display: "block",
          }}
        />
        <h1 className="app-title">Voice EMR</h1>
        <p className="app-tagline">Hospital Consultation Documentation</p>
        <p style={{ marginTop: "8px", color: "#64748b", fontSize: "14px" }}>
          Homi Bhabha Cancer Hospital &amp; Research Centre, Punjab
        </p>
      </div>

      <div className="page-wrapper">
        <div className="card">
          <h2>For Healthcare Providers</h2>
          <p>
            Access patient consultation history, search records, and review clinical notes.
          </p>

          <Link href="/doctor-dashboard" style={{ display: "block", marginTop: "20px" }}>
            <button
              className="button-primary"
              style={{
                width: "100%",
                background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                fontSize: "16px",
                padding: "14px 26px",
              }}
            >
              Doctor Dashboard
            </button>
          </Link>
        </div>

        <div className="card">
          <h2>Get Started</h2>

          <p>
            Securely convert doctor-patient conversations into structured, searchable
            clinical records using AI.
          </p>

          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", marginTop: "24px" }}>
            <Link href="/live-record" style={{ flex: "1 1 100%", minWidth: "200px" }}>
              <button
                className="button-primary"
                style={{
                  width: "100%",
                  background: "linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)",
                  fontSize: "16px",
                  padding: "14px 26px",
                }}
              >
                Live Recording
              </button>
            </Link>

            <Link href="/upload" style={{ flex: "1", minWidth: "200px" }}>
              <button className="button-primary" style={{ width: "100%" }}>
                Single Upload
              </button>
            </Link>

            <Link href="/upload-bulk" style={{ flex: "1", minWidth: "200px" }}>
              <button className="button-primary" style={{ width: "100%" }}>
                Bulk Upload
              </button>
            </Link>

            <Link href="/bulk-history" style={{ flex: "1", minWidth: "200px" }}>
              <button
                className="button-primary"
                style={{
                  width: "100%",
                  background: "linear-gradient(135deg, #0f766e 0%, #0d9488 100%)",
                }}
              >
                Bulk Upload History
              </button>
            </Link>
          </div>

          <div style={{ marginTop: "16px", fontSize: "14px", color: "#6b7280" }}>
            <p><strong>Live Recording:</strong> Record in real-time with live transcription</p>
            <p><strong>Single Upload:</strong> Upload one audio file at a time</p>
            <p><strong>Bulk Upload:</strong> Upload multiple files, up to 20 at once</p>
            <p><strong>Bulk Upload History:</strong> Review uploaded files and open completed transcriptions</p>
          </div>
        </div>
      </div>
    </>
  );
}

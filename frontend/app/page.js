"use client";

import Link from "next/link";

export default function Home() {
  return (
    <>
      {/* Navbar (structure only) */}
      <nav className="navbar">
        <div className="navbar-inner">
          {/* future back / nav buttons go here */}
        </div>
      </nav>

      {/* App Heading */}
      <div className="app-heading">
        <h1 className="app-title">🎙 Voice EMR</h1>
        <p className="app-tagline">
          Voice-Based Electronic Medical Records
        </p>
      </div>

      {/* Page Content */}
      <div className="page-wrapper">
        {/* Doctor Dashboard Card */}
        <div className="card">
          <h2>👨‍⚕️ For Healthcare Providers</h2>
          <p>
            Access patient consultation history, search records, and review clinical notes
          </p>

          <Link href="/doctor-dashboard" style={{ display: 'block', marginTop: '20px' }}>
            <button className="button-primary" style={{
              width: '100%',
              background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
              fontSize: '16px',
              padding: '14px 26px',
            }}>
              🔍 Doctor Dashboard
            </button>
          </Link>
        </div>

        {/* Recording & Upload Options */}
        <div className="card">
          <h2>Get Started</h2>

          <p>
            Securely convert doctor–patient conversations into structured,
            searchable clinical records using AI.
          </p>

          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginTop: '24px' }}>
            <Link href="/live-record" style={{ flex: '1 1 100%', minWidth: '200px' }}>
              <button className="button-primary" style={{
                width: '100%',
                background: 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)',
                fontSize: '16px',
                padding: '14px 26px',
              }}>
                🎙️ Live Recording
              </button>
            </Link>

            <Link href="/upload" style={{ flex: '1', minWidth: '200px' }}>
              <button className="button-primary" style={{ width: '100%' }}>
                📄 Single Upload
              </button>
            </Link>

            <Link href="/upload-bulk" style={{ flex: '1', minWidth: '200px' }}>
              <button className="button-primary" style={{ width: '100%' }}>
                📦 Bulk Upload
              </button>
            </Link>
          </div>

          <div style={{ marginTop: '16px', fontSize: '14px', color: '#6b7280' }}>
            <p><strong>🎙️ Live Recording:</strong> Record in real-time with live transcription</p>
            <p><strong>Single Upload:</strong> Upload one audio file at a time</p>
            <p><strong>Bulk Upload:</strong> Upload multiple files (up to 20) at once</p>
          </div>
        </div>
      </div>
    </>
  );
}

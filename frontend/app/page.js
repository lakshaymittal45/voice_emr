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
        <div className="card">
          <h2>Get Started</h2>

          <p>
            Securely convert doctor–patient conversations into structured,
            searchable clinical records using AI.
          </p>

          <Link href="/upload">
            <button className="button-primary">
              Upload Consultation
            </button>
          </Link>
        </div>
      </div>
    </>
  );
}

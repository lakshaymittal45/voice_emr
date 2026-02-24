"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DoctorDashboard() {
  const router = useRouter();
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

  const [patients, setPatients] = useState([]);
  const [filteredPatients, setFilteredPatients] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch all patients on mount
  useEffect(() => {
    fetchPatients();
  }, []);

  // Filter patients based on search query
  useEffect(() => {
    if (searchQuery.trim() === "") {
      setFilteredPatients([]);
      setShowDropdown(false);
    } else {
      const filtered = patients.filter(p => 
        p.patient_id.toLowerCase().includes(searchQuery.toLowerCase())
      );
      setFilteredPatients(filtered);
      setShowDropdown(true);
    }
  }, [searchQuery, patients]);

  async function fetchPatients() {
    try {
      const res = await fetch(`${API_BASE}/patients`);
      if (!res.ok) throw new Error("Failed to fetch patients");
      const data = await res.json();
      setPatients(data.patients || []);
    } catch (err) {
      console.error("Error fetching patients:", err);
      setError("Failed to load patient list");
    }
  }

  async function fetchAppointments(patientId) {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE}/patient/${encodeURIComponent(patientId)}/appointments`);
      
      if (!res.ok) {
        if (res.status === 404) {
          throw new Error("No appointments found for this patient");
        }
        throw new Error("Failed to fetch appointments");
      }
      
      const data = await res.json();
      setAppointments(data.appointments || []);
      setSelectedPatient(patientId);
    } catch (err) {
      console.error("Error fetching appointments:", err);
      setError(err.message);
      setAppointments([]);
    } finally {
      setLoading(false);
    }
  }

  function handlePatientSelect(patientId) {
    setSearchQuery(patientId);
    setShowDropdown(false);
    fetchAppointments(patientId);
  }

  function handleSearchSubmit(e) {
    e.preventDefault();
    if (searchQuery.trim()) {
      fetchAppointments(searchQuery.trim());
      setShowDropdown(false);
    }
  }

  function formatDateTime(isoString) {
    if (!isoString) return "—";
    const date = new Date(isoString);
    return date.toLocaleString('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'Asia/Kolkata'
    });
  }

  function formatDuration(seconds) {
    if (!seconds) return "—";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  }

  return (
    <>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-inner">
          <button className="nav-back" onClick={() => router.push("/")}>
            ← Home
          </button>
          <div className="navbar-title">👨‍⚕️ Doctor Dashboard</div>
        </div>
      </nav>

      {/* Page Content */}
      <main className="page-wrapper">
        {/* Search Card - Simplified */}
        <section className="search-card-simple">
          <h2>🔍 Find Patient</h2>

          <form onSubmit={handleSearchSubmit} className="form">
            <div className="search-container">
              <div className="search-input-wrapper">
                <input
                  type="text"
                  placeholder="Patient ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onFocus={() => {
                    if (searchQuery.trim()) setShowDropdown(true);
                  }}
                  className="search-input-large"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchQuery("");
                      setShowDropdown(false);
                      setSelectedPatient(null);
                      setAppointments([]);
                    }}
                    className="search-clear-btn"
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* Dropdown Suggestions */}
              {showDropdown && filteredPatients.length > 0 && (
                <div className="search-dropdown">
                  {filteredPatients.map((patient) => (
                    <button
                      key={patient.patient_id}
                      type="button"
                      onClick={() => handlePatientSelect(patient.patient_id)}
                      className="dropdown-item"
                    >
                      <div className="dropdown-item-main">
                        <span className="patient-id-badge">👤 {patient.patient_id}</span>
                      </div>
                      <div className="dropdown-item-meta">
                        {patient.total_appointments} visit{patient.total_appointments !== 1 ? 's' : ''} • Last: {formatDateTime(patient.last_appointment).split(',')[0]}
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {showDropdown && filteredPatients.length === 0 && searchQuery.trim() && (
                <div className="search-dropdown">
                  <div className="dropdown-empty">
                    No match for "{searchQuery}"
                  </div>
                </div>
              )}
            </div>

            <button type="submit" className="button-primary" disabled={!searchQuery.trim()}>
              Search
            </button>
          </form>
        </section>

        {/* Error Display */}
        {error && (
          <div className="error-state">
            <span className="error-icon">⚠️</span>
            <p className="error-message">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading appointments...</p>
          </div>
        )}

        {/* Appointments List */}
        {!loading && selectedPatient && appointments.length > 0 && (
          <section className="appointments-section">
            <h3 className="simple-section-title">
              Patient: {selectedPatient} ({appointments.length} visit{appointments.length !== 1 ? 's' : ''})
            </h3>

            <div className="appointments-list">
              {appointments.map((appt) => (
                <div
                  key={appt.audio_id}
                  className="appointment-card-simple"
                  onClick={() => router.push(`/consultation/${appt.audio_id}?role=doctor`)}
                >
                  <div className="appointment-main">
                    <div className="appointment-date-large">
                      📅 {formatDateTime(appt.time_of_capture)}
                    </div>
                    <div className="appointment-meta">
                      <span>👨‍⚕️ {appt.handling_clinician}</span>
                      {appt.audio_duration_seconds && (
                        <span>⏱️ {formatDuration(appt.audio_duration_seconds)}</span>
                      )}
                    </div>
                  </div>
                  <div className="appointment-action">
                    <span className="view-arrow">→</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </>
  );
}

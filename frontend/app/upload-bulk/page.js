"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { uploadConsultationAudioBulk } from "@/lib/api";

export default function UploadBulkPage() {
  const router = useRouter();

  const [audioFiles, setAudioFiles] = useState([]);
  const [patientId, setPatientId] = useState("");
  const [clinician, setClinician] = useState("");
  const [role, setRole] = useState("doctor");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function handleFileChange(e) {
    const files = Array.from(e.target.files);
    
    if (files.length > 20) {
      setError("Maximum 20 files allowed per bulk upload");
      return;
    }
    
    setAudioFiles(files);
    setError(null);
  }

  function removeFile(index) {
    setAudioFiles(audioFiles.filter((_, i) => i !== index));
  }

  async function handleSubmit(e) {
    e.preventDefault();

    if (audioFiles.length === 0 || !patientId || !clinician) {
      setError("Please fill all fields and select at least one audio file");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const formData = new FormData();
      
      // Append all audio files
      audioFiles.forEach(file => {
        formData.append("audio_files", file);
      });

      // Add metadata as query params (FastAPI expects this)
      const params = new URLSearchParams({
        patient_id: patientId,
        clinician: clinician
      });

      const res = await fetch(
        `http://127.0.0.1:8000/upload-consultation-audio-bulk?${params}`,
        { method: "POST", body: formData }
      );

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      const data = await res.json();

      // Store results in sessionStorage for the processing page
      sessionStorage.setItem('bulkUploadResults', JSON.stringify({
        results: data.results,
        role: role,
        patientId: patientId,
        clinician: clinician
      }));

      // Navigate to bulk processing page
      router.push(`/processing-bulk`);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const totalSize = audioFiles.reduce((sum, file) => sum + file.size, 0);

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
            Bulk Upload Consultations
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
                placeholder="e.g. P001"
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
              <label>Consultation Audio Files (Max 20)</label>
              <input
                type="file"
                accept="audio/*"
                multiple
                onChange={handleFileChange}
              />
              <p style={{ fontSize: '14px', color: '#6b7280', marginTop: '8px' }}>
                Supported formats: WAV, MP3, M4A, FLAC, OGG, WebM
              </p>
            </div>

            {/* File List */}
            {audioFiles.length > 0 && (
              <div style={{ 
                marginTop: '16px', 
                padding: '16px', 
                background: '#f9fafb', 
                borderRadius: '8px',
                border: '1px solid #e5e7eb'
              }}>
                <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px' }}>
                  Selected Files ({audioFiles.length}/20)
                </h3>
                
                <div style={{ marginBottom: '12px' }}>
                  <strong>Total Size:</strong> {formatFileSize(totalSize)}
                  {totalSize > 2000 * 1024 * 1024 && (
                    <span style={{ color: '#dc2626', marginLeft: '8px' }}>
                      (⚠️ Exceeds 2GB limit)
                    </span>
                  )}
                </div>

                <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                  {audioFiles.map((file, index) => (
                    <div 
                      key={index}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '8px 12px',
                        background: 'white',
                        borderRadius: '6px',
                        marginBottom: '8px',
                        border: '1px solid #e5e7eb'
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: '500', fontSize: '14px' }}>
                          {index + 1}. {file.name}
                        </div>
                        <div style={{ fontSize: '12px', color: '#6b7280' }}>
                          {formatFileSize(file.size)}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeFile(index)}
                        style={{
                          padding: '4px 12px',
                          background: '#fee2e2',
                          color: '#dc2626',
                          border: '1px solid #fecaca',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontSize: '14px'
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button 
              className="button-primary" 
              disabled={loading || audioFiles.length === 0}
              style={{ marginTop: '16px' }}
            >
              {loading ? `Uploading ${audioFiles.length} files…` : `Upload ${audioFiles.length} Files`}
            </button>

            {error && <p className="status-error">❌ {error}</p>}
          </form>
        </div>
      </div>
    </>
  );
}

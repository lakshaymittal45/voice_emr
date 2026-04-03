"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  fetchConsultationStatusBatch,
  removeQueuedAudio,
  startBulkProcessing,
} from "@/lib/api";

const STORAGE_KEY = "bulkUploadResults";

export default function UploadBulkPage() {
  const router = useRouter();
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

  const [audioFiles, setAudioFiles] = useState([]);
  const [fileMappings, setFileMappings] = useState([]);
  const [queuedResults, setQueuedResults] = useState([]);
  const [statusData, setStatusData] = useState(null);
  const [defaultPatientId, setDefaultPatientId] = useState("");
  const [defaultClinician, setDefaultClinician] = useState("");
  const [role, setRole] = useState("doctor");
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [deletingAudioIds, setDeletingAudioIds] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (!stored) return;

    try {
      const parsed = JSON.parse(stored);
      setQueuedResults(parsed.results || []);
      setRole(parsed.role || "doctor");
    } catch {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    const trackableAudioIds = queuedResults
      .filter((item) => item.audio_id)
      .map((item) => item.audio_id);

    if (!trackableAudioIds.length) {
      setStatusData(null);
      return;
    }

    const loadStatuses = async () => {
      try {
        const data = await fetchConsultationStatusBatch(trackableAudioIds);
        setStatusData(data);
      } catch (err) {
        setError(err.message);
      }
    };

    loadStatuses();

    const interval = setInterval(async () => {
      try {
        const data = await fetchConsultationStatusBatch(trackableAudioIds);
        setStatusData(data);

        const allComplete = Object.values(data.results).every(
          (status) => status === "done" || status === "failed"
        );

        if (allComplete) {
          clearInterval(interval);
          clearQueue();
        }
      } catch (err) {
        setError(err.message);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [queuedResults]);

  function persistResults(results, nextRole = role) {
    setQueuedResults(results);
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        results,
        role: nextRole,
      })
    );
  }

  function clearQueue() {
    setQueuedResults([]);
    setStatusData(null);
    setError(null);
    sessionStorage.removeItem(STORAGE_KEY);
  }

  function handleFileChange(e) {
    const files = Array.from(e.target.files || []);

    if (files.length > 20) {
      setError("Maximum 20 files allowed per bulk upload");
      return;
    }

    setAudioFiles(files);
    setFileMappings(
      files.map((file) => ({
        filename: file.name,
        patientId: defaultPatientId,
        clinician: defaultClinician,
      }))
    );
    setError(null);
  }

  function removeFile(index) {
    setAudioFiles((current) => current.filter((_, i) => i !== index));
    setFileMappings((current) => current.filter((_, i) => i !== index));
  }

  function updateMapping(index, field, value) {
    setFileMappings((current) =>
      current.map((mapping, i) =>
        i === index ? { ...mapping, [field]: value } : mapping
      )
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();

    if (audioFiles.length === 0) {
      setError("Please select at least one audio file");
      return;
    }

    const missingMapping = fileMappings.find(
      (mapping) => !mapping.patientId.trim() || !mapping.clinician.trim()
    );

    if (missingMapping) {
      setError("Every audio file must have a patient ID and clinician");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const formData = new FormData();
      audioFiles.forEach((file) => {
        formData.append("audio_files", file);
      });

      formData.append(
        "metadata_json",
        JSON.stringify(
          fileMappings.map((mapping) => ({
            filename: mapping.filename,
            patient_id: mapping.patientId.trim(),
            clinician: mapping.clinician.trim(),
          }))
        )
      );

      const res = await fetch(`${API_BASE}/upload-consultation-audio-bulk`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        const detail = errorData?.detail;
        throw new Error(
          typeof detail === "string" ? detail : JSON.stringify(detail || errorData)
        );
      }

      const data = await res.json();
      const mergedResults = [...queuedResults, ...data.results];
      persistResults(mergedResults, role);
      setAudioFiles([]);
      setFileMappings([]);
      setDefaultPatientId("");
      setDefaultClinician("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleStartProcessing() {
    const queuedAudioIds = queuedResults
      .filter((item) => item.audio_id)
      .filter((item) => {
        const currentStatus = statusData?.results?.[item.audio_id] || item.status;
        return currentStatus === "queued" || currentStatus === "accepted";
      })
      .map((item) => item.audio_id);

    if (!queuedAudioIds.length) return;

    try {
      setStarting(true);
      setError(null);
      await startBulkProcessing(queuedAudioIds);
      const refreshed = await fetchConsultationStatusBatch(
        queuedResults.filter((item) => item.audio_id).map((item) => item.audio_id)
      );
      setStatusData(refreshed);
    } catch (err) {
      setError(err.message);
    } finally {
      setStarting(false);
    }
  }

  async function handleDeleteFromQueue(item) {
    if (!item?.audio_id) {
      const filtered = queuedResults.filter((entry) => entry !== item);
      persistResults(filtered, role);
      return;
    }

    const audioId = item.audio_id;

    try {
      setDeletingAudioIds((current) => [...current, audioId]);
      setError(null);
      await removeQueuedAudio(audioId);

      const filtered = queuedResults.filter((entry) => entry.audio_id !== audioId);
      persistResults(filtered, role);
      setStatusData(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingAudioIds((current) => current.filter((id) => id !== audioId));
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const totalSize = audioFiles.reduce((sum, file) => sum + file.size, 0);
  const queuedItems = useMemo(
    () => queuedResults.filter((item) => item.status !== "rejected"),
    [queuedResults]
  );
  const rejectedItems = useMemo(
    () => queuedResults.filter((item) => item.status === "rejected"),
    [queuedResults]
  );
  const summary = statusData?.summary || {
    queued: queuedItems.length,
    processing: 0,
    done: 0,
    failed: rejectedItems.length,
  };
  const hasQueuedItems = queuedItems.some((item) => {
    const currentStatus = statusData?.results?.[item.audio_id] || item.status;
    return currentStatus === "queued" || currentStatus === "accepted";
  });

  const getStatusIcon = (status) => {
    switch (status) {
      case "queued":
        return "Q";
      case "processing":
        return "...";
      case "done":
        return "OK";
      case "failed":
        return "X";
      default:
        return "?";
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "queued":
        return "#64748b";
      case "processing":
        return "#f59e0b";
      case "done":
        return "#10b981";
      case "failed":
        return "#ef4444";
      default:
        return "#6b7280";
    }
  };

  return (
    <>
      <nav className="navbar">
        <div className="navbar-inner">
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <button className="nav-back" onClick={() => router.push("/")}>
              ← Home
            </button>
            <button className="nav-back" onClick={() => router.push("/bulk-history")}>
              Bulk History
            </button>
          </div>
          <div className="navbar-title">Bulk Upload Consultations</div>
        </div>
      </nav>

      <div className="page-wrapper">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1.35fr) minmax(320px, 0.95fr)",
            gap: "24px",
            alignItems: "start",
            width: "100%",
            maxWidth: "1400px",
            margin: "0 auto",
          }}
        >
          <div className="card">
            <form className="form" onSubmit={handleSubmit}>
              <div
                style={{
                  padding: "16px",
                  background: "#f8fafc",
                  borderRadius: "10px",
                  border: "1px solid #e2e8f0",
                }}
              >
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "16px",
                  }}
                >
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label>Patient id</label>
                    <input
                      value={defaultPatientId}
                      onChange={(e) => setDefaultPatientId(e.target.value)}
                      placeholder="Enter patient id"
                    />
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label>Clinician name</label>
                    <input
                      value={defaultClinician}
                      onChange={(e) => setDefaultClinician(e.target.value)}
                      placeholder="Enter clinician name"
                    />
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label>Access Role</label>
                    <select value={role} onChange={(e) => setRole(e.target.value)}>
                      <option value="doctor">Doctor</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                </div>

              </div>

              <div className="form-group">
                <label>Consultation Audio Files (Max 20)</label>
                <input type="file" accept="audio/*" multiple onChange={handleFileChange} />
                <p style={{ fontSize: "14px", color: "#6b7280", marginTop: "8px" }}>
                  Supported formats: WAV, MP3, M4A, FLAC, OGG, WebM
                </p>
              </div>

              {audioFiles.length > 0 && (
                <div
                  style={{
                    marginTop: "16px",
                    padding: "16px",
                    background: "#f9fafb",
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                  }}
                >
                  <h3 style={{ fontSize: "16px", fontWeight: "600", marginBottom: "12px" }}>
                    File Mapping ({audioFiles.length}/20)
                  </h3>

                  <div style={{ marginBottom: "12px" }}>
                    <strong>Total Size:</strong> {formatFileSize(totalSize)}
                  </div>

                  <div style={{ display: "grid", gap: "12px" }}>
                    {audioFiles.map((file, index) => (
                      <div
                        key={`${file.name}-${index}`}
                        style={{
                          background: "white",
                          borderRadius: "8px",
                          border: "1px solid #e5e7eb",
                          padding: "14px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            gap: "12px",
                            alignItems: "flex-start",
                            marginBottom: "12px",
                            flexWrap: "wrap",
                          }}
                        >
                          <div>
                            <div style={{ fontWeight: 600, fontSize: "14px" }}>
                              {index + 1}. {file.name}
                            </div>
                            <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "4px" }}>
                              {formatFileSize(file.size)}
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={() => removeFile(index)}
                            style={{
                              padding: "6px 12px",
                              background: "#fee2e2",
                              color: "#dc2626",
                              border: "1px solid #fecaca",
                              borderRadius: "6px",
                              cursor: "pointer",
                              fontSize: "14px",
                            }}
                          >
                            Remove
                          </button>
                        </div>

                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                            gap: "12px",
                          }}
                        >
                          <div>
                            <label style={{ display: "block", marginBottom: "6px", fontWeight: 500 }}>
                              Patient ID
                            </label>
                            <input
                              value={fileMappings[index]?.patientId || ""}
                              onChange={(e) => updateMapping(index, "patientId", e.target.value)}
                              placeholder="e.g. P001"
                            />
                          </div>

                          <div>
                            <label style={{ display: "block", marginBottom: "6px", fontWeight: 500 }}>
                              Clinician Name
                            </label>
                            <input
                              value={fileMappings[index]?.clinician || ""}
                              onChange={(e) => updateMapping(index, "clinician", e.target.value)}
                              placeholder="e.g. Dr. Sharma"
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <button
                className="button-primary"
                disabled={loading || audioFiles.length === 0}
                style={{ marginTop: "16px" }}
              >
                {loading ? `Adding ${audioFiles.length} files to queue...` : `Add ${audioFiles.length} Files To Queue`}
              </button>

              {error && <p className="status-error">❌ {error}</p>}
            </form>
          </div>

          <div className="card">
            <h2 style={{ marginBottom: "16px" }}>Queue Summary</h2>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                gap: "12px",
              }}
            >
              {[
                { label: "Total Files", value: queuedResults.length, color: "#1e40af", bg: "#eff6ff", border: "#bfdbfe" },
                { label: "Queued", value: summary.queued || 0, color: "#475569", bg: "#f8fafc", border: "#cbd5e1" },
                { label: "Processing", value: summary.processing || 0, color: "#b45309", bg: "#fffbeb", border: "#fde68a" },
                { label: "Done", value: summary.done || 0, color: "#15803d", bg: "#f0fdf4", border: "#bbf7d0" },
                { label: "Failed", value: (summary.failed || 0) + rejectedItems.length, color: "#dc2626", bg: "#fef2f2", border: "#fecaca" },
              ].map((item) => (
                <div
                  key={item.label}
                  style={{
                    padding: "16px",
                    background: item.bg,
                    border: `1px solid ${item.border}`,
                    borderRadius: "8px",
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: "24px", fontWeight: 700, color: item.color }}>{item.value}</div>
                  <div style={{ fontSize: "13px", color: "#64748b" }}>{item.label}</div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: "16px", display: "flex", gap: "12px", flexWrap: "wrap" }}>
              <button
                className="button-primary"
                onClick={handleStartProcessing}
                disabled={starting || !hasQueuedItems}
              >
                {starting ? "Starting Processing..." : "Start Process"}
              </button>
              <button
                type="button"
                onClick={clearQueue}
                disabled={!queuedResults.length}
                style={{
                  padding: "12px 18px",
                  background: "white",
                  color: "#dc2626",
                  border: "1px solid #fecaca",
                  borderRadius: "8px",
                  cursor: queuedResults.length ? "pointer" : "not-allowed",
                  fontSize: "14px",
                  fontWeight: 600,
                }}
              >
                Clear Queue
              </button>
            </div>

            <div style={{ marginTop: "20px" }}>
              <h3 style={{ marginBottom: "12px" }}>Queued Files ({queuedItems.length})</h3>
              {queuedItems.length === 0 ? (
                <p style={{ color: "#64748b", fontSize: "14px" }}>No queued files yet.</p>
              ) : (
                <div style={{ display: "grid", gap: "12px", maxHeight: "640px", overflowY: "auto" }}>
                  {queuedItems.map((item, index) => {
                    const currentStatus = item.audio_id
                      ? statusData?.results?.[item.audio_id] || item.status
                      : item.status;
                    const canDelete = currentStatus === "queued" || currentStatus === "accepted";
                    const isDeleting = item.audio_id && deletingAudioIds.includes(item.audio_id);

                    return (
                      <div
                        key={item.audio_id || `${item.filename}-${index}`}
                        style={{
                          background: "white",
                          borderRadius: "8px",
                          border: "1px solid #e5e7eb",
                          padding: "14px",
                        }}
                      >
                        <div style={{ fontWeight: 600, fontSize: "14px" }}>{item.filename}</div>
                        {item.audio_id && (
                          <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "4px" }}>
                            Audio ID: {item.audio_id}
                          </div>
                        )}
                        <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "4px" }}>
                          Patient: {item.patient_id || "-"} | Clinician: {item.clinician || "-"}
                        </div>
                        <div
                          style={{
                            marginTop: "8px",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: "10px",
                          }}
                        >
                          <span style={{ fontSize: "13px", fontWeight: 600, color: getStatusColor(currentStatus) }}>
                            {getStatusIcon(currentStatus)} {String(currentStatus).toUpperCase()}
                          </span>
                          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                            {canDelete && item.audio_id && (
                              <button
                                type="button"
                                onClick={() => handleDeleteFromQueue(item)}
                                disabled={Boolean(isDeleting)}
                                style={{
                                  padding: "6px 14px",
                                  background: "white",
                                  color: "#dc2626",
                                  border: "1px solid #fecaca",
                                  borderRadius: "6px",
                                  cursor: isDeleting ? "not-allowed" : "pointer",
                                  fontSize: "13px",
                                  fontWeight: 500,
                                }}
                              >
                                {isDeleting ? "Deleting..." : "Delete"}
                              </button>
                            )}
                            {currentStatus === "done" && item.audio_id && (
                              <button
                                type="button"
                                onClick={() => router.push(`/consultation/${item.audio_id}?role=${role}`)}
                                style={{
                                  padding: "6px 14px",
                                  background: "#3b82f6",
                                  color: "white",
                                  border: "none",
                                  borderRadius: "6px",
                                  cursor: "pointer",
                                  fontSize: "13px",
                                  fontWeight: 500,
                                }}
                              >
                                View
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

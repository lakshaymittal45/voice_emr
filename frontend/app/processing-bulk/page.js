"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchConsultationStatusBatch, startBulkProcessing } from "@/lib/api";

export default function ProcessingBulkPage() {
  const router = useRouter();

  const [uploadResults, setUploadResults] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [error, setError] = useState(null);
  const [role, setRole] = useState("doctor");
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem("bulkUploadResults");
    if (stored) {
      const data = JSON.parse(stored);
      setUploadResults(data);
      setRole(data.role || "doctor");
    } else {
      setError("No upload data found");
    }
  }, []);

  const queuedUploads = useMemo(() => {
    if (!uploadResults) return [];
    return uploadResults.results.filter(
      (item) => item.status === "queued" || item.status === "accepted"
    );
  }, [uploadResults]);

  useEffect(() => {
    if (!queuedUploads.length) return;

    const audioIds = queuedUploads.map((item) => item.audio_id);

    const loadStatuses = async () => {
      try {
        const data = await fetchConsultationStatusBatch(audioIds);
        setStatusData(data);
      } catch (err) {
        setError(err.message);
      }
    };

    loadStatuses();

    const interval = setInterval(async () => {
      try {
        const data = await fetchConsultationStatusBatch(audioIds);
        setStatusData(data);

        const allComplete = Object.values(data.results).every(
          (status) => status === "done" || status === "failed"
        );

        if (allComplete) {
          clearInterval(interval);
        }
      } catch (err) {
        setError(err.message);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [queuedUploads]);

  async function handleStartProcessing() {
    try {
      setStarting(true);
      setError(null);
      const audioIds = queuedUploads.map((item) => item.audio_id);
      await startBulkProcessing(audioIds);
      const refreshed = await fetchConsultationStatusBatch(audioIds);
      setStatusData(refreshed);
    } catch (err) {
      setError(err.message);
    } finally {
      setStarting(false);
    }
  }

  if (error && !uploadResults) {
    return (
      <div className="page-wrapper">
        <div className="card">
          <p className="status-error">❌ {error}</p>
          <button onClick={() => router.push("/")} className="button-primary">
            Go Home
          </button>
        </div>
      </div>
    );
  }

  if (!uploadResults) {
    return (
      <div className="page-wrapper">
        <div className="card">
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  const failedUploads = uploadResults.results.filter((item) => item.status === "rejected");
  const getStatusIcon = (status) => {
    switch (status) {
      case "queued":
        return "🗂️";
      case "processing":
        return "⏳";
      case "done":
        return "✅";
      case "failed":
        return "❌";
      default:
        return "❔";
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

  const summary = statusData?.summary || {
    queued: queuedUploads.length,
    processing: 0,
    done: 0,
    failed: 0,
  };
  const allDone =
    statusData &&
    Object.values(statusData.results).every((status) => status === "done" || status === "failed");
  const hasQueuedItems = statusData
    ? Object.values(statusData.results).some((status) => status === "queued")
    : queuedUploads.length > 0;

  return (
    <>
      <nav className="navbar">
        <div className="navbar-inner">
          <button className="nav-back" onClick={() => router.push("/")}>
            ← Home
          </button>
          <div className="navbar-title">Bulk Processing Status</div>
        </div>
      </nav>

      <div className="page-wrapper">
        <div className="card" style={{ marginBottom: "20px" }}>
          <h2>Queue Summary</h2>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "16px",
              marginTop: "16px",
            }}
          >
            <div style={{ padding: "16px", background: "#f0f9ff", borderRadius: "8px", border: "1px solid #bfdbfe" }}>
              <div style={{ fontSize: "24px", fontWeight: "700", color: "#1e40af" }}>{uploadResults.results.length}</div>
              <div style={{ fontSize: "14px", color: "#64748b" }}>Total Files</div>
            </div>
            <div style={{ padding: "16px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #cbd5e1" }}>
              <div style={{ fontSize: "24px", fontWeight: "700", color: "#475569" }}>{summary.queued || 0}</div>
              <div style={{ fontSize: "14px", color: "#64748b" }}>Queued</div>
            </div>
            <div style={{ padding: "16px", background: "#fffbeb", borderRadius: "8px", border: "1px solid #fde68a" }}>
              <div style={{ fontSize: "24px", fontWeight: "700", color: "#b45309" }}>{summary.processing || 0}</div>
              <div style={{ fontSize: "14px", color: "#64748b" }}>Processing</div>
            </div>
            <div style={{ padding: "16px", background: "#f0fdf4", borderRadius: "8px", border: "1px solid #bbf7d0" }}>
              <div style={{ fontSize: "24px", fontWeight: "700", color: "#15803d" }}>{summary.done || 0}</div>
              <div style={{ fontSize: "14px", color: "#64748b" }}>Done</div>
            </div>
            <div style={{ padding: "16px", background: "#fef2f2", borderRadius: "8px", border: "1px solid #fecaca" }}>
              <div style={{ fontSize: "24px", fontWeight: "700", color: "#dc2626" }}>{failedUploads.length + (summary.failed || 0)}</div>
              <div style={{ fontSize: "14px", color: "#64748b" }}>Failed</div>
            </div>
          </div>

          {hasQueuedItems && (
            <div style={{ marginTop: "20px" }}>
              <button onClick={handleStartProcessing} disabled={starting} className="button-primary">
                {starting ? "Starting Processing..." : "Start Process"}
              </button>
            </div>
          )}

          {error && <p className="status-error" style={{ marginTop: "16px" }}>❌ {error}</p>}
        </div>

        {queuedUploads.length > 0 && (
          <div className="card" style={{ marginBottom: "20px" }}>
            <h2>Queued Files ({queuedUploads.length})</h2>

            <div style={{ marginTop: "16px" }}>
              {queuedUploads.map((result) => {
                const currentStatus = statusData?.results?.[result.audio_id] || "queued";

                return (
                  <div
                    key={result.audio_id}
                    style={{
                      padding: "16px",
                      background: "white",
                      borderRadius: "8px",
                      marginBottom: "12px",
                      border: "1px solid #e5e7eb",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: "12px",
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: "600", fontSize: "14px" }}>{result.filename}</div>
                      <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "4px" }}>Audio ID: {result.audio_id}</div>
                      <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "4px" }}>
                        Patient: {result.patient_id || "-"} | Clinician: {result.clinician || "-"}
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span style={{ fontSize: "14px", fontWeight: "600", color: getStatusColor(currentStatus) }}>
                        {getStatusIcon(currentStatus)} {currentStatus.toUpperCase()}
                      </span>

                      {currentStatus === "done" && (
                        <button
                          onClick={() => router.push(`/consultation/${result.audio_id}?role=${role}`)}
                          style={{
                            padding: "6px 16px",
                            background: "#3b82f6",
                            color: "white",
                            border: "none",
                            borderRadius: "6px",
                            cursor: "pointer",
                            fontSize: "14px",
                            fontWeight: "500",
                          }}
                        >
                          View
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {failedUploads.length > 0 && (
          <div className="card">
            <h2 style={{ color: "#dc2626" }}>Rejected Files ({failedUploads.length})</h2>

            <div style={{ marginTop: "16px" }}>
              {failedUploads.map((result, index) => (
                <div
                  key={index}
                  style={{
                    padding: "16px",
                    background: "#fef2f2",
                    borderRadius: "8px",
                    marginBottom: "12px",
                    border: "1px solid #fecaca",
                  }}
                >
                  <div style={{ fontWeight: "600", fontSize: "14px", color: "#dc2626" }}>{result.filename}</div>
                  <div style={{ fontSize: "12px", color: "#991b1b", marginTop: "4px" }}>
                    Patient: {result.patient_id || "-"} | Clinician: {result.clinician || "-"}
                  </div>
                  <div style={{ fontSize: "13px", color: "#991b1b", marginTop: "4px" }}>❌ {result.error}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ marginTop: "24px", display: "flex", gap: "12px", justifyContent: "center" }}>
          <button onClick={() => router.push("/upload-bulk")} className="button-primary">
            Add More Files
          </button>

          {allDone && (
            <button
              onClick={() => router.push("/")}
              style={{
                padding: "12px 24px",
                background: "white",
                color: "#3b82f6",
                border: "1px solid #3b82f6",
                borderRadius: "8px",
                cursor: "pointer",
                fontSize: "16px",
                fontWeight: "500",
              }}
            >
              Go Home
            </button>
          )}
        </div>
      </div>
    </>
  );
}

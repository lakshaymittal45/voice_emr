"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchBulkUploadHistory } from "@/lib/api";

export default function BulkHistoryPage() {
  const router = useRouter();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [role, setRole] = useState("doctor");
  const [search, setSearch] = useState("");
  const [selectedDate, setSelectedDate] = useState("");

  const getDateKey = (item) => {
    const rawDate = item.created_at || item.time_of_capture;
    if (!rawDate) return "Unknown Date";

    const parsed = new Date(rawDate);
    if (Number.isNaN(parsed.getTime())) return "Unknown Date";
    return parsed.toISOString().slice(0, 10);
  };

  useEffect(() => {
    let mounted = true;

    const loadHistory = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchBulkUploadHistory(300);
        if (!mounted) return;
        setItems(data.history || []);
      } catch (err) {
        if (!mounted) return;
        setError(err.message);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadHistory();

    return () => {
      mounted = false;
    };
  }, []);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    const dateFilter = selectedDate.trim();

    return items.filter((item) => {
      const dateKey = getDateKey(item);
      if (dateFilter && dateKey !== dateFilter) {
        return false;
      }

      if (!query) {
        return true;
      }

      const source = [
        String(item.audio_id || ""),
        item.filename || "",
        item.patient_id || "",
        item.clinician || "",
        item.status || "",
        dateKey,
      ]
        .join(" ")
        .toLowerCase();
      return source.includes(query);
    });
  }, [items, search, selectedDate]);

  const groupedByDate = useMemo(() => {
    const groups = {};

    for (const item of filtered) {
      const dateKey = getDateKey(item);
      if (!groups[dateKey]) {
        groups[dateKey] = [];
      }
      groups[dateKey].push(item);
    }

    return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]));
  }, [filtered]);

  const summary = useMemo(() => {
    return {
      total: filtered.length,
      queued: filtered.filter((i) => i.status === "queued").length,
      processing: filtered.filter((i) => i.status === "processing").length,
      done: filtered.filter((i) => i.status === "done").length,
      failed: filtered.filter((i) => i.status === "failed").length,
    };
  }, [filtered]);

  return (
    <>
      <nav className="navbar">
        <div className="navbar-inner">
          <button className="nav-back" onClick={() => router.push("/")}>Home</button>
          <div className="navbar-title">Bulk Upload History</div>
        </div>
      </nav>

      <div className="page-wrapper">
        <div className="card" style={{ marginBottom: "18px" }}>
          <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by audio id, filename, patient, clinician"
              style={{ minWidth: "320px", flex: "1" }}
            />
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              style={{ width: "180px" }}
            />
            <button
              type="button"
              onClick={() => setSelectedDate("")}
              style={{
                padding: "10px 14px",
                background: "white",
                color: "#475569",
                border: "1px solid #cbd5e1",
                borderRadius: "8px",
                cursor: "pointer",
                fontSize: "14px",
                fontWeight: 600,
              }}
            >
              Clear Date
            </button>
            <select value={role} onChange={(e) => setRole(e.target.value)} style={{ width: "180px" }}>
              <option value="doctor">Doctor</option>
              <option value="admin">Admin</option>
            </select>
            <button className="button-primary" onClick={() => router.push("/upload-bulk")}>Upload More</button>
          </div>
        </div>

        <div className="card" style={{ marginBottom: "18px" }}>
          <h2 style={{ marginBottom: "12px" }}>Summary</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", gap: "10px" }}>
            {[
              { label: "Total", value: summary.total, color: "#1e40af", bg: "#eff6ff", border: "#bfdbfe" },
              { label: "Queued", value: summary.queued, color: "#475569", bg: "#f8fafc", border: "#cbd5e1" },
              { label: "Processing", value: summary.processing, color: "#b45309", bg: "#fffbeb", border: "#fde68a" },
              { label: "Done", value: summary.done, color: "#15803d", bg: "#f0fdf4", border: "#bbf7d0" },
              { label: "Failed", value: summary.failed, color: "#dc2626", bg: "#fef2f2", border: "#fecaca" },
            ].map((item) => (
              <div
                key={item.label}
                style={{
                  textAlign: "center",
                  borderRadius: "8px",
                  border: `1px solid ${item.border}`,
                  background: item.bg,
                  padding: "14px",
                }}
              >
                <div style={{ color: item.color, fontSize: "24px", fontWeight: 700 }}>{item.value}</div>
                <div style={{ color: "#64748b", fontSize: "13px" }}>{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 style={{ marginBottom: "12px" }}>Audio History ({filtered.length})</h2>

          {loading && <p>Loading history...</p>}
          {!loading && error && <p className="status-error">❌ {error}</p>}
          {!loading && !error && filtered.length === 0 && (
            <p style={{ color: "#64748b", fontSize: "14px" }}>No history found.</p>
          )}

          {!loading && !error && filtered.length > 0 && (
            <div style={{ display: "grid", gap: "12px", maxHeight: "760px", overflowY: "auto" }}>
              {groupedByDate.map(([dateKey, dateItems]) => (
                <div key={dateKey}>
                  <div
                    style={{
                      fontSize: "14px",
                      fontWeight: 700,
                      color: "#334155",
                      marginBottom: "10px",
                    }}
                  >
                    {dateKey} ({dateItems.length})
                  </div>

                  <div style={{ display: "grid", gap: "12px" }}>
                    {dateItems.map((item) => {
                      const statusColor =
                        item.status === "done"
                          ? "#15803d"
                          : item.status === "failed"
                          ? "#dc2626"
                          : item.status === "processing"
                          ? "#b45309"
                          : "#475569";

                      return (
                        <div
                          key={item.audio_id}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: "12px",
                            flexWrap: "wrap",
                            border: "1px solid #e5e7eb",
                            borderRadius: "8px",
                            padding: "14px",
                          }}
                        >
                          <div>
                            <div style={{ fontSize: "15px", fontWeight: 600 }}>{item.filename || "-"}</div>
                            <div style={{ color: "#64748b", fontSize: "13px", marginTop: "4px" }}>
                              Audio ID: {item.audio_id} | Patient: {item.patient_id || "-"} | Clinician: {item.clinician || "-"}
                            </div>
                            <div style={{ color: "#64748b", fontSize: "12px", marginTop: "4px" }}>
                              Captured: {item.time_of_capture || "-"}
                            </div>
                          </div>

                          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                            <span style={{ color: statusColor, fontWeight: 700, fontSize: "13px" }}>
                              {String(item.status || "unknown").toUpperCase()}
                            </span>
                            <button
                              type="button"
                              className="button-primary"
                              disabled={item.status !== "done"}
                              onClick={() => router.push(`/consultation/${item.audio_id}?role=${role}`)}
                              style={{
                                opacity: item.status === "done" ? 1 : 0.5,
                                cursor: item.status === "done" ? "pointer" : "not-allowed",
                                minWidth: "140px",
                              }}
                            >
                              View Transcription
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

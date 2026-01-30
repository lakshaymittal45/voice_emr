"use client";

export default function ClinicalNotes({ notes }) {
  if (!notes || Object.keys(notes).length === 0) {
    return (
      <div className="notes-box">
        <p className="empty-text">No clinical notes available.</p>
      </div>
    );
  }

  return (
    <div className="notes-box">
      {Object.entries(notes).map(([key, value]) => (
        <div className="notes-item" key={key}>
          <div className="notes-label">
            {formatLabel(key)}
          </div>

          <div className="notes-value">
            {value && value.trim() !== "" ? value : "—"}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------- helpers ---------- */

function formatLabel(key) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

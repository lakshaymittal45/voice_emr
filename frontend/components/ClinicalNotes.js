"use client";

import { useState } from "react";

export default function ClinicalNotes({ notes }) {
  const [copiedField, setCopiedField] = useState(null);

  if (!notes || Object.keys(notes).length === 0) {
    return (
      <div className="notes-box-enhanced">
        <p className="empty-text">No clinical notes available.</p>
      </div>
    );
  }

  const handleCopyField = (key, value) => {
    if (!value || value.trim() === "") return;
    
    navigator.clipboard.writeText(value);
    setCopiedField(key);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleCopyAll = () => {
    const text = Object.entries(notes)
      .filter(([_, value]) => value && value.trim() !== "")
      .map(([key, value]) => `${formatLabel(key)}:\n${value}`)
      .join("\n\n");
    
    navigator.clipboard.writeText(text);
    setCopiedField("all");
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Group notes by category
  const noteCategories = [
    {
      title: "Presenting Complaint",
      icon: "🩺",
      fields: ["chief_complaint", "history_of_present_illness"]
    },
    {
      title: "Medical History",
      icon: "📋",
      fields: ["past_medical_history", "associated_diseases", "drug_history", "allergies"]
    },
    {
      title: "Clinical Assessment",
      icon: "🔍",
      fields: ["assessment", "treatment_plan"]
    }
  ];

  return (
    <div className="notes-box-enhanced">
      {/* Header with Copy All */}
      <div className="notes-header">
        <h3 className="notes-title">Clinical Documentation</h3>
        <button 
          onClick={handleCopyAll}
          className="copy-all-btn"
          title="Copy all notes"
        >
          {copiedField === "all" ? "✓ Copied!" : "📋 Copy All"}
        </button>
      </div>

      {/* Categorized Notes */}
      {noteCategories.map((category, catIndex) => {
        const categoryFields = category.fields.filter(field => 
          notes[field] && notes[field].trim() !== ""
        );

        if (categoryFields.length === 0) return null;

        return (
          <div key={catIndex} className="notes-category">
            <h4 className="category-title">
              <span className="category-icon">{category.icon}</span>
              {category.title}
            </h4>

            {categoryFields.map((field) => (
              <div className="notes-item-enhanced" key={field}>
                <div className="notes-item-header">
                  <div className="notes-label-enhanced">
                    {formatLabel(field)}
                  </div>
                  <button
                    onClick={() => handleCopyField(field, notes[field])}
                    className="copy-field-btn"
                    title="Copy this field"
                  >
                    {copiedField === field ? "✓" : "📋"}
                  </button>
                </div>

                <div className="notes-value-enhanced">
                  {notes[field]}
                </div>
              </div>
            ))}
          </div>
        );
      })}

      {/* Empty State - if all fields are empty */}
      {noteCategories.every(cat => 
        cat.fields.every(field => !notes[field] || notes[field].trim() === "")
      ) && (
        <div className="empty-state">
          <p className="empty-text">ℹ️ No clinical information extracted from this consultation.</p>
        </div>
      )}
    </div>
  );
}

/* ---------- helpers ---------- */

function formatLabel(key) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

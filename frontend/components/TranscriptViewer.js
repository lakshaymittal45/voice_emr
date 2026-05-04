"use client";

import { useMemo, useState, useCallback } from "react";

export default function TranscriptViewer({
  transcript,
  transcriptCorrected,
  audioId,
  onSaveCorrected,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [speakerFilter, setSpeakerFilter] = useState("all");
  const [expandedItems, setExpandedItems] = useState(new Set());

  // ── Edit mode state ──
  const [isEditing, setIsEditing] = useState(false);
  const [editedSegments, setEditedSegments] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // "saved" | "error"
  const [viewMode, setViewMode] = useState("corrected"); // "raw" | "corrected"

  const hasCorrected = Array.isArray(transcriptCorrected) && transcriptCorrected.length > 0;

  // The active transcript shown (corrected if available and viewMode is corrected)
  const activeTranscript = useMemo(() => {
    if (isEditing && editedSegments) return editedSegments;
    if (viewMode === "corrected" && hasCorrected) return transcriptCorrected;
    return transcript;
  }, [isEditing, editedSegments, viewMode, hasCorrected, transcriptCorrected, transcript]);

  // Map speaker IDs from backend (SPEAKER_00, SPEAKER_01) to human-readable labels
  function getSpeakerDisplay(speakerId) {
    if (!speakerId) return { label: "Speaker", badge: "SP", cssClass: "speaker-other" };
    if (speakerId === "Doctor") return { label: "Doctor", badge: "DR", cssClass: "speaker-doctor" };
    if (speakerId === "Patient") return { label: "Patient", badge: "PT", cssClass: "speaker-patient" };
    if (speakerId.startsWith("SPEAKER_")) {
      const num = parseInt(speakerId.replace("SPEAKER_", ""), 10);
      if (num === 0) return { label: "Speaker 1", badge: "S1", cssClass: "speaker-doctor" };
      if (num === 1) return { label: "Speaker 2", badge: "S2", cssClass: "speaker-patient" };
      return { label: `Speaker ${num + 1}`, badge: `S${num + 1}`, cssClass: "speaker-other" };
    }
    return { label: speakerId, badge: speakerId.slice(0, 2).toUpperCase(), cssClass: "speaker-other" };
  }

  const getDisplayText = (seg) => seg?.text_romanized || seg?.text || "-";
  const hasWordConfidence = (seg) =>
    Array.isArray(seg?.word_confidences) && seg.word_confidences.length > 0;

  // ── Edit handlers ──
  const handleStartEdit = useCallback(() => {
    // Start from the corrected version if it exists, else from raw
    const base = hasCorrected ? transcriptCorrected : transcript;
    setEditedSegments(JSON.parse(JSON.stringify(base))); // deep clone
    setIsEditing(true);
    setSaveStatus(null);
  }, [transcript, transcriptCorrected, hasCorrected]);

  const handleCancelEdit = useCallback(() => {
    setIsEditing(false);
    setEditedSegments(null);
    setSaveStatus(null);
  }, []);

  const handleSegmentTextChange = useCallback((index, newText) => {
    setEditedSegments((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index] };
      // Update the primary text field
      if (updated[index].text_romanized) {
        updated[index].text_romanized = newText;
      } else {
        updated[index].text = newText;
      }
      return updated;
    });
  }, []);

  const handleSaveEdit = useCallback(async () => {
    if (!onSaveCorrected || !editedSegments) return;
    setSaving(true);
    setSaveStatus(null);
    try {
      await onSaveCorrected(editedSegments);
      setSaveStatus("saved");
      setIsEditing(false);
      // Don't clear editedSegments — parent will reload data
    } catch (err) {
      console.error("Failed to save corrected transcript:", err);
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  }, [onSaveCorrected, editedSegments]);

  if (!transcript || transcript.length === 0) {
    return (
      <div className="transcript-box">
        <p className="empty-text">No transcript available.</p>
      </div>
    );
  }

  if (typeof transcript === "string") {
    return (
      <div className="transcript-box">
        <pre className="transcript-raw">{transcript}</pre>
      </div>
    );
  }

  if (!Array.isArray(transcript)) {
    return (
      <div className="transcript-box">
        <p className="empty-text">Unsupported transcript format.</p>
      </div>
    );
  }

  const allSpeakers = useMemo(() => {
    const src = activeTranscript || transcript;
    const ids = [...new Set(src.map((s) => s.speaker).filter(Boolean))];
    return ids.map((id) => ({ id, ...getSpeakerDisplay(id) }));
  }, [activeTranscript, transcript]);

  const stats = useMemo(() => {
    const src = activeTranscript || transcript;
    const totalWords = src.reduce(
      (sum, seg) => sum + getDisplayText(seg).split(/\s+/).filter((w) => w).length,
      0
    );
    const duration =
      src.length > 0
        ? src[src.length - 1].end - src[0].start
        : 0;

    return { totalWords, duration };
  }, [activeTranscript, transcript]);

  const filteredTranscript = useMemo(() => {
    const src = activeTranscript || transcript;
    let filtered = src;

    if (speakerFilter !== "all") {
      filtered = filtered.filter(
        (seg) => seg.speaker === speakerFilter
      );
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (seg) =>
          getDisplayText(seg).toLowerCase().includes(query) ||
          seg.speaker?.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [activeTranscript, transcript, speakerFilter, searchQuery]);

  const handleExport = (format) => {
    const src = activeTranscript || transcript;
    if (format === "txt") {
      const text = src
        .map(
          (seg) =>
            `[${formatTime(seg.start)} - ${formatTime(seg.end)}] ${seg.speaker}: ${getDisplayText(seg)}`
        )
        .join("\n\n");
      downloadFile(text, "transcript.txt", "text/plain");
    } else if (format === "json") {
      const json = JSON.stringify(src, null, 2);
      downloadFile(json, "transcript.json", "application/json");
    }
  };

  const handleCopyAll = () => {
    const src = activeTranscript || transcript;
    const text = src
      .map((seg) => `${seg.speaker}: ${getDisplayText(seg)}`)
      .join("\n\n");
    navigator.clipboard.writeText(text);
    alert("Transcript copied to clipboard!");
  };

  const toggleExpand = (index) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedItems(newExpanded);
  };

  return (
    <div className="transcript-box-enhanced">
      <div className="transcript-controls">
        <div className="transcript-stats">
          <div className="stat-item">
            <span className="stat-value">{stats.totalWords}</span>
            <span className="stat-label">Words</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{(activeTranscript || transcript).length}</span>
            <span className="stat-label">Segments</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{formatDuration(stats.duration)}</span>
            <span className="stat-label">Duration</span>
          </div>
        </div>

        <div className="transcript-filters">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search transcript..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="search-clear"
                title="Clear search"
              >
                x
              </button>
            )}
          </div>

          <select
            value={speakerFilter}
            onChange={(e) => setSpeakerFilter(e.target.value)}
            className="speaker-filter"
          >
            <option value="all">All Speakers</option>
            {allSpeakers.map((sp) => (
              <option key={sp.id} value={sp.id}>
                {sp.label} Only
              </option>
            ))}
          </select>

          <div className="export-dropdown">
            <button className="export-btn">Export v</button>
            <div className="export-menu">
              <button onClick={() => handleExport("txt")}>Text File</button>
              <button onClick={() => handleExport("json")}>JSON</button>
              <button onClick={handleCopyAll}>Copy All</button>
              <button onClick={() => window.print()}>Print</button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Version Toggle + Edit Controls ── */}
      <div className="transcript-edit-toolbar">
        <div className="transcript-version-toggle">
          {hasCorrected && !isEditing && (
            <>
              <button
                className={`version-btn ${viewMode === "corrected" ? "active" : ""}`}
                onClick={() => setViewMode("corrected")}
              >
                ✏️ Corrected
              </button>
              <button
                className={`version-btn ${viewMode === "raw" ? "active" : ""}`}
                onClick={() => setViewMode("raw")}
              >
                🤖 Raw AI
              </button>
            </>
          )}
          {!hasCorrected && !isEditing && (
            <span className="version-label">🤖 AI Transcript</span>
          )}
          {isEditing && (
            <span className="version-label editing-label">✏️ Editing Mode</span>
          )}
        </div>

        <div className="transcript-edit-actions">
          {!isEditing ? (
            <button
              className="edit-transcript-btn"
              onClick={handleStartEdit}
              title="Edit transcript"
            >
              ✏️ Edit Transcript
            </button>
          ) : (
            <>
              <button
                className="edit-save-btn"
                onClick={handleSaveEdit}
                disabled={saving}
              >
                {saving ? "Saving..." : "💾 Save Corrections"}
              </button>
              <button
                className="edit-cancel-btn"
                onClick={handleCancelEdit}
                disabled={saving}
              >
                ✕ Cancel
              </button>
            </>
          )}
        </div>

        {saveStatus === "saved" && (
          <div className="save-status save-success">
            ✅ Corrected transcript saved successfully!
          </div>
        )}
        {saveStatus === "error" && (
          <div className="save-status save-error">
            ❌ Failed to save. Please try again.
          </div>
        )}
      </div>

      <div
        className="consultation-word-legend"
        style={{
          display: "flex",
          gap: "8px",
          flexWrap: "wrap",
          padding: "10px 18px 0",
          fontSize: "12px",
          color: "#475569",
        }}
      >
        <span>Word confidence:</span>
        <span style={confidenceLegendStyle("#dcfce7", "#166534")}>High</span>
        <span style={confidenceLegendStyle("#fef3c7", "#92400e")}>Medium</span>
        <span style={confidenceLegendStyle("#fee2e2", "#991b1b")}>Low</span>
      </div>

      {searchQuery && (
        <div className="search-results-info">
          Showing {filteredTranscript.length} of {(activeTranscript || transcript).length} segments
          {filteredTranscript.length === 0 && " - No matches found"}
        </div>
      )}

      <div className="transcript-content">
        {filteredTranscript.length === 0 ? (
          <p className="empty-text">No matching segments found.</p>
        ) : (
          filteredTranscript.map((seg) => {
            const src = activeTranscript || transcript;
            const originalIndex = src.indexOf(seg);
            const isExpanded = expandedItems.has(originalIndex);
            const displayText = getDisplayText(seg);
            const isLongText = displayText.length > 300;

            const speaker = getSpeakerDisplay(seg.speaker);

            return (
              <div
                key={originalIndex}
                className={`transcript-line-enhanced ${speaker.cssClass} ${isEditing ? "editing" : ""}`}
              >
                <div className="transcript-header-enhanced">
                  <div className="speaker-info">
                    <span className="speaker-badge">
                      {speaker.badge}
                    </span>
                    <span className="speaker-name">{speaker.label}</span>
                    {seg.start != null && seg.end != null && (
                      <span className="timestamp-badge">
                        {formatTime(seg.start)} {"->"} {formatTime(seg.end)}
                      </span>
                    )}
                  </div>

                  {typeof seg.confidence === "number" && (
                    <span
                      className="confidence-badge"
                      style={{ background: getConfidenceColor(seg.confidence) }}
                    >
                      {(seg.confidence * 100).toFixed(0)}% confident
                    </span>
                  )}
                </div>

                {isEditing ? (
                  <textarea
                    className="transcript-edit-textarea"
                    value={displayText}
                    onChange={(e) =>
                      handleSegmentTextChange(originalIndex, e.target.value)
                    }
                    rows={Math.max(2, Math.ceil(displayText.length / 80))}
                  />
                ) : (
                  <p
                    className={`transcript-text-enhanced ${
                      !isExpanded && isLongText ? "truncated" : ""
                    }`}
                  >
                    {hasWordConfidence(seg) && !searchQuery.trim()
                      ? renderWordConfidence(seg.word_confidences)
                      : highlightSearch(displayText, searchQuery)}
                  </p>
                )}

                {!isEditing && seg.text_native && seg.text_native !== displayText && (
                  <p className="transcript-text-enhanced" style={{ opacity: 0.68 }}>
                    {seg.text_native}
                  </p>
                )}

                {!isEditing && isLongText && (
                  <button
                    onClick={() => toggleExpand(originalIndex)}
                    className="expand-btn"
                  >
                    {isExpanded ? "Show Less ^" : "Show More v"}
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function formatTime(seconds = 0) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatDuration(seconds = 0) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

function getConfidenceColor(confidence) {
  if (confidence >= 0.9) return "#dcfce7";
  if (confidence >= 0.75) return "#fef3c7";
  return "#fee2e2";
}

function getConfidenceTextColor(confidence) {
  if (confidence >= 0.9) return "#166534";
  if (confidence >= 0.75) return "#92400e";
  return "#991b1b";
}

function confidenceLegendStyle(background, color) {
  return {
    background,
    color,
    padding: "2px 8px",
    borderRadius: "999px",
    fontWeight: 600,
  };
}

function renderWordConfidence(words) {
  return words.map((word, index) => {
    const confidence =
      typeof word?.confidence === "number" ? word.confidence : 0.75;
    return (
      <span
        key={`${word?.start ?? "w"}-${index}`}
        title={`${Math.round(confidence * 100)}% confidence`}
        style={{
          background: getConfidenceColor(confidence),
          color: getConfidenceTextColor(confidence),
          padding: "2px 4px",
          borderRadius: "6px",
          marginRight: "4px",
          display: "inline-block",
          marginBottom: "4px",
        }}
      >
        {word?.text || ""}
      </span>
    );
  });
}

function highlightSearch(text, query) {
  if (!query.trim()) return text;

  const regex = new RegExp(`(${escapeRegex(query)})`, "gi");
  const parts = text.split(regex);

  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark
        key={i}
        style={{ background: "#fef08a", padding: "2px 4px", borderRadius: "3px" }}
      >
        {part}
      </mark>
    ) : (
      part
    )
  );
}

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

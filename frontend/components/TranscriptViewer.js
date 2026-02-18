"use client";

import { useState, useMemo } from "react";

export default function TranscriptViewer({ transcript }) {
  const [searchQuery, setSearchQuery] = useState("");
  const [speakerFilter, setSpeakerFilter] = useState("all");
  const [expandedItems, setExpandedItems] = useState(new Set());

  // No transcript
  if (!transcript || transcript.length === 0) {
    return (
      <div className="transcript-box">
        <p className="empty-text">No transcript available.</p>
      </div>
    );
  }

  // Fallback: plain string
  if (typeof transcript === "string") {
    return (
      <div className="transcript-box">
        <pre className="transcript-raw">{transcript}</pre>
      </div>
    );
  }

  // Only handle array transcripts beyond this point
  if (!Array.isArray(transcript)) {
    return (
      <div className="transcript-box">
        <p className="empty-text">Unsupported transcript format.</p>
      </div>
    );
  }

  // Calculate statistics
  const stats = useMemo(() => {
    const totalWords = transcript.reduce((sum, seg) => 
      sum + (seg.text || "").split(/\s+/).filter(w => w).length, 0
    );
    const doctorCount = transcript.filter(s => s.speaker === "Doctor").length;
    const patientCount = transcript.filter(s => s.speaker === "Patient").length;
    const duration = transcript.length > 0 
      ? transcript[transcript.length - 1].end - transcript[0].start 
      : 0;
    
    return { totalWords, doctorCount, patientCount, duration };
  }, [transcript]);

  // Filter transcript
  const filteredTranscript = useMemo(() => {
    let filtered = transcript;

    // Speaker filter
    if (speakerFilter !== "all") {
      filtered = filtered.filter(seg => 
        seg.speaker?.toLowerCase() === speakerFilter.toLowerCase()
      );
    }

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(seg => 
        seg.text?.toLowerCase().includes(query) ||
        seg.speaker?.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [transcript, speakerFilter, searchQuery]);

  // Export functions
  const handleExport = (format) => {
    if (format === "txt") {
      const text = transcript.map(seg => 
        `[${formatTime(seg.start)} - ${formatTime(seg.end)}] ${seg.speaker}: ${seg.text}`
      ).join("\n\n");
      downloadFile(text, "transcript.txt", "text/plain");
    } else if (format === "json") {
      const json = JSON.stringify(transcript, null, 2);
      downloadFile(json, "transcript.json", "application/json");
    }
  };

  const handleCopyAll = () => {
    const text = transcript.map(seg => 
      `${seg.speaker}: ${seg.text}`
    ).join("\n\n");
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
      {/* Control Bar */}
      <div className="transcript-controls">
        <div className="transcript-stats">
          <div className="stat-item">
            <span className="stat-value">{stats.totalWords}</span>
            <span className="stat-label">Words</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{transcript.length}</span>
            <span className="stat-label">Segments</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{formatDuration(stats.duration)}</span>
            <span className="stat-label">Duration</span>
          </div>
        </div>

        <div className="transcript-filters">
          {/* Search */}
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
                ✕
              </button>
            )}
          </div>

          {/* Speaker Filter */}
          <select 
            value={speakerFilter} 
            onChange={(e) => setSpeakerFilter(e.target.value)}
            className="speaker-filter"
          >
            <option value="all">All Speakers</option>
            <option value="doctor">Doctor Only</option>
            <option value="patient">Patient Only</option>
          </select>

          {/* Export Dropdown */}
          <div className="export-dropdown">
            <button className="export-btn">Export ▾</button>
            <div className="export-menu">
              <button onClick={() => handleExport("txt")}>📄 Text File</button>
              <button onClick={() => handleExport("json")}>📋 JSON</button>
              <button onClick={handleCopyAll}>📋 Copy All</button>
              <button onClick={() => window.print()}>🖨️ Print</button>
            </div>
          </div>
        </div>
      </div>

      {/* Results Info */}
      {searchQuery && (
        <div className="search-results-info">
          Showing {filteredTranscript.length} of {transcript.length} segments
          {filteredTranscript.length === 0 && " - No matches found"}
        </div>
      )}

      {/* Transcript Content */}
      <div className="transcript-content">
        {filteredTranscript.length === 0 ? (
          <p className="empty-text">No matching segments found.</p>
        ) : (
          filteredTranscript.map((seg, index) => {
            const originalIndex = transcript.indexOf(seg);
            const isExpanded = expandedItems.has(originalIndex);
            const isLongText = seg.text && seg.text.length > 300;

            return (
              <div
                key={originalIndex}
                className={`transcript-line-enhanced ${
                  seg.speaker === "Doctor"
                    ? "speaker-doctor"
                    : "speaker-patient"
                }`}
              >
                {/* Header */}
                <div className="transcript-header-enhanced">
                  <div className="speaker-info">
                    <span className="speaker-badge">
                      {seg.speaker === "Doctor" ? "👨‍⚕️" : "🧑"}
                    </span>
                    <span className="speaker-name">
                      {seg.speaker || "Speaker"}
                    </span>
                    {seg.start != null && seg.end != null && (
                      <span className="timestamp-badge">
                        {formatTime(seg.start)} → {formatTime(seg.end)}
                      </span>
                    )}
                  </div>

                  {typeof seg.confidence === "number" && (
                    <span 
                      className="confidence-badge"
                      style={{
                        background: getConfidenceColor(seg.confidence)
                      }}
                    >
                      {(seg.confidence * 100).toFixed(0)}% confident
                    </span>
                  )}
                </div>

                {/* Text */}
                <p className={`transcript-text-enhanced ${
                  !isExpanded && isLongText ? "truncated" : ""
                }`}>
                  {highlightSearch(seg.text || "—", searchQuery)}
                </p>

                {/* Expand/Collapse for long text */}
                {isLongText && (
                  <button 
                    onClick={() => toggleExpand(originalIndex)}
                    className="expand-btn"
                  >
                    {isExpanded ? "Show Less ▲" : "Show More ▼"}
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

/* ---------------- Helpers ---------------- */

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
  if (confidence >= 0.9) return "#dcfce7"; // green
  if (confidence >= 0.75) return "#fef3c7"; // yellow
  return "#fee2e2"; // red
}

function highlightSearch(text, query) {
  if (!query.trim()) return text;
  
  const regex = new RegExp(`(${escapeRegex(query)})`, "gi");
  const parts = text.split(regex);
  
  return parts.map((part, i) => 
    regex.test(part) ? (
      <mark key={i} style={{ background: "#fef08a", padding: "2px 4px", borderRadius: "3px" }}>
        {part}
      </mark>
    ) : part
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

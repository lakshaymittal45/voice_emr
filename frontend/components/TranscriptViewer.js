"use client";

import { useMemo, useState } from "react";

export default function TranscriptViewer({ transcript }) {
  const [searchQuery, setSearchQuery] = useState("");
  const [speakerFilter, setSpeakerFilter] = useState("all");
  const [expandedItems, setExpandedItems] = useState(new Set());

  const getDisplayText = (seg) => seg?.text_romanized || seg?.text || "-";
  const hasWordConfidence = (seg) =>
    Array.isArray(seg?.word_confidences) && seg.word_confidences.length > 0;

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

  const stats = useMemo(() => {
    const totalWords = transcript.reduce(
      (sum, seg) => sum + getDisplayText(seg).split(/\s+/).filter((w) => w).length,
      0
    );
    const doctorCount = transcript.filter((s) => s.speaker === "Doctor").length;
    const patientCount = transcript.filter((s) => s.speaker === "Patient").length;
    const duration =
      transcript.length > 0
        ? transcript[transcript.length - 1].end - transcript[0].start
        : 0;

    return { totalWords, doctorCount, patientCount, duration };
  }, [transcript]);

  const filteredTranscript = useMemo(() => {
    let filtered = transcript;

    if (speakerFilter !== "all") {
      filtered = filtered.filter(
        (seg) => seg.speaker?.toLowerCase() === speakerFilter.toLowerCase()
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
  }, [transcript, speakerFilter, searchQuery]);

  const handleExport = (format) => {
    if (format === "txt") {
      const text = transcript
        .map(
          (seg) =>
            `[${formatTime(seg.start)} - ${formatTime(seg.end)}] ${seg.speaker}: ${getDisplayText(seg)}`
        )
        .join("\n\n");
      downloadFile(text, "transcript.txt", "text/plain");
    } else if (format === "json") {
      const json = JSON.stringify(transcript, null, 2);
      downloadFile(json, "transcript.json", "application/json");
    }
  };

  const handleCopyAll = () => {
    const text = transcript
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
            <span className="stat-value">{transcript.length}</span>
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
            <option value="doctor">Doctor Only</option>
            <option value="patient">Patient Only</option>
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
          Showing {filteredTranscript.length} of {transcript.length} segments
          {filteredTranscript.length === 0 && " - No matches found"}
        </div>
      )}

      <div className="transcript-content">
        {filteredTranscript.length === 0 ? (
          <p className="empty-text">No matching segments found.</p>
        ) : (
          filteredTranscript.map((seg) => {
            const originalIndex = transcript.indexOf(seg);
            const isExpanded = expandedItems.has(originalIndex);
            const displayText = getDisplayText(seg);
            const isLongText = displayText.length > 300;

            return (
              <div
                key={originalIndex}
                className={`transcript-line-enhanced ${
                  seg.speaker === "Doctor" ? "speaker-doctor" : "speaker-patient"
                }`}
              >
                <div className="transcript-header-enhanced">
                  <div className="speaker-info">
                    <span className="speaker-badge">
                      {seg.speaker === "Doctor" ? "DR" : "SP"}
                    </span>
                    <span className="speaker-name">{seg.speaker || "Speaker"}</span>
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

                <p
                  className={`transcript-text-enhanced ${
                    !isExpanded && isLongText ? "truncated" : ""
                  }`}
                >
                  {hasWordConfidence(seg) && !searchQuery.trim()
                    ? renderWordConfidence(seg.word_confidences)
                    : highlightSearch(displayText, searchQuery)}
                </p>

                {seg.text_native && seg.text_native !== displayText && (
                  <p className="transcript-text-enhanced" style={{ opacity: 0.68 }}>
                    {seg.text_native}
                  </p>
                )}

                {isLongText && (
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

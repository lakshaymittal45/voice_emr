export default function ClinicalNotes({ notes }) {
  if (!notes) return <p>No clinical notes generated.</p>;

  return (
    <section>
      <h2>📋 Clinical Notes</h2>

      {Object.entries(notes).map(([key, value]) => (
        <div key={key} style={{ marginBottom: 12 }}>
          <strong>{formatLabel(key)}:</strong>
          <p>{value || "—"}</p>
        </div>
      ))}
    </section>
  );
}

function formatLabel(label) {
  return label
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function ClinicalNotes({ notes }) {
  if (!notes) return <p>No clinical notes.</p>;

  return (
    <section>
      <h2>📋 Clinical Notes</h2>
      {Object.entries(notes).map(([k, v]) => (
        <div key={k}>
          <strong>{k.replace(/_/g, " ")}:</strong>
          <p>{v || "—"}</p>
        </div>
      ))}
    </section>
  );
}
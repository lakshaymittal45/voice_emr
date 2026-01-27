"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";

import TranscriptViewer from "@/components/TranscriptViewer";
import ClinicalNotes from "@/components/ClinicalNotes";

export default function ConsultationPage() {
  const { audioId } = useParams();
  const searchParams = useSearchParams();

  const role = searchParams.get("role") || "doctor";

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchConsultation() {
      try {
        setLoading(true);

        const res = await fetch(
          `http://127.0.0.1:8000/consultation/${audioId}?role=${role}`
        );

        if (!res.ok) {
          throw new Error("Failed to fetch consultation data");
        }

        const result = await res.json();
        setData(result);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchConsultation();
  }, [audioId, role]);

  if (loading) return <p>⏳ Loading consultation...</p>;
  if (error) return <p style={{ color: "red" }}>❌ {error}</p>;

  return (
    <main style={{ padding: 24 }}>
      <h1>🩺 Consultation View</h1>

      <p>
        <strong>Patient ID:</strong> {data.patient_id}
      </p>
      <p>
        <strong>Clinician:</strong> {data.clinician}
      </p>

      <hr />

      <TranscriptViewer transcript={data.transcript} />

      <hr />

      <ClinicalNotes notes={data.clinical_notes} />
    </main>
  );
}

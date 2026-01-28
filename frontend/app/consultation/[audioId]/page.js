"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";

import TranscriptViewer from "@/components/TranscriptViewer";
import ClinicalNotes from "@/components/ClinicalNotes";

export default function ConsultationPage() {
  const params = useParams();
  const searchParams = useSearchParams();

  const audioId = params?.audioId;
  const role = searchParams.get("role") || "doctor";

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchedRef = useRef(false);

  useEffect(() => {
    if (!audioId || fetchedRef.current) return;
    fetchedRef.current = true;

    async function fetchConsultation() {
      try {
        setLoading(true);
        const res = await fetch(
          `http://127.0.0.1:8000/consultation/${audioId}?role=${role}`
        );
        if (!res.ok) throw new Error("Fetch failed");
        setData(await res.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchConsultation();
  }, [audioId]);

  if (!audioId) return <p>Preparing consultation…</p>;
  if (loading) return <p>⏳ Loading consultation…</p>;
  if (error) return <p style={{ color: "red" }}>❌ {error}</p>;
  if (!data) return <p>No data found</p>;

  return (
    <main style={{ padding: 24 }}>
      <h1>🩺 Consultation View</h1>
      <p><strong>Patient:</strong> {data.patient_id}</p>
      <p><strong>Clinician:</strong> {data.clinician}</p>

      <hr />
      <TranscriptViewer transcript={data.transcript} />
      <hr />
      <ClinicalNotes notes={data.clinical_notes} />
    </main>
  );
}
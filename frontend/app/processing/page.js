"use client";

import { useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function ProcessingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const audioId = searchParams.get("audio_id");
  const role = searchParams.get("role") || "doctor";

  const intervalRef = useRef(null);

  useEffect(() => {
    if (!audioId || intervalRef.current) return;

    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(
          `http://127.0.0.1:8000/consultation-status/${audioId}`
        );

        if (!res.ok) return;

        const data = await res.json();

        if (data.status === "done") {
          clearInterval(intervalRef.current);
          intervalRef.current = null;

          router.push(`/consultation/${audioId}?role=${role}`);
        }
      } catch {
        // silent retry
      }
    }, 3000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [audioId, role, router]);

  return (
    <div className="processing-wrapper">
      <div className="processing-card">
        <div className="processing-spinner" />

        <h1>Processing Consultation</h1>

        <p>Your audio is being securely analyzed.</p>
        <p>This may take 1–2 minutes.</p>

        <p className="processing-note">
          Please keep this tab open.
        </p>
      </div>
    </div>
  );
}

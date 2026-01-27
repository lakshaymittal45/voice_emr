"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function AudioUploader() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleUpload = async () => {
    if (!file) {
      alert("Please select an audio file");
      return;
    }

    const formData = new FormData();
    formData.append("audio", file);
    formData.append("patient_id", "CASE_001");
    formData.append("clinician", "Dr. Demo");

    try {
      setLoading(true);

      const res = await fetch("http://127.0.0.1:8000/upload-consultation-audio", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      // redirect to consultation page
      router.push(`/consultation/${data.audio_id}`);
    } catch (err) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input
        type="file"
        accept="audio/*"
        onChange={(e) => setFile(e.target.files[0])}
      />

      <br /><br />

      <button onClick={handleUpload} disabled={loading}>
        {loading ? "Uploading..." : "Upload Consultation"}
      </button>
    </div>
  );
}

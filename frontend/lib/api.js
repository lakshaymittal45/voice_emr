const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

export async function uploadConsultationAudio(formData) {
  const res = await fetch(`${API_BASE}/upload-consultation-audio`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }

  return res.json();
}

export async function uploadConsultationAudioBulk(formData) {
  const res = await fetch(`${API_BASE}/upload-consultation-audio-bulk`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }

  return res.json();
}

export async function fetchConsultation(audioId, role = "doctor") {
  const res = await fetch(
    `${API_BASE}/consultation/${audioId}?role=${role}`
  );

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }

  return res.json();
}

export async function fetchConsultationStatus(audioId) {
  const res = await fetch(
    `${API_BASE}/consultation-status/${audioId}`
  );

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }

  return res.json();
}

export async function fetchConsultationStatusBatch(audioIds) {
  const res = await fetch(
    `${API_BASE}/consultation-status-batch`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(audioIds),
    }
  );

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }

  return res.json();
}

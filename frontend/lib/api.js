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

export async function startBulkProcessing(audioIds) {
  const res = await fetch(
    `${API_BASE}/bulk-start-processing`,
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

export async function removeQueuedAudio(audioId) {
  const res = await fetch(
    `${API_BASE}/bulk-remove-from-queue/${audioId}`,
    {
      method: "POST",
    }
  );

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }

  return res.json();
}

export async function fetchBulkUploadHistory(limit = 200) {
  const res = await fetch(`${API_BASE}/bulk-upload-history?limit=${limit}`);

  if (res.ok) {
    return res.json();
  }

  if (res.status !== 404) {
    const err = await res.text();
    throw new Error(err);
  }

  // Backward-compatible fallback when /bulk-upload-history is not available.
  const patientsRes = await fetch(`${API_BASE}/patients`);
  if (!patientsRes.ok) {
    const err = await patientsRes.text();
    throw new Error(err);
  }

  const patientsData = await patientsRes.json();
  const patients = patientsData?.patients || [];
  if (!patients.length) {
    return { status: "success", count: 0, history: [] };
  }

  const appointmentResponses = await Promise.all(
    patients.map(async (patient) => {
      const patientId = patient.patient_id;
      const encoded = encodeURIComponent(patientId);
      const apptRes = await fetch(`${API_BASE}/patient/${encoded}/appointments`);
      if (!apptRes.ok) {
        return [];
      }
      const apptData = await apptRes.json();
      return (apptData?.appointments || []).map((appt) => ({
        audio_id: appt.audio_id,
        patient_id: appt.patient_id,
        clinician: appt.handling_clinician,
        time_of_capture: appt.time_of_capture,
        created_at: appt.created_at,
      }));
    })
  );

  const appointments = appointmentResponses.flat();
  if (!appointments.length) {
    return { status: "success", count: 0, history: [] };
  }

  const audioIds = appointments.map((appt) => appt.audio_id).slice(0, Math.max(1, limit));
  const statusRes = await fetch(`${API_BASE}/consultation-status-batch`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(audioIds),
  });

  if (!statusRes.ok) {
    const err = await statusRes.text();
    throw new Error(err);
  }

  const statusData = await statusRes.json();
  const statusMap = statusData?.results || {};

  const history = appointments
    .filter((appt) => audioIds.includes(appt.audio_id))
    .map((appt) => ({
      audio_id: appt.audio_id,
      filename: `audio_${appt.audio_id}`,
      patient_id: appt.patient_id,
      clinician: appt.clinician,
      status: statusMap[appt.audio_id] || "unknown",
      time_of_capture: appt.time_of_capture,
      created_at: appt.created_at,
    }))
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
    .slice(0, limit);

  return {
    status: "success",
    count: history.length,
    history,
  };
}

export async function saveCorrectedTranscript(audioId, transcriptCorrected, role = "doctor") {
  const res = await fetch(
    `${API_BASE}/consultation/${audioId}/transcript?role=${role}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ transcript_corrected: transcriptCorrected }),
    }
  );

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }

  return res.json();
}

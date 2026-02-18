"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchConsultationStatusBatch } from "@/lib/api";

export default function ProcessingBulkPage() {
  const router = useRouter();
  
  const [uploadResults, setUploadResults] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [error, setError] = useState(null);
  const [role, setRole] = useState("doctor");

  useEffect(() => {
    // Load upload results from sessionStorage
    const stored = sessionStorage.getItem('bulkUploadResults');
    if (stored) {
      const data = JSON.parse(stored);
      setUploadResults(data);
      setRole(data.role || "doctor");
    } else {
      setError("No upload data found");
    }
  }, []);

  useEffect(() => {
    if (!uploadResults) return;

    // Get successful audio IDs
    const audioIds = uploadResults.results
      .filter(r => r.status === 'accepted')
      .map(r => r.audio_id);

    if (audioIds.length === 0) {
      return; // No files to track
    }

    // Poll for status updates
    const interval = setInterval(async () => {
      try {
        const data = await fetchConsultationStatusBatch(audioIds);
        setStatusData(data);

        // Check if all are done or failed
        const allComplete = Object.values(data.results).every(
          status => status === 'done' || status === 'failed'
        );

        if (allComplete) {
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Status check failed:", err);
        setError(err.message);
      }
    }, 5000); // Poll every 5 seconds

    // Initial fetch
    fetchConsultationStatusBatch(audioIds)
      .then(data => setStatusData(data))
      .catch(err => setError(err.message));

    return () => clearInterval(interval);
  }, [uploadResults]);

  if (error && !uploadResults) {
    return (
      <div className="page-wrapper">
        <div className="card">
          <p className="status-error">❌ {error}</p>
          <button onClick={() => router.push("/")} className="button-primary">
            Go Home
          </button>
        </div>
      </div>
    );
  }

  if (!uploadResults) {
    return (
      <div className="page-wrapper">
        <div className="card">
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  const successfulUploads = uploadResults.results.filter(r => r.status === 'accepted');
  const failedUploads = uploadResults.results.filter(r => r.status === 'rejected');

  const getStatusIcon = (status) => {
    switch(status) {
      case 'processing': return '⏳';
      case 'done': return '✅';
      case 'failed': return '❌';
      default: return '❓';
    }
  };

  const getStatusColor = (status) => {
    switch(status) {
      case 'processing': return '#f59e0b';
      case 'done': return '#10b981';
      case 'failed': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const allDone = statusData && 
    Object.values(statusData.results).every(s => s === 'done' || s === 'failed');

  return (
    <>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-inner">
          <button
            className="nav-back"
            onClick={() => router.push("/")}
          >
            ← Home
          </button>
          <div className="navbar-title">
            Bulk Processing Status
          </div>
        </div>
      </nav>

      {/* Page */}
      <div className="page-wrapper">
        {/* Summary Card */}
        <div className="card" style={{ marginBottom: '20px' }}>
          <h2>Upload Summary</h2>
          
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
            marginTop: '16px'
          }}>
            <div style={{ 
              padding: '16px', 
              background: '#f0f9ff', 
              borderRadius: '8px',
              border: '1px solid #bfdbfe'
            }}>
              <div style={{ fontSize: '24px', fontWeight: '700', color: '#1e40af' }}>
                {uploadResults.results.length}
              </div>
              <div style={{ fontSize: '14px', color: '#64748b' }}>Total Files</div>
            </div>

            <div style={{ 
              padding: '16px', 
              background: '#f0fdf4', 
              borderRadius: '8px',
              border: '1px solid #bbf7d0'
            }}>
              <div style={{ fontSize: '24px', fontWeight: '700', color: '#15803d' }}>
                {successfulUploads.length}
              </div>
              <div style={{ fontSize: '14px', color: '#64748b' }}>Accepted</div>
            </div>

            <div style={{ 
              padding: '16px', 
              background: '#fef2f2', 
              borderRadius: '8px',
              border: '1px solid #fecaca'
            }}>
              <div style={{ fontSize: '24px', fontWeight: '700', color: '#dc2626' }}>
                {failedUploads.length}
              </div>
              <div style={{ fontSize: '14px', color: '#64748b' }}>Rejected</div>
            </div>
          </div>

          {statusData && (
            <div style={{ marginTop: '20px', padding: '16px', background: '#f9fafb', borderRadius: '8px' }}>
              <h3 style={{ fontSize: '16px', marginBottom: '12px' }}>Processing Status</h3>
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: '12px'
              }}>
                <div>
                  <span style={{ fontSize: '20px', fontWeight: '600' }}>
                    {statusData.summary.processing}
                  </span>
                  <span style={{ marginLeft: '8px', color: '#f59e0b' }}>⏳ Processing</span>
                </div>
                <div>
                  <span style={{ fontSize: '20px', fontWeight: '600' }}>
                    {statusData.summary.done}
                  </span>
                  <span style={{ marginLeft: '8px', color: '#10b981' }}>✅ Done</span>
                </div>
                <div>
                  <span style={{ fontSize: '20px', fontWeight: '600' }}>
                    {statusData.summary.failed}
                  </span>
                  <span style={{ marginLeft: '8px', color: '#ef4444' }}>❌ Failed</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Successful Uploads - Processing Status */}
        {successfulUploads.length > 0 && (
          <div className="card" style={{ marginBottom: '20px' }}>
            <h2>Processing Files ({successfulUploads.length})</h2>
            
            <div style={{ marginTop: '16px' }}>
              {successfulUploads.map((result, index) => {
                const currentStatus = statusData?.results[result.audio_id] || 'processing';
                
                return (
                  <div 
                    key={result.audio_id}
                    style={{
                      padding: '16px',
                      background: 'white',
                      borderRadius: '8px',
                      marginBottom: '12px',
                      border: '1px solid #e5e7eb',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: '600', fontSize: '14px' }}>
                        {result.filename}
                      </div>
                      <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                        Audio ID: {result.audio_id}
                      </div>
                    </div>
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ 
                        fontSize: '14px', 
                        fontWeight: '600',
                        color: getStatusColor(currentStatus)
                      }}>
                        {getStatusIcon(currentStatus)} {currentStatus.toUpperCase()}
                      </span>
                      
                      {currentStatus === 'done' && (
                        <button
                          onClick={() => router.push(`/consultation/${result.audio_id}?role=${role}`)}
                          style={{
                            padding: '6px 16px',
                            background: '#3b82f6',
                            color: 'white',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            fontSize: '14px',
                            fontWeight: '500'
                          }}
                        >
                          View
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Failed Uploads */}
        {failedUploads.length > 0 && (
          <div className="card">
            <h2 style={{ color: '#dc2626' }}>Rejected Files ({failedUploads.length})</h2>
            
            <div style={{ marginTop: '16px' }}>
              {failedUploads.map((result, index) => (
                <div 
                  key={index}
                  style={{
                    padding: '16px',
                    background: '#fef2f2',
                    borderRadius: '8px',
                    marginBottom: '12px',
                    border: '1px solid #fecaca'
                  }}
                >
                  <div style={{ fontWeight: '600', fontSize: '14px', color: '#dc2626' }}>
                    {result.filename}
                  </div>
                  <div style={{ fontSize: '13px', color: '#991b1b', marginTop: '4px' }}>
                    ❌ {result.error}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ marginTop: '24px', display: 'flex', gap: '12px', justifyContent: 'center' }}>
          <button
            onClick={() => router.push("/upload-bulk")}
            className="button-primary"
          >
            Upload More Files
          </button>
          
          {allDone && (
            <button
              onClick={() => router.push("/")}
              style={{
                padding: '12px 24px',
                background: 'white',
                color: '#3b82f6',
                border: '1px solid #3b82f6',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '16px',
                fontWeight: '500'
              }}
            >
              Go Home
            </button>
          )}
        </div>
      </div>
    </>
  );
}

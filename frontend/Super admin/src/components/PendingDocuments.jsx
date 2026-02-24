import React, { useState, useEffect } from "react";
import {
  FileText,
  Clock,
  CheckCircle,
  XCircle,
  Calendar,
  Play,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const PendingDocuments = ({ onApprove, onReject, onSchedule, onTrigger }) => {
  const { apiCall } = useAuth();
  const [pendingDocs, setPendingDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [showRejectionModal, setShowRejectionModal] = useState(false);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [processSchedule, setProcessSchedule] = useState("immediate");
  const [scheduledAt, setScheduledAt] = useState("");
  const [comments, setComments] = useState("");

  useEffect(() => {
    loadPendingDocuments();
  }, []);

  const loadPendingDocuments = async () => {
    try {
      setLoading(true);
      const data = await apiCall("/super-admin/pending-documents");
      setPendingDocs(data.pending_documents || []);
    } catch (error) {
      console.error("Failed to load pending documents:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    try {
      await apiCall("/super-admin/approve-document", {
        method: "POST",
        body: JSON.stringify({
          document_id: selectedDoc.id,
          comments: comments,
          process_schedule: processSchedule,
          scheduled_at: processSchedule === "scheduled" ? scheduledAt : null,
        }),
      });
      setShowApprovalModal(false);
      setSelectedDoc(null);
      setComments("");
      setProcessSchedule("immediate");
      setScheduledAt("");
      await loadPendingDocuments();
      if (onApprove) onApprove();
    } catch (error) {
      alert("Failed to approve document: " + error.message);
    }
  };

  const handleReject = async () => {
    try {
      await apiCall("/super-admin/reject-document", {
        method: "POST",
        body: JSON.stringify({
          document_id: selectedDoc.id,
          reason: comments,
        }),
      });
      setShowRejectionModal(false);
      setSelectedDoc(null);
      setComments("");
      await loadPendingDocuments();
      if (onReject) onReject();
    } catch (error) {
      alert("Failed to reject document: " + error.message);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
  };

  if (loading) {
    return (
      <div className="text-center py-12">Loading pending documents...</div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-[var(--text-primary)]">
          Pending Documents
        </h2>
        <button
          onClick={loadPendingDocuments}
          className="swiss-btn-secondary px-4 py-2 text-sm font-semibold"
        >
          Refresh
        </button>
      </div>

      {pendingDocs.length === 0 ? (
        <div className="text-center py-12 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-soft)]">
          <FileText
            className="mx-auto text-[var(--text-muted)] mb-4"
            size={48}
          />
          <p className="text-[var(--text-secondary)]">No pending documents</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {pendingDocs.map((doc) => (
            <div
              key={doc.id}
              className="swiss-card p-6 transition-all hover:border-[var(--border-strong)]"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <FileText className="text-[var(--accent)]" size={24} />
                    <h3 className="text-lg font-bold text-[var(--text-primary)]">
                      {doc.filename}
                    </h3>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm text-[var(--text-secondary)] mb-4">
                    <div>
                      <span className="font-semibold">College:</span>{" "}
                      {doc.college_name}
                    </div>
                    <div>
                      <span className="font-semibold">Uploaded by:</span>{" "}
                      {doc.uploader_email}
                    </div>
                    <div>
                      <span className="font-semibold">Type:</span>{" "}
                      {doc.file_type?.toUpperCase()}
                    </div>
                    <div>
                      <span className="font-semibold">Size:</span>{" "}
                      {formatFileSize(doc.file_size)}
                    </div>
                    <div>
                      <span className="font-semibold">Uploaded:</span>{" "}
                      {new Date(doc.uploaded_at).toLocaleString()}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setSelectedDoc(doc);
                      setShowApprovalModal(true);
                    }}
                    className="swiss-btn-primary flex items-center gap-2 px-4 py-2 text-sm"
                  >
                    <CheckCircle size={18} />
                    Approve
                  </button>
                  <button
                    onClick={() => {
                      setSelectedDoc(doc);
                      setShowRejectionModal(true);
                    }}
                    className="swiss-btn-danger flex items-center gap-2 px-4 py-2 text-sm"
                  >
                    <XCircle size={18} />
                    Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Approval Modal */}
      {showApprovalModal && selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101418]/45 p-4">
          <div className="w-full max-w-md rounded-xl border border-[var(--border-soft)] bg-[var(--bg-surface)] p-8">
            <h3 className="text-xl font-bold mb-4">Approve Document</h3>
            <p className="text-[var(--text-secondary)] mb-6">
              {selectedDoc.filename}
            </p>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-semibold mb-2">
                  Processing Schedule
                </label>
                <select
                  value={processSchedule}
                  onChange={(e) => setProcessSchedule(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-subtle)] px-4 py-2"
                >
                  <option value="immediate">Process Immediately</option>
                  <option value="scheduled">Schedule for Later</option>
                  <option value="manual">Manual Trigger</option>
                </select>
              </div>

              {processSchedule === "scheduled" && (
                <div>
                  <label className="block text-sm font-semibold mb-2">
                    Scheduled Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    value={scheduledAt}
                    onChange={(e) => setScheduledAt(e.target.value)}
                    className="w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-subtle)] px-4 py-2"
                    min={new Date().toISOString().slice(0, 16)}
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-semibold mb-2">
                  Comments (Optional)
                </label>
                <textarea
                  value={comments}
                  onChange={(e) => setComments(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-subtle)] px-4 py-2"
                  rows="3"
                  placeholder="Add any comments about this approval..."
                />
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowApprovalModal(false);
                  setSelectedDoc(null);
                  setComments("");
                  setProcessSchedule("immediate");
                  setScheduledAt("");
                }}
                className="swiss-btn-secondary flex-1 px-4 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleApprove}
                className="swiss-btn-primary flex-1 px-4 py-2 text-sm"
              >
                Approve
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rejection Modal */}
      {showRejectionModal && selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101418]/45 p-4">
          <div className="w-full max-w-md rounded-xl border border-[var(--border-soft)] bg-[var(--bg-surface)] p-8">
            <h3 className="text-xl font-bold mb-4">Reject Document</h3>
            <p className="text-[var(--text-secondary)] mb-6">
              {selectedDoc.filename}
            </p>

            <div className="mb-6">
              <label className="block text-sm font-semibold mb-2">
                Rejection Reason *
              </label>
              <textarea
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                className="w-full rounded-lg border border-[var(--border-soft)] bg-[var(--bg-subtle)] px-4 py-2"
                rows="4"
                placeholder="Please provide a reason for rejection..."
                required
              />
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowRejectionModal(false);
                  setSelectedDoc(null);
                  setComments("");
                }}
                className="swiss-btn-secondary flex-1 px-4 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={!comments.trim()}
                className="flex-1 rounded-lg border border-[var(--danger)] bg-[var(--danger)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:opacity-90 disabled:opacity-50"
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PendingDocuments;

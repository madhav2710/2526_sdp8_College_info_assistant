import React, { useState, useMemo } from "react";
import { adminAPI } from "./services/api";
import {
  Upload,
  FileText,
  Database,
  History,
  CheckCircle,
  Clock,
  AlertCircle,
  Search,
  ChevronRight,
  BarChart3,
  ShieldCheck,
  Filter,
  RefreshCw,
  Info,
  Menu,
  X,
} from "lucide-react";

const StatusBadge = ({ status, ragStatus }) => {
  const styles = {
    Ingested:
      "bg-[var(--bg-subtle)] text-[var(--success)] border-[var(--border-soft)]",
    Completed:
      "bg-[var(--bg-subtle)] text-[var(--success)] border-[var(--border-soft)]",
    "RAG Ready":
      "bg-[var(--bg-subtle)] text-[var(--success)] border-[var(--border-soft)]",
    Pending:
      "bg-[var(--bg-subtle)] text-[var(--warning)] border-[var(--border-soft)]",
    "Pending Approval":
      "bg-[var(--bg-subtle)] text-[var(--warning)] border-[var(--border-soft)]",
    Uploaded:
      "bg-[var(--bg-subtle)] text-[var(--warning)] border-[var(--border-soft)]",
    Processing:
      "bg-[var(--bg-subtle)] text-[var(--info)] border-[var(--border-soft)]",
    "RAG Processing":
      "bg-[var(--bg-subtle)] text-[var(--info)] border-[var(--border-soft)]",
    Ingesting:
      "bg-[var(--bg-subtle)] text-[var(--info)] border-[var(--border-soft)]",
    Failed:
      "bg-[var(--bg-subtle)] text-[var(--danger)] border-[var(--border-soft)]",
    Approved:
      "bg-[var(--bg-subtle)] text-[var(--info)] border-[var(--border-soft)]",
  };

  const icons = {
    Ingested: <CheckCircle size={14} className="mr-1" />,
    Completed: <CheckCircle size={14} className="mr-1" />,
    "RAG Ready": <CheckCircle size={14} className="mr-1" />,
    Pending: <Clock size={14} className="mr-1" />,
    "Pending Approval": <Clock size={14} className="mr-1" />,
    Uploaded: <Clock size={14} className="mr-1" />,
    Processing: <RefreshCw size={14} className="mr-1 animate-spin" />,
    "RAG Processing": <RefreshCw size={14} className="mr-1 animate-spin" />,
    Ingesting: <RefreshCw size={14} className="mr-1 animate-spin" />,
    Failed: <AlertCircle size={14} className="mr-1" />,
    Approved: <CheckCircle size={14} className="mr-1" />,
  };

  // Determine display status based on document status and RAG readiness
  let displayStatus = status;
  if (status === "Completed" && ragStatus?.is_rag_ready) {
    displayStatus = "RAG Ready";
  } else if (status === "Processing" && ragStatus?.processing_progress) {
    displayStatus = "RAG Processing";
  } else if (status === "Pending Approval") {
    displayStatus = "Pending Approval";
  }

  return (
    <span className={`status-pill ${styles[displayStatus] || styles[status]}`}>
      {icons[displayStatus] || icons[status]}
      {displayStatus}
    </span>
  );
};

const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(
    !!localStorage.getItem("admin_token"),
  );
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");
  const [documents, setDocuments] = useState([]);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  React.useEffect(() => {
    const syncSidebar = () => setSidebarOpen(window.innerWidth >= 1024);
    syncSidebar();
    window.addEventListener("resize", syncSidebar);
    return () => window.removeEventListener("resize", syncSidebar);
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError("");
    try {
      const data = await adminAPI.login(loginEmail, loginPassword);
      if (data.role === "college_admin") {
        localStorage.setItem("admin_token", data.access_token);
        localStorage.setItem("admin_college_id", data.college_id);
        setIsAuthenticated(true);
      } else {
        setLoginError("Access denied. You must be a college admin.");
      }
    } catch (error) {
      setLoginError(error.message || "Could not connect to server.");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_college_id");
    setIsAuthenticated(false);
  };

  // Fetch documents from API
  const fetchDocuments = async () => {
    if (!isAuthenticated) return;
    try {
      const data = await adminAPI.getDocuments();
      // The API returns { documents: [...], statistics: {...}, ... }
      const documentsList = data.documents || data;
      setDocuments(
        documentsList.map((doc) => ({
          id: doc.id,
          name: doc.filename,
          type:
            doc.file_type && doc.file_type.includes("pdf")
              ? "PDF"
              : (doc.file_type || "Document").toUpperCase(),
          size: doc.file_size
            ? `${(doc.file_size / 1024 / 1024).toFixed(2)} MB`
            : "Unknown",
          status: (doc.status || "unknown")
            .replace(/_/g, " ")
            .replace(/\b\w/g, (char) => char.toUpperCase()),
          date: doc.created_at ? doc.created_at.split("T")[0] : "N/A",
          ragStatus: doc.rag_status || {
            is_rag_ready: false,
            chunk_count: 0,
            processing_progress: null,
            can_be_queried: false,
          },
          processingProgress: doc.rag_status?.processing_progress,
        })),
      );
    } catch (error) {
      console.error("Error fetching documents:", error);
    }
  };

  const fetchQueryHistory = async () => {
    if (!isAuthenticated) return;
    try {
      setHistoryLoading(true);
      const data = await adminAPI.getQueryHistory(50);
      const queryHistory = data.query_history || [];

      setHistory(
        queryHistory.map((item) => ({
          id: item.id,
          query: item.query || "No query available",
          title: item.title || "Untitled conversation",
          timestamp: item.created_at
            ? new Date(item.created_at).toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })
            : "Unknown time",
          messageCount: item.message_count || 0,
          sources: [],
        })),
      );
    } catch (error) {
      console.error("Error fetching query history:", error);
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  React.useEffect(() => {
    if (isAuthenticated) {
      fetchDocuments();
      fetchQueryHistory();
      // Poll for updates every 10 seconds to see status changes
      const interval = setInterval(() => {
        fetchDocuments();
        fetchQueryHistory();
      }, 10000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated]);

  // Stats calculation with RAG processing metrics
  const stats = useMemo(
    () => ({
      total: documents.length,
      ingested: documents.filter(
        (d) => d.status === "Completed" || d.status === "Ingested",
      ).length,
      ragReady: documents.filter((d) => d.ragStatus?.is_rag_ready).length,
      pending: documents.filter(
        (d) =>
          d.status === "Processing" ||
          d.status === "Pending" ||
          d.status === "Pending Approval" ||
          d.status === "Uploaded",
      ).length,
      failed: documents.filter((d) => d.status === "Failed").length,
      processing: documents.filter((d) => d.status === "Processing").length,
    }),
    [documents],
  );

  const showNotification = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3000);
  };

  const historyMetrics = useMemo(() => {
    if (history.length === 0) {
      return {
        totalConversations: 0,
        totalMessages: 0,
        avgMessagesPerConversation: 0,
      };
    }

    const totalMessages = history.reduce(
      (total, item) => total + (item.messageCount || 0),
      0,
    );

    return {
      totalConversations: history.length,
      totalMessages,
      avgMessagesPerConversation: (totalMessages / history.length).toFixed(1),
    };
  }, [history]);

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setIsUploading(true);
    let successCount = 0;

    for (const file of files) {
      try {
        await adminAPI.uploadDocument(file);
        successCount++;
      } catch (error) {
        console.error("Error uploading file:", error);
      }
    }

    setIsUploading(false);
    if (successCount > 0) {
      showNotification(
        `Successfully uploaded ${successCount} document(s). Awaiting super admin approval.`,
      );
      fetchDocuments();
    } else {
      showNotification("Failed to upload documents.", "error");
    }
  };

  const triggerRagProcessing = async (id) => {
    try {
      setDocuments((prev) =>
        prev.map((doc) =>
          doc.id === id ? { ...doc, status: "Processing" } : doc,
        ),
      );

      await adminAPI.triggerRagProcessing(id);
      showNotification("RAG processing started successfully.");

      // Refresh documents to get updated status
      setTimeout(() => {
        fetchDocuments();
      }, 1000);
    } catch (error) {
      console.error("Error triggering RAG processing:", error);
      showNotification("Failed to start RAG processing.", "error");

      // Revert status change on error
      fetchDocuments();
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-canvas)] px-4">
        <div className="swiss-card w-full max-w-md p-8">
          <div className="flex items-center gap-3 mb-8 justify-center">
            <div className="rounded-lg bg-[var(--accent)] p-2 text-white">
              <Database className="text-white" size={24} />
            </div>
            <span className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
              EduQuery Admin
            </span>
          </div>

          <h2 className="mb-2 text-center text-xl font-bold text-[var(--text-primary)]">
            Welcome Back
          </h2>
          <p className="mb-8 text-center text-sm text-[var(--text-secondary)]">
            Sign in to manage your college knowledge base.
          </p>

          {loginError && (
            <div className="mb-6 p-4 bg-red-50 border border-red-100 text-red-700 text-sm rounded-xl flex items-center gap-2">
              <AlertCircle size={16} />
              {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="mb-1.5 block text-sm font-semibold text-[var(--text-secondary)]">
                Email Address
              </label>
              <input
                type="email"
                required
                className="w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-surface)] px-4 py-3 focus:outline-none"
                placeholder="admin@college.edu"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-semibold text-[var(--text-secondary)]">
                Password
              </label>
              <input
                type="password"
                required
                className="w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-surface)] px-4 py-3 focus:outline-none"
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
              />
            </div>
            <button type="submit" className="swiss-btn-primary w-full py-3">
              Sign In
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      {sidebarOpen && (
        <button
          className="fixed inset-0 z-30 bg-[#101418]/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close sidebar overlay"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed z-40 h-full w-64 border-r border-[#202830] bg-[var(--sidebar-bg)] text-[var(--sidebar-text)] transition-transform duration-[180ms] ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } lg:translate-x-0`}
      >
        <div className="flex items-center gap-3 border-b border-[#202830] p-6">
          <div className="rounded-lg bg-[var(--accent)] p-2 text-white">
            <Database className="text-white" size={24} />
          </div>
          <span className="text-xl font-bold tracking-tight text-[#f5f7f8]">
            EduQuery Admin
          </span>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          <button
            onClick={() => {
              setActiveTab("dashboard");
              if (window.innerWidth < 1024) setSidebarOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === "dashboard"
                ? "bg-[var(--sidebar-active)] text-[#f5f7f8] font-semibold border-l-[3px] border-[var(--accent)]"
                : "text-[var(--sidebar-text)] hover:bg-[var(--sidebar-active)]"
            }`}
          >
            <BarChart3 size={20} />
            Dashboard
          </button>
          <button
            onClick={() => {
              setActiveTab("documents");
              if (window.innerWidth < 1024) setSidebarOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === "documents"
                ? "bg-[var(--sidebar-active)] text-[#f5f7f8] font-semibold border-l-[3px] border-[var(--accent)]"
                : "text-[var(--sidebar-text)] hover:bg-[var(--sidebar-active)]"
            }`}
          >
            <FileText size={20} />
            Documents
          </button>
          <button
            onClick={() => {
              setActiveTab("history");
              if (window.innerWidth < 1024) setSidebarOpen(false);
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === "history"
                ? "bg-[var(--sidebar-active)] text-[#f5f7f8] font-semibold border-l-[3px] border-[var(--accent)]"
                : "text-[var(--sidebar-text)] hover:bg-[var(--sidebar-active)]"
            }`}
          >
            <History size={20} />
            Query History
          </button>
        </nav>

        <div className="border-t border-[#202830] p-4">
          <div className="rounded-2xl border border-[#2a333d] bg-[#131a21] p-4 text-white">
            <div className="flex items-center gap-2 mb-2">
              <ShieldCheck size={16} className="text-[var(--accent)]" />
              <span className="text-xs font-medium uppercase tracking-wider opacity-70">
                College Account
              </span>
            </div>
            <p className="text-sm font-semibold truncate">Admin Panel</p>
            <button
              onClick={handleLogout}
              className="mt-3 w-full rounded-lg border border-[#3a434d] bg-transparent py-2 text-xs transition-colors hover:bg-[#1d2731]"
            >
              Sign Out
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-4 sm:p-6 lg:ml-64 lg:p-8">
        {/* Header */}
        <header className="mb-8 flex items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <button
              onClick={() => setSidebarOpen((prev) => !prev)}
              className="swiss-btn-secondary flex h-10 w-10 items-center justify-center p-0 lg:hidden"
              aria-label="Toggle sidebar"
            >
              {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
            </button>

            <div>
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                {activeTab === "dashboard" && "Admin Overview"}
                {activeTab === "documents" && "Document Management"}
                {activeTab === "history" && "Student Query History"}
              </h1>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                {activeTab === "dashboard" &&
                  "Real-time status of your knowledge base."}
                {activeTab === "documents" &&
                  "Upload documents and monitor live processing status."}
                {activeTab === "history" &&
                  "Monitor how students are interacting with AI."}
              </p>
            </div>
          </div>

          <div className="flex gap-3">
            <button className="relative rounded-lg border border-[var(--border-soft)] bg-[var(--bg-surface)] p-2 text-[var(--text-secondary)]">
              <Info size={20} />
            </button>
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border-soft)] bg-[var(--bg-subtle)] font-bold text-[var(--text-primary)]">
              AD
            </div>
          </div>
        </header>

        {/* Notification Toast */}
        {notification && (
          <div
            className={`fixed bottom-8 right-8 z-50 flex items-center gap-3 rounded-xl border px-6 py-4 shadow-sm ${
              notification.type === "success"
                ? "bg-[var(--bg-surface)] border-[var(--success)]/30 text-[var(--success)]"
                : "bg-[var(--bg-surface)] border-[var(--danger)]/30 text-[var(--danger)]"
            }`}
          >
            {notification.type === "success" ? (
              <CheckCircle className="text-green-500" />
            ) : (
              <AlertCircle className="text-red-500" />
            )}
            <span className="font-medium">{notification.msg}</span>
          </div>
        )}

        {/* Dashboard Tab Content */}
        {activeTab === "dashboard" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              {[
                {
                  label: "Total Docs",
                  value: stats.total,
                  color:
                    "bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--border-soft)]",
                  icon: FileText,
                },
                {
                  label: "RAG Ready",
                  value: stats.ragReady,
                  color:
                    "bg-[var(--bg-subtle)] text-[var(--success)] border-[var(--border-soft)]",
                  icon: CheckCircle,
                },
                {
                  label: "Ingested",
                  value: stats.ingested,
                  color:
                    "bg-[var(--bg-subtle)] text-[var(--success)] border-[var(--border-soft)]",
                  icon: CheckCircle,
                },
                {
                  label: "Processing",
                  value: stats.processing,
                  color:
                    "bg-[var(--bg-subtle)] text-[var(--info)] border-[var(--border-soft)]",
                  icon: RefreshCw,
                },
                {
                  label: "Failed",
                  value: stats.failed,
                  color:
                    "bg-[var(--bg-subtle)] text-[var(--danger)] border-[var(--border-soft)]",
                  icon: AlertCircle,
                },
              ].map((item, i) => (
                <div
                  key={i}
                  className="swiss-card flex items-center justify-between p-6"
                >
                  <div>
                    <p className="text-sm font-medium text-[var(--text-secondary)]">
                      {item.label}
                    </p>
                    <h3 className="mt-1 text-3xl font-bold text-[var(--text-primary)]">
                      {item.value}
                    </h3>
                  </div>
                  <div className={`${item.color} rounded-xl border p-3`}>
                    <item.icon size={24} />
                  </div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="swiss-card p-6">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="font-bold text-lg">Processing Queue</h3>
                  <button
                    onClick={() => setActiveTab("documents")}
                    className="text-[var(--accent)] text-sm font-semibold hover:underline"
                  >
                    View All
                  </button>
                </div>

                <div className="space-y-4">
                  {documents
                    .filter(
                      (d) =>
                        d.status === "Pending" ||
                        d.status === "Pending Approval" ||
                        d.status === "Uploaded" ||
                        d.status === "Processing" ||
                        d.status === "Approved",
                    )
                    .slice(0, 3)
                    .map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between p-4 bg-[var(--bg-subtle)] rounded-xl border border-[var(--border-soft)]"
                      >
                        <div className="flex items-center gap-3">
                          <div className="bg-[var(--bg-surface)] p-2 rounded-lg border border-[var(--border-soft)]">
                            <FileText
                              size={18}
                              className="text-[var(--text-muted)]"
                            />
                          </div>
                          <div>
                            <p className="text-sm font-semibold truncate max-w-[150px]">
                              {doc.name}
                            </p>
                            <p className="text-xs text-[var(--text-secondary)]">
                              {doc.size}
                            </p>
                            {doc.status === "Processing" &&
                              doc.processingProgress && (
                                <p className="text-xs text-[var(--info)] mt-1">
                                  RAG Processing...
                                </p>
                              )}
                          </div>
                        </div>

                        {doc.status === "Pending" ||
                        doc.status === "Pending Approval" ||
                        doc.status === "Uploaded" ? (
                          <div className="px-3 py-1.5 bg-amber-50 text-amber-700 text-xs font-semibold rounded-lg border border-amber-200">
                            Awaiting approval
                          </div>
                        ) : doc.status === "Approved" ? (
                          <button
                            onClick={() => triggerRagProcessing(doc.id)}
                            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5"
                          >
                            <RefreshCw size={12} />
                            Start RAG
                          </button>
                        ) : (
                          <div className="flex items-center gap-2 text-[var(--info)]">
                            <RefreshCw size={14} className="animate-spin" />
                            <span className="text-xs font-medium">
                              Processing
                            </span>
                          </div>
                        )}
                      </div>
                    ))}

                  {documents.filter(
                    (d) =>
                      d.status === "Pending" ||
                      d.status === "Pending Approval" ||
                      d.status === "Uploaded" ||
                      d.status === "Processing" ||
                      d.status === "Approved",
                  ).length === 0 && (
                    <div className="text-center py-8">
                      <p className="text-[var(--text-muted)] text-sm italic">
                        No documents pending processing.
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="swiss-card p-6">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="font-bold text-lg">Recent Queries</h3>
                  <button
                    onClick={() => setActiveTab("history")}
                    className="text-[var(--accent)] text-sm font-semibold hover:underline"
                  >
                    Full Logs
                  </button>
                </div>

                <div className="space-y-4">
                  {historyLoading ? (
                    <div className="text-sm text-[var(--text-secondary)]">
                      Loading query history...
                    </div>
                  ) : history.length === 0 ? (
                    <div className="text-sm text-[var(--text-secondary)]">
                      No query history available yet.
                    </div>
                  ) : (
                    history.slice(0, 3).map((item) => (
                      <div
                        key={item.id}
                        className="p-4 bg-[var(--bg-subtle)] rounded-xl border border-[var(--border-soft)]"
                      >
                        <p className="text-sm text-[var(--text-primary)] line-clamp-1 italic">
                          &quot;{item.query}&quot;
                        </p>
                        <div className="flex items-center justify-between mt-3">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1">
                            <History size={10} /> {item.timestamp}
                          </span>
                          <span className="text-xs font-semibold text-[var(--accent)]">
                            {item.title}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Documents Tab Content */}
        {activeTab === "documents" && (
          <div className="space-y-6">
            {/* Upload Area */}
            <div className="swiss-card relative border-2 border-dashed border-[var(--border-strong)] p-10 transition-all hover:border-[var(--accent)] group">
              <input
                type="file"
                multiple
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFileUpload}
                disabled={isUploading}
              />
              <div className="flex flex-col items-center justify-center text-center">
                <div
                  className={`p-4 rounded-full mb-4 transition-colors ${
                    isUploading
                      ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                      : "bg-[var(--accent-soft)] text-[var(--accent)] group-hover:bg-[var(--accent-soft)]"
                  }`}
                >
                  <Upload size={32} />
                </div>
                <h3 className="text-lg font-bold text-[var(--text-primary)]">
                  {isUploading
                    ? "Uploading files..."
                    : "Upload College Documents"}
                </h3>
                <p className="text-[var(--text-secondary)] mt-1 max-w-sm">
                  Drag and drop your syllabus, placement PDFs, or notices here.
                  Supports PDF, DOCX, and TXT.
                </p>
              </div>
            </div>

            {/* Document List */}
            <div className="swiss-card overflow-hidden">
              <div className="p-6 border-b border-[var(--border-soft)] flex flex-col sm:flex-row justify-between gap-4">
                <div className="relative flex-1 max-w-md">
                  <Search
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                    size={18}
                  />
                  <input
                    type="text"
                    placeholder="Search documents..."
                    className="w-full pl-10 pr-4 py-2 bg-[var(--bg-subtle)] border border-[var(--border-soft)] rounded-xl focus:outline-none focus:ring-2 focus:ring-[var(--accent-soft)] text-sm"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                <div className="flex gap-2">
                  <button className="flex items-center gap-2 rounded-xl border border-[var(--border-soft)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]">
                    <Filter size={16} />
                    Filters
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="bg-[var(--bg-subtle)] text-[var(--text-secondary)] text-xs uppercase tracking-wider font-semibold">
                    <tr>
                      <th className="px-6 py-4">Document Name</th>
                      <th className="px-6 py-4">Type</th>
                      <th className="px-6 py-4">Size</th>
                      <th className="px-6 py-4">Status</th>
                      <th className="px-6 py-4">RAG Status</th>
                      <th className="px-6 py-4">Upload Date</th>
                      <th className="px-6 py-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-soft)]">
                    {documents
                      .filter((d) =>
                        d.name.toLowerCase().includes(searchTerm.toLowerCase()),
                      )
                      .map((doc) => (
                        <tr
                          key={doc.id}
                          className="hover:bg-[var(--bg-subtle)] transition-colors group"
                        >
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <div className="p-2 bg-[var(--accent-soft)] text-[var(--accent)] rounded-lg group-hover:bg-[var(--accent)] group-hover:text-white transition-colors">
                                <FileText size={18} />
                              </div>
                              <span className="text-sm font-semibold text-[var(--text-primary)]">
                                {doc.name}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-xs text-[var(--text-secondary)] bg-[var(--bg-subtle)] px-2 py-1 rounded-md">
                              {doc.type}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-xs text-[var(--text-secondary)]">
                            {doc.size}
                          </td>
                          <td className="px-6 py-4">
                            <StatusBadge
                              status={doc.status}
                              ragStatus={doc.ragStatus}
                            />
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-col gap-1">
                              {doc.ragStatus?.is_rag_ready ? (
                                <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
                                  <CheckCircle size={12} />
                                  Ready ({doc.ragStatus.chunk_count} chunks)
                                </span>
                              ) : doc.status === "Processing" ? (
                                <span className="text-xs text-[var(--info)] font-medium flex items-center gap-1">
                                  <RefreshCw
                                    size={12}
                                    className="animate-spin"
                                  />
                                  Processing...
                                </span>
                              ) : doc.status === "Completed" ? (
                                <span className="text-xs text-yellow-600 font-medium flex items-center gap-1">
                                  <Clock size={12} />
                                  Indexing pending
                                </span>
                              ) : (
                                <span className="text-xs text-[var(--text-muted)]">
                                  Not processed
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-xs text-[var(--text-secondary)]">
                            {doc.date}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex justify-end gap-2">
                              {(doc.status === "Pending" ||
                                doc.status === "Pending Approval" ||
                                doc.status === "Uploaded") && (
                                <div
                                  className="px-2 py-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md"
                                  title="Pending super admin approval"
                                >
                                  Awaiting approval
                                </div>
                              )}
                              {(doc.status === "Approved" ||
                                doc.status === "Failed") && (
                                <button
                                  onClick={() => triggerRagProcessing(doc.id)}
                                  className="p-2 text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                                  title="Start RAG Processing"
                                >
                                  <RefreshCw size={16} />
                                </button>
                              )}
                              {doc.ragStatus?.is_rag_ready && (
                                <div
                                  className="p-2 text-emerald-600"
                                  title="Ready for queries"
                                >
                                  <CheckCircle size={16} />
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* History Tab Content */}
        {activeTab === "history" && (
          <div className="space-y-6">
            <div className="swiss-card">
              <div className="p-6 border-b border-[var(--border-soft)] flex items-center justify-between">
                <h3 className="font-bold text-lg">
                  Knowledge Base Interactions
                </h3>
                <div className="flex gap-2">
                  <button className="text-xs font-bold text-[var(--accent)] hover:underline">
                    Export CSV
                  </button>
                </div>
              </div>

              <div className="divide-y divide-[var(--border-soft)]">
                {historyLoading ? (
                  <div className="p-6 text-sm text-[var(--text-secondary)]">
                    Loading query history...
                  </div>
                ) : history.length === 0 ? (
                  <div className="p-6 text-sm text-[var(--text-secondary)]">
                    No query history available yet.
                  </div>
                ) : (
                  history.map((item) => (
                    <div
                      key={item.id}
                      className="p-6 hover:bg-[var(--bg-subtle)] transition-colors"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-2">
                          <span className="bg-[var(--accent-soft)] text-[var(--accent)] text-[10px] font-bold px-2 py-0.5 rounded uppercase">
                            Conversation: {item.title}
                          </span>
                          <span className="text-[var(--text-muted)] text-xs">
                            {item.timestamp}
                          </span>
                        </div>
                        <button className="text-[var(--text-muted)] hover:text-[var(--accent)]">
                          <ChevronRight size={20} />
                        </button>
                      </div>

                      <p className="text-[var(--text-primary)] font-medium mb-4">
                        &quot;{item.query}&quot;
                      </p>

                      <div className="flex flex-wrap gap-2 items-center">
                        <span className="text-[10px] text-[var(--text-muted)] uppercase font-bold tracking-tight">
                          Messages in Conversation:
                        </span>
                        <span className="flex items-center gap-1.5 rounded-lg border border-[var(--border-soft)] bg-[var(--bg-surface)] px-2 py-1 text-xs text-[var(--text-secondary)]">
                          <History size={12} className="text-[var(--accent)]" />
                          {item.messageCount}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Insights Section */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="rounded-2xl border border-[var(--border-soft)] bg-[var(--accent-soft)] p-6 text-[var(--text-primary)] shadow-sm">
                <h4 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[var(--accent)]">
                  Total Conversations
                </h4>
                <p className="text-2xl font-bold">
                  {historyMetrics.totalConversations}
                </p>
                <div className="mt-4 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                  <BarChart3 size={14} />
                  <span>Live from query history</span>
                </div>
              </div>

              <div className="swiss-card p-6">
                <h4 className="text-[var(--text-muted)] text-sm font-semibold uppercase tracking-wider mb-2">
                  Total Messages Tracked
                </h4>
                <p className="text-2xl font-bold text-[var(--text-primary)]">
                  {historyMetrics.totalMessages}
                </p>
                <p className="mt-4 text-xs text-[var(--text-secondary)]">
                  Aggregated from conversation history.
                </p>
              </div>

              <div className="swiss-card p-6">
                <h4 className="text-[var(--text-muted)] text-sm font-semibold uppercase tracking-wider mb-2">
                  Avg Messages / Conversation
                </h4>
                <p className="text-2xl font-bold text-[var(--text-primary)]">
                  {historyMetrics.avgMessagesPerConversation}
                </p>
                <div className="mt-4 h-1.5 w-full bg-[var(--bg-subtle)] rounded-full overflow-hidden">
                  <div className="h-full bg-green-500 w-full rounded-full" />
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;

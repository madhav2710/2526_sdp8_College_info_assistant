import React, { useState, useMemo } from 'react';
import { adminAPI } from './services/api';
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
  Trash2
} from 'lucide-react';

const INITIAL_HISTORY = [];

const StatusBadge = ({ status, ragStatus }) => {
  const styles = {
    Ingested: 'bg-green-100 text-green-700 border-green-200',
    Completed: 'bg-green-100 text-green-700 border-green-200',
    'RAG Ready': 'bg-emerald-100 text-emerald-700 border-emerald-200',
    Pending: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    'Pending Approval': 'bg-yellow-100 text-yellow-700 border-yellow-200',
    Processing: 'bg-blue-100 text-blue-700 border-blue-200 animate-pulse',
    'RAG Processing': 'bg-blue-100 text-blue-700 border-blue-200 animate-pulse',
    Ingesting: 'bg-blue-100 text-blue-700 border-blue-200 animate-pulse',
    Failed: 'bg-red-100 text-red-700 border-red-200',
    Approved: 'bg-indigo-100 text-indigo-700 border-indigo-200',
    Uploaded: 'bg-slate-100 text-slate-700 border-slate-200',
    Rejected: 'bg-gray-100 text-gray-700 border-gray-200'
  };

  const icons = {
    Ingested: <CheckCircle size={14} className="mr-1" />,
    Completed: <CheckCircle size={14} className="mr-1" />,
    'RAG Ready': <CheckCircle size={14} className="mr-1" />,
    Pending: <Clock size={14} className="mr-1" />,
    'Pending Approval': <Clock size={14} className="mr-1" />,
    Processing: <RefreshCw size={14} className="mr-1 animate-spin" />,
    'RAG Processing': <RefreshCw size={14} className="mr-1 animate-spin" />,
    Ingesting: <RefreshCw size={14} className="mr-1 animate-spin" />,
    Failed: <AlertCircle size={14} className="mr-1" />,
    Approved: <CheckCircle size={14} className="mr-1" />,
    Uploaded: <Upload size={14} className="mr-1" />,
    Rejected: <AlertCircle size={14} className="mr-1" />
  };

  // Determine display status based on document status and RAG readiness
  let displayStatus = status;
  if (status === 'Completed' && ragStatus?.is_rag_ready) {
    displayStatus = 'RAG Ready';
  } else if (status === 'Processing' && ragStatus?.processing_progress) {
    displayStatus = 'RAG Processing';
  } else if (status === 'Pending Approval' || status === 'Pending_approval' || status === 'pending_approval') {
    displayStatus = 'Pending Approval';
  }

  return (
    <span className={`flex items-center w-fit px-2.5 py-0.5 rounded-full text-xs font-medium border ${styles[displayStatus] || styles[status] || styles.Pending}`}>
      {icons[displayStatus] || icons[status] || icons.Pending}
      {displayStatus.replace(/_/g, ' ')}
    </span>
  );
};

const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('admin_token'));
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [documents, setDocuments] = useState([]);
  const [history, setHistory] = useState(INITIAL_HISTORY);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [notification, setNotification] = useState(null);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    try {
      const data = await adminAPI.login(loginEmail, loginPassword);
      if (data.role === 'college_admin') {
        localStorage.setItem('admin_token', data.access_token);
        localStorage.setItem('admin_college_id', data.college_id);
        setIsAuthenticated(true);
      } else {
        setLoginError('Access denied. You must be a college admin.');
      }
    } catch (error) {
      setLoginError(error.message || 'Could not connect to server.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_college_id');
    setIsAuthenticated(false);
  };

  const formatStatusLabel = (value) => {
    if (!value) return 'Unknown';
    const words = value.replace(/_/g, ' ').split(' ');
    return words.map((word) => (word ? word[0].toUpperCase() + word.slice(1) : '')).join(' ');
  };

  const isAwaitingApproval = (rawStatus) => {
    return ['pending_approval', 'pending', 'uploaded'].includes(rawStatus);
  };

  // Fetch documents from API
  const fetchDocuments = async () => {
    if (!isAuthenticated) return;
    try {
      const data = await adminAPI.getDocuments();
      // The API returns { documents: [...], statistics: {...}, ... }
      const documentsList = data.documents || data;
      setDocuments(documentsList.map(doc => ({
        id: doc.id,
        name: doc.filename,
        type: doc.file_type && doc.file_type.includes('pdf') ? 'PDF' : (doc.file_type || 'Document').toUpperCase(),
        size: doc.file_size ? `${(doc.file_size / 1024 / 1024).toFixed(2)} MB` : 'Unknown',
        status: formatStatusLabel(doc.status),
        rawStatus: doc.status,
        date: doc.created_at ? doc.created_at.split('T')[0] : 'N/A',
        ragStatus: doc.rag_status || {
          is_rag_ready: false,
          chunk_count: 0,
          processing_progress: null,
          can_be_queried: false
        },
        processingProgress: doc.rag_status?.processing_progress
      })));
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const formatHistoryTimestamp = (dateValue) => {
    if (!dateValue) return 'N/A';
    try {
      return new Date(dateValue).toLocaleString();
    } catch {
      return dateValue;
    }
  };

  const fetchHistory = async (limit = 10) => {
    if (!isAuthenticated) return;
    setHistoryLoading(true);
    try {
      const data = await adminAPI.getQueryHistory(limit);
      const items = data.query_history || [];
      const mapped = items.map((item) => ({
        id: item.id,
        query: item.query,
        user: item.title || 'Conversation',
        timestamp: formatHistoryTimestamp(item.created_at),
        sources: item.sources || []
      }));
      setHistory(mapped);
    } catch (error) {
      console.error('Error fetching query history:', error);
      showNotification('Failed to load query history.', 'error');
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleDeleteHistory = async (id) => {
    if (!window.confirm('Are you sure you want to delete this interaction?')) return;
    try {
      await adminAPI.deleteQueryHistory(id);
      showNotification('Interaction deleted successfully.');
      fetchHistory(activeTab === 'history' ? 50 : 10);
    } catch (error) {
      console.error('Error deleting interaction:', error);
      showNotification('Failed to delete interaction.', 'error');
    }
  };

  React.useEffect(() => {
    if (isAuthenticated) {
      fetchDocuments();
      fetchHistory(activeTab === 'history' ? 50 : 10);
      // Poll for updates every 10 seconds to see status changes
      const interval = setInterval(fetchDocuments, 10000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, activeTab]);

  // Stats calculation with RAG processing metrics
  const stats = useMemo(
    () => ({
      total: documents.length,
      ingested: documents.filter((d) => d.rawStatus === 'completed' || d.rawStatus === 'ingested').length,
      ragReady: documents.filter((d) => d.ragStatus?.is_rag_ready).length,
      pending: documents.filter((d) => d.rawStatus === 'processing' || isAwaitingApproval(d.rawStatus)).length,
      failed: documents.filter((d) => d.rawStatus === 'failed').length,
      processing: documents.filter((d) => d.rawStatus === 'processing').length
    }),
    [documents]
  );

  const showNotification = (msg, type = 'success') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3000);
  };

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
        console.error('Error uploading file:', error);
      }
    }

    setIsUploading(false);
    if (successCount > 0) {
      showNotification(`Successfully uploaded ${successCount} document(s). Awaiting super admin approval.`);
      fetchDocuments();
    } else {
      showNotification('Failed to upload documents.', 'error');
    }
  };

  const triggerRagProcessing = async (id) => {
    try {
      setDocuments((prev) => prev.map((doc) => (doc.id === id ? { ...doc, status: 'Processing', rawStatus: 'processing' } : doc)));
      
      await adminAPI.triggerRagProcessing(id);
      showNotification('RAG processing started successfully.');
      
      // Refresh documents to get updated status
      setTimeout(() => {
        fetchDocuments();
      }, 1000);
      
    } catch (error) {
      console.error('Error triggering RAG processing:', error);
      showNotification('Failed to start RAG processing.', 'error');
      
      // Revert status change on error
      fetchDocuments();
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 font-sans">
        <div className="w-full max-w-md bg-white p-8 rounded-2xl border border-slate-200 shadow-xl">
          <div className="flex items-center gap-3 mb-8 justify-center">
            <div className="bg-indigo-600 p-2 rounded-lg">
              <Database className="text-white" size={24} />
            </div>
            <span className="font-bold text-2xl tracking-tight text-slate-800">EduQuery Admin</span>
          </div>
          
          <h2 className="text-xl font-bold text-center text-slate-800 mb-2">Welcome Back</h2>
          <p className="text-center text-slate-500 text-sm mb-8">Sign in to manage your college knowledge base.</p>

          {loginError && (
            <div className="mb-6 p-4 bg-red-50 border border-red-100 text-red-700 text-sm rounded-xl flex items-center gap-2">
              <AlertCircle size={16} />
              {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">Email Address</label>
              <input
                type="email"
                required
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
                placeholder="admin@college.edu"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">Password</label>
              <input
                type="password"
                required
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all"
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
              />
            </div>
            <button
              type="submit"
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-lg shadow-indigo-100"
            >
              Sign In
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col fixed h-full">
        <div className="p-6 flex items-center gap-3 border-b border-slate-100">
          <div className="bg-indigo-600 p-2 rounded-lg">
            <Database className="text-white" size={24} />
          </div>
          <span className="font-bold text-xl tracking-tight text-slate-800">EduQuery Admin</span>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === 'dashboard' ? 'bg-indigo-50 text-indigo-700 font-semibold' : 'text-slate-500 hover:bg-slate-50'
            }`}
          >
            <BarChart3 size={20} />
            Dashboard
          </button>
          <button
            onClick={() => setActiveTab('documents')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === 'documents' ? 'bg-indigo-50 text-indigo-700 font-semibold' : 'text-slate-500 hover:bg-slate-50'
            }`}
          >
            <FileText size={20} />
            Documents
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === 'history' ? 'bg-indigo-50 text-indigo-700 font-semibold' : 'text-slate-500 hover:bg-slate-50'
            }`}
          >
            <History size={20} />
            Query History
          </button>
        </nav>

        <div className="p-4 border-t border-slate-100">
          <div className="bg-slate-900 rounded-2xl p-4 text-white">
            <div className="flex items-center gap-2 mb-2">
              <ShieldCheck size={16} className="text-indigo-400" />
              <span className="text-xs font-medium uppercase tracking-wider opacity-70">College Account</span>
            </div>
            <p className="text-sm font-semibold truncate">Admin Panel</p>
            <button 
              onClick={handleLogout}
              className="mt-3 w-full py-2 bg-white/10 hover:bg-white/20 rounded-lg text-xs transition-colors"
            >
              Sign Out
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-64 p-8">
        {/* Header */}
        <header className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              {activeTab === 'dashboard' && 'Admin Overview'}
              {activeTab === 'documents' && 'Document Management'}
              {activeTab === 'history' && 'Student Query History'}
            </h1>
            <p className="text-slate-500 text-sm mt-1">
              {activeTab === 'dashboard' && 'Real-time status of your knowledge base.'}
              {activeTab === 'documents' && 'Upload and ingest files into ChromaDB.'}
              {activeTab === 'history' && 'Monitor how students are interacting with AI.'}
            </p>
          </div>

          <div className="flex gap-3">
            <button className="p-2 bg-white border border-slate-200 rounded-lg text-slate-500 hover:bg-slate-50 relative">
              <Info size={20} />
            </button>
            <div className="h-10 w-10 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 border-2 border-white shadow-sm flex items-center justify-center text-white font-bold">
              AD
            </div>
          </div>
        </header>

        {/* Notification Toast */}
        {notification && (
          <div
            className={`fixed bottom-8 right-8 z-50 px-6 py-4 rounded-xl shadow-2xl flex items-center gap-3 animate-bounce border ${
              notification.type === 'success'
                ? 'bg-white border-green-200 text-green-800'
                : 'bg-white border-red-200 text-red-800'
            }`}
          >
            {notification.type === 'success' ? (
              <CheckCircle className="text-green-500" />
            ) : (
              <AlertCircle className="text-red-500" />
            )}
            <span className="font-medium">{notification.msg}</span>
          </div>
        )}

        {/* Dashboard Tab Content */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              {[
                { label: 'Total Docs', value: stats.total, color: 'bg-indigo-600', icon: FileText },
                { label: 'RAG Ready', value: stats.ragReady, color: 'bg-emerald-600', icon: CheckCircle },
                { label: 'Ingested', value: stats.ingested, color: 'bg-green-600', icon: CheckCircle },
                { label: 'Processing', value: stats.processing, color: 'bg-blue-600', icon: RefreshCw },
                { label: 'Failed', value: stats.failed, color: 'bg-red-600', icon: AlertCircle }
              ].map((item, i) => (
                <div
                  key={i}
                  className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-500">{item.label}</p>
                    <h3 className="text-3xl font-bold text-slate-900 mt-1">{item.value}</h3>
                  </div>
                  <div className={`${item.color} p-3 rounded-xl text-white`}>
                    <item.icon size={24} />
                  </div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="font-bold text-lg">Quick Ingest</h3>
                  <button
                    onClick={() => setActiveTab('documents')}
                    className="text-indigo-600 text-sm font-semibold hover:underline"
                  >
                    View All
                  </button>
                </div>

                <div className="space-y-4">
                  {documents
                    .filter((d) => isAwaitingApproval(d.rawStatus) || d.rawStatus === 'processing' || d.rawStatus === 'approved' || d.rawStatus === 'failed')
                    .slice(0, 3)
                    .map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-100"
                      >
                        <div className="flex items-center gap-3">
                          <div className="bg-white p-2 rounded-lg border border-slate-200">
                            <FileText size={18} className="text-slate-400" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold truncate max-w-[150px]">{doc.name}</p>
                            <p className="text-xs text-slate-500">{doc.size}</p>
                            {doc.rawStatus === 'processing' && doc.processingProgress && (
                              <p className="text-xs text-blue-600 mt-1">
                                RAG Processing...
                              </p>
                            )}
                          </div>
                        </div>

                        {isAwaitingApproval(doc.rawStatus) ? (
                          <div className="flex items-center gap-2 text-amber-600">
                            <Clock size={14} />
                            <span className="text-xs font-medium">Awaiting Approval</span>
                          </div>
                        ) : doc.rawStatus === 'approved' || doc.rawStatus === 'failed' ? (
                          <button
                            onClick={() => triggerRagProcessing(doc.id)}
                            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5"
                          >
                            <RefreshCw size={12} />
                            Start RAG
                          </button>
                        ) : doc.rawStatus === 'processing' ? (
                          <div className="flex items-center gap-2 text-blue-600">
                            <RefreshCw size={14} className="animate-spin" />
                            <span className="text-xs font-medium">Processing</span>
                          </div>
                        ) : null}
                      </div>
                    ))}

                  {documents.filter((d) => isAwaitingApproval(d.rawStatus) || d.rawStatus === 'processing' || d.rawStatus === 'approved' || d.rawStatus === 'failed').length === 0 && (
                    <div className="text-center py-8">
                      <p className="text-slate-400 text-sm italic">No documents pending processing.</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="font-bold text-lg">Recent Queries</h3>
                  <button
                    onClick={() => setActiveTab('history')}
                    className="text-indigo-600 text-sm font-semibold hover:underline"
                  >
                    Full Logs
                  </button>
                </div>

                <div className="space-y-4">
                  {historyLoading && (
                    <div className="text-sm text-slate-500">Loading recent queries...</div>
                  )}
                  {!historyLoading && history.length === 0 && (
                    <div className="text-sm text-slate-400 italic">No recent queries yet.</div>
                  )}
                  {!historyLoading && history.slice(0, 3).map((item) => (
                    <div key={item.id} className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                      <p className="text-sm text-slate-800 line-clamp-1 italic">&quot;{item.query}&quot;</p>
                      <div className="flex items-center justify-between mt-3">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                          <History size={10} /> {item.timestamp}
                        </span>
                        <span className="text-xs font-semibold text-indigo-600">{item.user}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Documents Tab Content */}
        {activeTab === 'documents' && (
          <div className="space-y-6">
            {/* Upload Area */}
            <div className="bg-white border-2 border-dashed border-indigo-200 rounded-2xl p-10 transition-all hover:border-indigo-400 group relative">
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
                      ? 'bg-indigo-100 text-indigo-600 animate-pulse'
                      : 'bg-indigo-50 text-indigo-500 group-hover:bg-indigo-100'
                  }`}
                >
                  <Upload size={32} />
                </div>
                <h3 className="text-lg font-bold text-slate-800">
                  {isUploading ? 'Uploading files...' : 'Upload College Documents'}
                </h3>
                <p className="text-slate-500 mt-1 max-w-sm">
                  Drag and drop your syllabus, placement PDFs, or notices here. Supports PDF, DOCX, and TXT.
                </p>
              </div>
            </div>

            {/* Document List */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-6 border-b border-slate-100 flex flex-col sm:flex-row justify-between gap-4">
                <div className="relative flex-1 max-w-md">
                  <Search
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    size={18}
                  />
                  <input
                    type="text"
                    placeholder="Search documents..."
                    className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 text-sm"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                <div className="flex gap-2">
                  <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-50">
                    <Filter size={16} />
                    Filters
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider font-semibold">
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
                  <tbody className="divide-y divide-slate-100">
                    {documents
                      .filter((d) => d.name.toLowerCase().includes(searchTerm.toLowerCase()))
                      .map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-50/50 transition-colors group">
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <div className="p-2 bg-indigo-50 text-indigo-500 rounded-lg group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                                <FileText size={18} />
                              </div>
                              <span className="text-sm font-semibold text-slate-700">{doc.name}</span>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded-md">
                              {doc.type}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-xs text-slate-500">{doc.size}</td>
                          <td className="px-6 py-4">
                            <StatusBadge status={doc.status} ragStatus={doc.ragStatus} />
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-col gap-1">
                              {doc.ragStatus?.is_rag_ready ? (
                                <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
                                  <CheckCircle size={12} />
                                  Ready ({doc.ragStatus.chunk_count} chunks)
                                </span>
                              ) : doc.rawStatus === 'processing' ? (
                                <span className="text-xs text-blue-600 font-medium flex items-center gap-1">
                                  <RefreshCw size={12} className="animate-spin" />
                                  Processing...
                                </span>
                              ) : doc.rawStatus === 'completed' ? (
                                <span className="text-xs text-yellow-600 font-medium flex items-center gap-1">
                                  <Clock size={12} />
                                  Indexing pending
                                </span>
                              ) : (
                                <span className="text-xs text-slate-400">
                                  Not processed
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-xs text-slate-500">{doc.date}</td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex justify-end gap-2">
                              {isAwaitingApproval(doc.rawStatus) && (
                                <div className="p-2 text-amber-600" title="Awaiting super admin approval">
                                  <Clock size={16} />
                                </div>
                              )}
                              {(doc.rawStatus === 'approved' || doc.rawStatus === 'failed') && (
                                <button
                                  onClick={() => triggerRagProcessing(doc.id)}
                                  className="p-2 text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                                  title="Start RAG Processing"
                                >
                                  <RefreshCw size={16} />
                                </button>
                              )}
                              {doc.ragStatus?.is_rag_ready && (
                                <div className="p-2 text-emerald-600" title="Ready for queries">
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
        {activeTab === 'history' && (
          <div className="space-y-6">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
              <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                <h3 className="font-bold text-lg">Knowledge Base Interactions</h3>
                <div className="flex gap-2">
                  <button className="text-xs font-bold text-indigo-600 hover:underline">Export CSV</button>
                </div>
              </div>

              <div className="divide-y divide-slate-100">
                {historyLoading && (
                  <div className="p-6 text-sm text-slate-500">Loading query history...</div>
                )}
                {!historyLoading && history.length === 0 && (
                  <div className="p-6 text-sm text-slate-400 italic">No query history available.</div>
                )}
                {!historyLoading && history.map((item) => (
                  <div key={item.id} className="p-6 hover:bg-slate-50/50 transition-colors">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className="bg-indigo-100 text-indigo-700 text-[10px] font-bold px-2 py-0.5 rounded uppercase">
                          User ID: {item.user}
                        </span>
                        <span className="text-slate-400 text-xs">{item.timestamp}</span>
                      </div>
                      <div className="flex gap-2">
                        <button 
                          onClick={() => handleDeleteHistory(item.id)}
                          className="text-slate-400 hover:text-red-600 transition-colors"
                          title="Delete interaction"
                        >
                          <Trash2 size={18} />
                        </button>
                        <button className="text-slate-400 hover:text-indigo-600">
                          <ChevronRight size={20} />
                        </button>
                      </div>
                    </div>

                    <p className="text-slate-900 font-medium mb-4">&quot;{item.query}&quot;</p>

                    <div className="flex flex-wrap gap-2 items-center">
                      <span className="text-[10px] text-slate-400 uppercase font-bold tracking-tight">
                        Verified Sources:
                      </span>
                      {item.sources.length === 0 ? (
                        <span className="text-xs text-slate-400">No sources recorded</span>
                      ) : (
                        item.sources.map((source, i) => (
                          <span
                            key={i}
                            className="flex items-center gap-1.5 px-2 py-1 bg-white border border-slate-200 rounded-lg text-xs text-slate-600"
                          >
                            <FileText size={12} className="text-indigo-400" />
                            {source}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Insights Section */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-indigo-600 p-6 rounded-2xl text-white shadow-lg shadow-indigo-200">
                <h4 className="text-indigo-100 text-sm font-semibold uppercase tracking-wider mb-2">
                  Popular Topic
                </h4>
                <p className="text-2xl font-bold">Placements 2024</p>
                <div className="mt-4 flex items-center gap-2 text-indigo-200 text-xs">
                  <BarChart3 size={14} />
                  <span>34% of all queries</span>
                </div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <h4 className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">
                  Unanswered Queries
                </h4>
                <p className="text-2xl font-bold text-slate-800">12</p>
                <button className="mt-4 text-xs font-bold text-indigo-600 flex items-center gap-1 hover:gap-2 transition-all">
                  Review gaps in knowledge <ChevronRight size={14} />
                </button>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <h4 className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">
                  Avg. Response Time
                </h4>
                <p className="text-2xl font-bold text-slate-800">1.2s</p>
                <div className="mt-4 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-green-500 w-[85%] rounded-full" />
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



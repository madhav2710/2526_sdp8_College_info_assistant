import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from './context/AuthContext';
import PendingDocuments from './components/PendingDocuments';
import { superadminAPI } from './services/api';
import { 
  ShieldCheck, 
  Globe, 
  LogOut, 
  FileText, 
  AlertTriangle,
  Check,
  X,
  Clock,
  Settings,
  Users,
  School,
  Activity,
  Plus,
  Search,
  Edit2,
  Trash2,
  ToggleLeft,
  ToggleRight,
  MoreVertical,
  BarChart3,
  MessageSquare,
  Mail,
  Lock
} from 'lucide-react';

const App = () => {
  const { user, login, logout, loading } = useAuth();
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [notification, setNotification] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');

  // Data states
  const [admins, setAdmins] = useState([]);
  const [colleges, setColleges] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState({
    colleges: 0,
    totalAdmins: 0,
    totalDocs: 0,
    totalQueries: 0,
    activeNodes: 12
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [dataLoading, setDataLoading] = useState(false);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCollegeModalOpen, setIsCollegeModalOpen] = useState(false);
  const [editingAdmin, setEditingAdmin] = useState(null);
  const [editingCollege, setEditingCollege] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    college_id: '',
    password: ''
  });
  const [collegeFormData, setCollegeFormData] = useState({
    name: '',
    domain: ''
  });

  const showNotification = (msg, type = 'success') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3000);
  };

  // Fetch data functions
  const fetchStats = async () => {
    try {
      const data = await superadminAPI.getStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const fetchAdmins = async () => {
    try {
      setDataLoading(true);
      const response = await superadminAPI.getAdmins(searchTerm);
      setAdmins(response.admins || []);
    } catch (error) {
      showNotification(`Failed to load admins: ${error.message}`, 'error');
    } finally {
      setDataLoading(false);
    }
  };

  const fetchColleges = async () => {
    try {
      setDataLoading(true);
      const response = await superadminAPI.getColleges(searchTerm);
      setColleges(response.colleges || []);
    } catch (error) {
      showNotification(`Failed to load colleges: ${error.message}`, 'error');
    } finally {
      setDataLoading(false);
    }
  };

  const fetchDocuments = async () => {
    try {
      setDataLoading(true);
      const response = await superadminAPI.getDocuments(searchTerm);
      setDocuments(response.groups || []);
    } catch (error) {
      showNotification(`Failed to load documents: ${error.message}`, 'error');
    } finally {
      setDataLoading(false);
    }
  };

  // Load data when authenticated and tab changes
  useEffect(() => {
    if (user) {
      fetchStats();
      if (activeTab === 'admins') {
        fetchAdmins();
        fetchColleges(); // Need colleges for dropdown
      } else if (activeTab === 'colleges') {
        fetchColleges();
      } else if (activeTab === 'documents') {
        fetchDocuments();
      } else if (activeTab === 'dashboard') {
        fetchStats();
      }
    }
  }, [user, activeTab]);

  // Debounced search
  useEffect(() => {
    if (!user) return;
    const timeoutId = setTimeout(() => {
      if (activeTab === 'admins') {
        fetchAdmins();
      } else if (activeTab === 'colleges') {
        fetchColleges();
      } else if (activeTab === 'documents') {
        fetchDocuments();
      }
    }, 300);
    return () => clearTimeout(timeoutId);
  }, [searchTerm, activeTab, user]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    
    try {
      await login(loginEmail, loginPassword);
      showNotification('Login successful. Welcome!');
    } catch (error) {
      setLoginError(error.message);
      showNotification(error.message, 'error');
    }
  };

  const handleLogout = () => {
    logout();
    setLoginEmail('');
    setLoginPassword('');
    setAdmins([]);
    setColleges([]);
    setDocuments([]);
    showNotification('You have been logged out successfully.');
  };

  // Admin CRUD operations
  const handleOpenAdminModal = (admin = null) => {
    if (admin) {
      setEditingAdmin(admin);
      const college = colleges.find(c => c.name === admin.college);
      setFormData({ 
        name: admin.name, 
        email: admin.email, 
        college_id: college?.id || admin.college_id || '',
        password: ''
      });
    } else {
      setEditingAdmin(null);
      setFormData({ 
        name: '', 
        email: '', 
        college_id: colleges[0]?.id || '',
        password: ''
      });
    }
    setIsModalOpen(true);
  };

  const handleSubmitAdmin = async (e) => {
    e.preventDefault();
    setDataLoading(true);
    try {
      if (editingAdmin) {
        await superadminAPI.updateAdmin(editingAdmin.id, {
          name: formData.name,
          email: formData.email,
          college_id: formData.college_id
        });
        showNotification("Admin updated successfully.");
      } else {
        if (!formData.password) {
          showNotification("Password is required for new admins.", "error");
          setDataLoading(false);
          return;
        }
        await superadminAPI.createAdmin({
          name: formData.name,
          email: formData.email,
          college_id: formData.college_id,
          password: formData.password
        });
        showNotification("New admin created successfully.");
      }
      setIsModalOpen(false);
      await fetchAdmins();
    } catch (error) {
      showNotification(`Failed to save admin: ${error.message}`, "error");
    } finally {
      setDataLoading(false);
    }
  };

  const deleteAdmin = async (id) => {
    if (!window.confirm('Are you sure you want to delete this admin?')) {
      return;
    }
    try {
      await superadminAPI.deleteAdmin(id);
      await fetchAdmins();
      showNotification("Admin account deleted.", "error");
    } catch (error) {
      showNotification(`Failed to delete admin: ${error.message}`, "error");
    }
  };

  const toggleAdminStatus = async (id) => {
    try {
      const admin = admins.find(a => a.id === id);
      const newStatus = admin.status === 'active' ? 'disabled' : 'active';
      await superadminAPI.toggleAdminStatus(id, newStatus);
      await fetchAdmins();
      showNotification("Admin status updated.");
    } catch (error) {
      showNotification(`Failed to update status: ${error.message}`, "error");
    }
  };

  // College CRUD operations
  const handleOpenCollegeModal = (college = null) => {
    if (college) {
      setEditingCollege(college);
      setCollegeFormData({ name: college.name, domain: college.domain || '' });
    } else {
      setEditingCollege(null);
      setCollegeFormData({ name: '', domain: '' });
    }
    setIsCollegeModalOpen(true);
  };

  const handleSubmitCollege = async (e) => {
    e.preventDefault();
    setDataLoading(true);
    try {
      if (editingCollege) {
        await superadminAPI.updateCollege(editingCollege.id, collegeFormData);
        showNotification("College updated successfully.");
      } else {
        await superadminAPI.createCollege(collegeFormData);
        showNotification("New college created successfully.");
      }
      setIsCollegeModalOpen(false);
      await fetchColleges();
      if (activeTab === 'admins') {
        await fetchAdmins(); // Refresh admins to update college dropdown
      }
    } catch (error) {
      showNotification(`Failed to save college: ${error.message}`, "error");
    } finally {
      setDataLoading(false);
    }
  };

  const deleteCollege = async (id) => {
    if (!window.confirm('Are you sure you want to delete this college? This will also delete all associated admins.')) {
      return;
    }
    try {
      await superadminAPI.deleteCollege(id);
      await fetchColleges();
      showNotification("College deleted successfully.", "error");
    } catch (error) {
      showNotification(`Failed to delete college: ${error.message}`, "error");
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-slate-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 font-sans">
        <div className="w-full max-w-md bg-white p-8 rounded-2xl border border-slate-200 shadow-xl">
          <div className="flex items-center gap-3 mb-8 justify-center">
            <div className="bg-blue-600 p-2 rounded-lg">
              <Globe className="text-white" size={24} />
            </div>
            <span className="font-bold text-2xl tracking-tight text-slate-800">SuperHub</span>
          </div>
          
          <h2 className="text-xl font-bold text-center text-slate-800 mb-2">Welcome Back</h2>
          <p className="text-center text-slate-500 text-sm mb-8">Sign in to access the Super Admin Panel.</p>

          {loginError && (
            <div className="mb-6 p-4 bg-red-50 border border-red-100 text-red-700 text-sm rounded-xl flex items-center gap-2">
              <AlertTriangle size={16} />
              {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5 flex items-center gap-2">
                <Mail size={14} />
                Email Address
              </label>
              <input
                type="email"
                required
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
                placeholder="superadmin@example.com"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5 flex items-center gap-2">
                <Lock size={14} />
                Password
              </label>
              <input
                type="password"
                required
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
              />
            </div>
            <button
              type="submit"
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-all shadow-lg shadow-blue-100 flex items-center justify-center gap-2"
            >
              <ShieldCheck size={20} />
              Sign In to Super Admin
            </button>
          </form>
        </div>

        {notification && (
          <div className={`fixed top-8 right-8 z-50 px-6 py-4 rounded-xl shadow-2xl flex items-center gap-3 animate-bounce border ${
            notification.type === 'success'
              ? 'bg-white border-green-200 text-green-800'
              : 'bg-white border-red-200 text-red-800'
          }`}>
            {notification.type === 'success' ? (
              <Check className="text-green-500" size={20} />
            ) : (
              <AlertTriangle className="text-red-500" size={20} />
            )}
            <span className="font-medium">{notification.msg}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex font-sans text-gray-900">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-white flex flex-col fixed h-full shadow-2xl">
        <div className="p-6 flex items-center gap-3 border-b border-slate-800">
          <div className="bg-blue-500 p-2 rounded-lg shadow-lg shadow-blue-500/20">
            <Globe className="text-white" size={24} />
          </div>
          <span className="font-bold text-xl tracking-tight">SuperHub</span>
        </div>
        
        <nav className="flex-1 p-4 space-y-1">
          <NavItem 
            active={activeTab === 'dashboard'} 
            onClick={() => setActiveTab('dashboard')} 
            icon={<Activity size={20} />} 
            label="Global Overview" 
          />
          <NavItem 
            active={activeTab === 'admins'} 
            onClick={() => setActiveTab('admins')} 
            icon={<Users size={20} />} 
            label="Admin Management" 
          />
          <NavItem 
            active={activeTab === 'colleges'} 
            onClick={() => setActiveTab('colleges')} 
            icon={<School size={20} />} 
            label="Colleges" 
          />
          <NavItem 
            active={activeTab === 'pending'} 
            onClick={() => setActiveTab('pending')} 
            icon={<FileText size={20} />} 
            label="Pending Documents" 
          />
          <div className="pt-4 pb-2 px-4 text-[10px] font-bold uppercase tracking-widest text-slate-500">System</div>
          <NavItem 
            active={activeTab === 'documents'} 
            onClick={() => setActiveTab('documents')} 
            icon={<Settings size={20} />} 
            label="Document Log" 
          />
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-64 p-8">
        <header className="flex justify-between items-center mb-10">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
              {activeTab === 'dashboard' && 'Network Health'}
              {activeTab === 'admins' && 'Admin Directory'}
              {activeTab === 'colleges' && 'College Registry'}
              {activeTab === 'pending' && 'Pending Documents'}
              {activeTab === 'documents' && 'Document Log'}
            </h1>
            <p className="text-slate-500 mt-1">
              Global control panel for EduQuery multi-tenant infrastructure.
            </p>
          </div>

          <div className="flex items-center gap-4">
            <button 
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl transition-all text-sm font-bold"
            >
              <LogOut size={18} />
              <span className="hidden sm:inline">Logout</span>
            </button>
            <div className="text-right hidden sm:block">
              <p className="text-sm font-bold text-slate-900">Root Admin</p>
              <p className="text-xs text-slate-500">{user?.userId || 'N/A'}</p>
            </div>
            <div className="h-12 w-12 rounded-2xl bg-slate-900 flex items-center justify-center text-white font-bold border-4 border-white shadow-xl">
              SA
            </div>
          </div>
        </header>

        {notification && (
          <div className={`fixed top-8 right-8 z-[100] px-6 py-3 rounded-xl shadow-2xl flex items-center gap-3 border animate-in fade-in slide-in-from-top-4 duration-300 ${
            notification.type === 'success' 
              ? 'bg-white border-green-100 text-green-800' 
              : 'bg-white border-red-100 text-red-800'
          }`}>
            <div className={`p-1 rounded-full ${
              notification.type === 'success' 
                ? 'bg-green-100 text-green-600' 
                : 'bg-red-100 text-red-600'
            }`}>
              {notification.type === 'success' ? <Check size={16} /> : <X size={16} />}
            </div>
            <span className="font-semibold text-sm">{notification.msg}</span>
          </div>
        )}

        {/* Dashboard Content */}
        {activeTab === 'dashboard' && (
          <div className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <StatCard label="Colleges" value={stats.colleges} icon={<School />} color="blue" />
              <StatCard label="Global Admins" value={stats.totalAdmins} icon={<Users />} color="purple" />
              <StatCard label="Total Documents" value={stats.totalDocs.toLocaleString()} icon={<FileText />} color="indigo" />
              <StatCard label="Queries Served" value={stats.totalQueries.toLocaleString()} icon={<MessageSquare />} color="orange" />
            </div>
          </div>
        )}

        {/* Admins Management Content */}
        {activeTab === 'admins' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div className="relative w-full max-w-md">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                <input 
                  type="text" 
                  placeholder="Search by name, email or college..." 
                  className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-2xl shadow-sm focus:outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all text-sm"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <button 
                onClick={() => handleOpenAdminModal()}
                className="w-full sm:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 font-bold transition-all"
              >
                <Plus size={20} />
                Create New Admin
              </button>
            </div>

            <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
              <table className="w-full text-left">
                <thead className="bg-slate-50/50 border-b border-slate-100">
                  <tr>
                    <th className="px-8 py-5 text-xs font-bold uppercase tracking-wider text-slate-500">Admin Info</th>
                    <th className="px-8 py-5 text-xs font-bold uppercase tracking-wider text-slate-500">College Association</th>
                    <th className="px-8 py-5 text-xs font-bold uppercase tracking-wider text-slate-500">Status</th>
                    <th className="px-8 py-5 text-xs font-bold uppercase tracking-wider text-slate-500">Date Joined</th>
                    <th className="px-8 py-5 text-xs font-bold uppercase tracking-wider text-slate-500 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {dataLoading ? (
                    <tr>
                      <td colSpan="5" className="px-8 py-12 text-center text-slate-500">
                        Loading admins...
                      </td>
                    </tr>
                  ) : admins.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="px-8 py-20 text-center">
                        <div className="bg-slate-50 h-16 w-16 rounded-3xl mx-auto flex items-center justify-center text-slate-300 mb-4">
                          <Users size={32} />
                        </div>
                        <h3 className="text-slate-800 font-bold">No administrators found</h3>
                        <p className="text-slate-500 text-sm mt-1">Try adjusting your search or create a new account.</p>
                      </td>
                    </tr>
                  ) : (
                    admins.map((admin) => (
                      <tr key={admin.id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="px-8 py-6">
                          <div className="flex items-center gap-4">
                            <div className="h-10 w-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 font-bold border-2 border-white shadow-sm">
                              {admin.name.charAt(0)}
                            </div>
                            <div>
                              <p className="text-sm font-bold text-slate-900">{admin.name}</p>
                              <p className="text-xs text-slate-500">{admin.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-8 py-6">
                          <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 text-blue-700 text-xs font-bold rounded-lg border border-blue-100 w-fit">
                            <School size={14} />
                            {admin.college}
                          </div>
                        </td>
                        <td className="px-8 py-6">
                          <button 
                            onClick={() => toggleAdminStatus(admin.id)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold transition-all border ${
                              admin.status === 'active' 
                                ? 'bg-green-50 text-green-700 border-green-200' 
                                : 'bg-red-50 text-red-700 border-red-200'
                            }`}
                          >
                            {admin.status === 'active' ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                            {admin.status === 'active' ? 'Enabled' : 'Disabled'}
                          </button>
                        </td>
                        <td className="px-8 py-6 text-xs text-slate-500 font-medium">
                          {admin.joined}
                        </td>
                        <td className="px-8 py-6 text-right">
                          <div className="flex justify-end gap-2">
                            <button 
                              onClick={() => handleOpenAdminModal(admin)}
                              className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all"
                            >
                              <Edit2 size={18} />
                            </button>
                            <button 
                              onClick={() => deleteAdmin(admin.id)}
                              className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all"
                            >
                              <Trash2 size={18} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Colleges Management Content */}
        {activeTab === 'colleges' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div className="relative w-full max-w-md">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                <input 
                  type="text" 
                  placeholder="Search colleges..." 
                  className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-2xl shadow-sm focus:outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all text-sm"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <button 
                onClick={() => handleOpenCollegeModal()}
                className="w-full sm:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 font-bold transition-all"
              >
                <Plus size={20} />
                Add New College
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {dataLoading ? (
                <div className="col-span-3 text-center py-12 text-slate-500">Loading colleges...</div>
              ) : colleges.length === 0 ? (
                <div className="col-span-3 py-20 text-center">
                  <div className="bg-slate-50 h-16 w-16 rounded-3xl mx-auto flex items-center justify-center text-slate-300 mb-4">
                    <School size={32} />
                  </div>
                  <h3 className="text-slate-800 font-bold">No colleges found</h3>
                  <p className="text-slate-500 text-sm mt-1">Try adjusting your search or add a new college.</p>
                </div>
              ) : (
                colleges.map((college) => (
                  <div key={college.id} className="bg-white rounded-3xl border border-slate-200 shadow-sm p-8 hover:border-slate-300 transition-all group">
                    <div className="flex items-start justify-between mb-6">
                      <div className="p-4 bg-blue-50 rounded-2xl border border-blue-100 group-hover:scale-110 transition-transform duration-300">
                        <School className="text-blue-600" size={24} />
                      </div>
                      <button 
                        onClick={() => deleteCollege(college.id)}
                        className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                    <div className="space-y-4">
                      <div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">{college.name}</h3>
                        <div className="flex items-center gap-4 text-sm">
                          <div className="flex items-center gap-2">
                            <Users size={16} className="text-slate-400" />
                            <span className="text-slate-500 font-medium">{college.admin_count || 0} Admin{(college.admin_count || 0) !== 1 ? 's' : ''}</span>
                          </div>
                        </div>
                      </div>
                      <div className="pt-4 border-t border-slate-100 flex gap-2">
                        <button 
                          onClick={() => handleOpenCollegeModal(college)}
                          className="flex-1 px-4 py-2 bg-slate-50 hover:bg-slate-100 text-slate-600 text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-2"
                        >
                          <Edit2 size={14} />
                          Edit
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Pending Documents */}
        {activeTab === 'pending' && (
          <PendingDocuments 
            onApprove={() => {
              showNotification('Document approved successfully!');
              fetchStats();
            }}
            onReject={() => {
              showNotification('Document rejected.');
              fetchStats();
            }}
          />
        )}

        {/* Document Log */}
        {activeTab === 'documents' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div className="relative w-full max-w-md">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                <input 
                  type="text" 
                  placeholder="Search by college, admin, or document..." 
                  className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-2xl shadow-sm focus:outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all text-sm"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-6">
              {dataLoading ? (
                <div className="text-center py-12 text-slate-500">Loading documents...</div>
              ) : documents.length === 0 ? (
                <div className="py-20 text-center">
                  <div className="bg-slate-50 h-16 w-16 rounded-3xl mx-auto flex items-center justify-center text-slate-300 mb-4">
                    <FileText size={32} />
                  </div>
                  <h3 className="text-slate-800 font-bold">No documents found</h3>
                  <p className="text-slate-500 text-sm mt-1">Try adjusting your search or upload new documents.</p>
                </div>
              ) : (
                documents.map((group, idx) => (
                  <div key={idx} className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
                    <div className="px-8 py-6 bg-slate-50 border-b border-slate-100">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-blue-50 rounded-xl border border-blue-100">
                            <School className="text-blue-600" size={24} />
                          </div>
                          <div>
                            <h3 className="text-lg font-bold text-slate-900">{group.college}</h3>
                            <div className="flex items-center gap-2 mt-1">
                              <Users size={14} className="text-slate-400" />
                              <span className="text-sm text-slate-600 font-medium">{group.admin_name}</span>
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Documents</span>
                          <p className="text-2xl font-extrabold text-slate-900 mt-1">{group.total_documents || group.documents.length}</p>
                        </div>
                      </div>
                    </div>
                    <div className="p-6">
                      <div className="space-y-3">
                        {group.documents.map((doc) => (
                          <div key={doc.id} className="flex items-center gap-4 p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-slate-200 hover:bg-slate-100/50 transition-all group">
                            <div className="p-3 bg-blue-50 rounded-lg border border-blue-100 group-hover:scale-110 transition-transform duration-300">
                              <FileText className="text-blue-600" size={20} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-bold text-slate-900 truncate">{doc.name}</h4>
                              <div className="flex items-center gap-4 mt-1 text-xs text-slate-500">
                                <span className="flex items-center gap-1">
                                  <Activity size={12} />
                                  {doc.uploaded_at}
                                </span>
                                <span className="px-2 py-0.5 bg-slate-200 rounded text-slate-600 font-medium text-[10px] uppercase">
                                  {doc.type}
                                </span>
                                <span className="text-slate-400">{doc.size}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Admin Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={() => setIsModalOpen(false)}></div>
            <div className="relative bg-white w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden border border-white/20">
              <div className="px-8 py-6 bg-slate-50 border-b border-slate-100 flex justify-between items-center">
                <h3 className="text-xl font-bold text-slate-900">
                  {editingAdmin ? 'Edit College Admin' : 'Create New Admin Account'}
                </h3>
                <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-900 transition-colors">
                  <X size={24} />
                </button>
              </div>
              <form onSubmit={handleSubmitAdmin} className="p-8 space-y-6">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Full Name</label>
                  <input 
                    required
                    type="text" 
                    placeholder="e.g. Rachel Zane"
                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Email Address</label>
                  <input 
                    required
                    type="email" 
                    placeholder="name@college.edu"
                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Assign College</label>
                  <select 
                    required
                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none appearance-none"
                    value={formData.college_id}
                    onChange={(e) => setFormData({...formData, college_id: e.target.value})}
                  >
                    <option value="">Select a college</option>
                    {colleges.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                {!editingAdmin && (
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Password</label>
                    <input 
                      required
                      type="password" 
                      placeholder="Enter password for new admin"
                      className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none"
                      value={formData.password}
                      onChange={(e) => setFormData({...formData, password: e.target.value})}
                    />
                  </div>
                )}
                <div className="pt-4 flex gap-3">
                  <button 
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="flex-1 py-4 bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold rounded-2xl transition-all"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    disabled={dataLoading}
                    className="flex-[2] py-4 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-2xl shadow-lg shadow-blue-600/20 transition-all disabled:opacity-50"
                  >
                    {dataLoading ? 'Saving...' : (editingAdmin ? 'Save Changes' : 'Create Account')}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* College Modal */}
        {isCollegeModalOpen && (
          <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={() => setIsCollegeModalOpen(false)}></div>
            <div className="relative bg-white w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden border border-white/20">
              <div className="px-8 py-6 bg-slate-50 border-b border-slate-100 flex justify-between items-center">
                <h3 className="text-xl font-bold text-slate-900">
                  {editingCollege ? 'Edit College' : 'Create New College'}
                </h3>
                <button onClick={() => setIsCollegeModalOpen(false)} className="text-slate-400 hover:text-slate-900 transition-colors">
                  <X size={24} />
                </button>
              </div>
              <form onSubmit={handleSubmitCollege} className="p-8 space-y-6">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">College Name</label>
                  <input 
                    required
                    type="text" 
                    placeholder="e.g. St. Xavier's Institute"
                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none"
                    value={collegeFormData.name}
                    onChange={(e) => setCollegeFormData({...collegeFormData, name: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Domain (Optional)</label>
                  <input 
                    type="text" 
                    placeholder="e.g. stxaviers.edu"
                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none"
                    value={collegeFormData.domain}
                    onChange={(e) => setCollegeFormData({...collegeFormData, domain: e.target.value})}
                  />
                </div>
                <div className="pt-4 flex gap-3">
                  <button 
                    type="button"
                    onClick={() => setIsCollegeModalOpen(false)}
                    className="flex-1 py-4 bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold rounded-2xl transition-all"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    disabled={dataLoading}
                    className="flex-[2] py-4 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-2xl shadow-lg shadow-blue-600/20 transition-all disabled:opacity-50"
                  >
                    {dataLoading ? 'Saving...' : (editingCollege ? 'Save Changes' : 'Create College')}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

const NavItem = ({ active, icon, label, onClick }) => (
  <button 
    onClick={onClick}
    className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
      active 
        ? 'bg-blue-600 text-white font-bold shadow-lg shadow-blue-600/20' 
        : 'text-slate-400 hover:bg-slate-800 hover:text-white'
    }`}
  >
    {icon}
    <span className="text-sm">{label}</span>
  </button>
);

const StatCard = ({ label, value, icon, color }) => {
  const colorMap = {
    blue: 'bg-blue-500 shadow-blue-500/20',
    purple: 'bg-purple-500 shadow-purple-500/20',
    indigo: 'bg-indigo-500 shadow-indigo-500/20',
    orange: 'bg-orange-500 shadow-orange-500/20',
  };

  return (
    <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm flex flex-col justify-between hover:border-slate-300 transition-all group">
      <div className="flex justify-between items-start mb-6">
        <p className="text-sm font-bold text-slate-400 uppercase tracking-widest">{label}</p>
        <div className={`p-3 rounded-2xl text-white ${colorMap[color]} group-hover:scale-110 transition-transform duration-300`}>
          {icon}
        </div>
      </div>
      <h3 className="text-4xl font-extrabold text-slate-900 tracking-tight">{value}</h3>
    </div>
  );
};

export default App;

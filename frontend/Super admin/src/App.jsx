import React, { useState } from 'react';
import { useAuth } from './context/AuthContext';
import PendingDocuments from './components/PendingDocuments';
import { 
  ShieldCheck, 
  Globe, 
  LogOut, 
  FileText, 
  AlertTriangle,
  Check,
  X,
  Clock,
  Settings
} from 'lucide-react';

const App = () => {
  const { user, login, logout, loading } = useAuth();
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [notification, setNotification] = useState(null);
  const [activeTab, setActiveTab] = useState('pending');

  const showNotification = (msg, type = 'success') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 3000);
  };

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
    showNotification('You have been logged out successfully.');
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
            active={activeTab === 'pending'} 
            onClick={() => setActiveTab('pending')} 
            icon={<FileText size={20} />} 
            label="Pending Documents" 
          />
          <NavItem 
            active={activeTab === 'scheduled'} 
            onClick={() => setActiveTab('scheduled')} 
            icon={<Clock size={20} />} 
            label="Scheduled Processing" 
          />
          <div className="pt-4 pb-2 px-4 text-[10px] font-bold uppercase tracking-widest text-slate-500">System</div>
          <NavItem 
            active={activeTab === 'settings'} 
            onClick={() => setActiveTab('settings')} 
            icon={<Settings size={20} />} 
            label="Settings" 
          />
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-64 p-8">
        <header className="flex justify-between items-center mb-10">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
              {activeTab === 'pending' && 'Pending Documents'}
              {activeTab === 'scheduled' && 'Scheduled Processing'}
              {activeTab === 'settings' && 'Settings'}
            </h1>
            <p className="text-slate-500 mt-1">
              Super Admin Control Panel
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
              <p className="text-sm font-bold text-slate-900">Super Admin</p>
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

        {/* Content */}
        {activeTab === 'pending' && (
          <PendingDocuments 
            onApprove={() => showNotification('Document approved successfully!')}
            onReject={() => showNotification('Document rejected.')}
          />
        )}
        
        {activeTab === 'scheduled' && (
          <div className="bg-white rounded-xl border border-slate-200 p-8">
            <p className="text-slate-600">Scheduled documents view coming soon...</p>
          </div>
        )}
        
        {activeTab === 'settings' && (
          <div className="bg-white rounded-xl border border-slate-200 p-8">
            <p className="text-slate-600">Settings view coming soon...</p>
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

export default App;

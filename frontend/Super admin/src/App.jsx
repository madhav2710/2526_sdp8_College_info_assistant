//SUPER ADMIN PANEL:

import React, { useState, useMemo } from 'react';

import { 

  Users, 

  School, 

  ShieldCheck, 

  Activity, 

  Plus, 

  Search, 

  Edit2, 

  Trash2, 

  ToggleLeft, 

  ToggleRight, 

  MoreVertical,

  BarChart3,

  FileText,

  MessageSquare,

  Globe,

  Settings,

  X,

  Check,

  AlertTriangle,

  LogOut,

  Mail,

  Lock

} from 'lucide-react';



// Mock Data for Super Admin

const INITIAL_COLLEGES = [

  'St. Xavier\'s Institute',

  'MIT Pune',

  'IIT Delhi',

  'Stanford University',

  'Oxford University'

];



const INITIAL_ADMINS = [

  { id: '1', name: 'John Doe', email: 'john.doe@stxaviers.edu', college: 'St. Xavier\'s Institute', status: 'active', role: 'College Admin', joined: '2023-05-12' },

  { id: '2', name: 'Sarah Connor', email: 's.connor@mitpune.ac.in', college: 'MIT Pune', status: 'active', role: 'College Admin', joined: '2023-08-20' },

  { id: '3', name: 'Mike Ross', email: 'mike.ross@iitd.ac.in', college: 'IIT Delhi', status: 'disabled', role: 'College Admin', joined: '2023-01-15' },

  { id: '4', name: 'Harvey Specter', email: 'h.specter@stanford.edu', college: 'Stanford University', status: 'active', role: 'College Admin', joined: '2023-11-30' },

];



// Mock Document Data

const INITIAL_DOCUMENTS = [

  { id: '1', name: 'Admission Guidelines 2024.pdf', adminId: '1', adminName: 'John Doe', college: 'St. Xavier\'s Institute', uploadedAt: '2024-01-15 10:30 AM', size: '2.5 MB', type: 'PDF' },

  { id: '2', name: 'Course Curriculum - Computer Science.docx', adminId: '1', adminName: 'John Doe', college: 'St. Xavier\'s Institute', uploadedAt: '2024-01-14 03:45 PM', size: '1.8 MB', type: 'DOCX' },

  { id: '3', name: 'Faculty Handbook 2024.pdf', adminId: '2', adminName: 'Sarah Connor', college: 'MIT Pune', uploadedAt: '2024-01-13 09:15 AM', size: '3.2 MB', type: 'PDF' },

  { id: '4', name: 'Research Publications List.xlsx', adminId: '2', adminName: 'Sarah Connor', college: 'MIT Pune', uploadedAt: '2024-01-12 02:20 PM', size: '856 KB', type: 'XLSX' },

  { id: '5', name: 'Infrastructure Report.pdf', adminId: '3', adminName: 'Mike Ross', college: 'IIT Delhi', uploadedAt: '2024-01-11 11:00 AM', size: '4.1 MB', type: 'PDF' },

  { id: '6', name: 'Student Enrollment Data.xlsx', adminId: '3', adminName: 'Mike Ross', college: 'IIT Delhi', uploadedAt: '2024-01-10 04:30 PM', size: '2.3 MB', type: 'XLSX' },

  { id: '7', name: 'Academic Calendar 2024.pdf', adminId: '4', adminName: 'Harvey Specter', college: 'Stanford University', uploadedAt: '2024-01-09 08:45 AM', size: '1.2 MB', type: 'PDF' },

  { id: '8', name: 'Department Policies.docx', adminId: '4', adminName: 'Harvey Specter', college: 'Stanford University', uploadedAt: '2024-01-08 01:15 PM', size: '980 KB', type: 'DOCX' },

  { id: '9', name: 'Scholarship Information.pdf', adminId: '1', adminName: 'John Doe', college: 'St. Xavier\'s Institute', uploadedAt: '2024-01-07 10:00 AM', size: '1.5 MB', type: 'PDF' },

  { id: '10', name: 'Examination Schedule.xlsx', adminId: '2', adminName: 'Sarah Connor', college: 'MIT Pune', uploadedAt: '2024-01-06 03:30 PM', size: '720 KB', type: 'XLSX' },

];



const App = () => {

  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('super_admin_token'));

  const [loginEmail, setLoginEmail] = useState('');

  const [loginPassword, setLoginPassword] = useState('');

  const [loginError, setLoginError] = useState('');

  const [activeTab, setActiveTab] = useState('dashboard');

  const [admins, setAdmins] = useState(INITIAL_ADMINS);

  const [searchTerm, setSearchTerm] = useState('');

  const [isModalOpen, setIsModalOpen] = useState(false);

  const [editingAdmin, setEditingAdmin] = useState(null);

  const [notification, setNotification] = useState(null);



  // Form State

  const [formData, setFormData] = useState({

    name: '',

    email: '',

    college: INITIAL_COLLEGES[0]

  });



  const stats = useMemo(() => ({

    colleges: INITIAL_COLLEGES.length,

    totalAdmins: admins.length,

    totalDocs: 0,

    totalQueries: 0,

    activeNodes: 12

  }), [admins]);



  const showNotification = (msg, type = 'success') => {

    setNotification({ msg, type });

    setTimeout(() => setNotification(null), 3000);

  };



  // Super Admin Credentials (In production, this would be handled by a backend)

  const SUPER_ADMIN_CREDENTIALS = {

    email: 'admin@platform.com',

    password: 'adminpassword123'

  };



  const handleLogin = (e) => {

    e.preventDefault();

    setLoginError('');



    if (loginEmail === SUPER_ADMIN_CREDENTIALS.email && loginPassword === SUPER_ADMIN_CREDENTIALS.password) {

      localStorage.setItem('super_admin_token', 'authenticated');

      setIsAuthenticated(true);

      showNotification("Login successful. Welcome back!");

    } else {

      setLoginError('Invalid credentials. Please try again.');

      showNotification("Invalid credentials. Please try again.", "error");

    }

  };



  const handleLogout = () => {

    localStorage.removeItem('super_admin_token');

    setIsAuthenticated(false);

    setLoginEmail('');

    setLoginPassword('');

    showNotification("You have been logged out successfully.");

  };



  const toggleAdminStatus = (id) => {

    setAdmins(admins.map(admin => 

      admin.id === id ? { ...admin, status: admin.status === 'active' ? 'disabled' : 'active' } : admin

    ));

    showNotification("Admin status updated.");

  };



  const deleteAdmin = (id) => {

    setAdmins(admins.filter(admin => admin.id !== id));

    showNotification("Admin account deleted.", "error");

  };



  const handleOpenModal = (admin = null) => {

    if (admin) {

      setEditingAdmin(admin);

      setFormData({ name: admin.name, email: admin.email, college: admin.college });

    } else {

      setEditingAdmin(null);

      setFormData({ name: '', email: '', college: INITIAL_COLLEGES[0] });

    }

    setIsModalOpen(true);

  };



  const handleSubmit = (e) => {

    e.preventDefault();

    if (editingAdmin) {

      setAdmins(admins.map(a => a.id === editingAdmin.id ? { ...a, ...formData } : a));

      showNotification("Admin updated successfully.");

    } else {

      const newAdmin = {

        ...formData,

        id: Math.random().toString(36).substr(2, 9),

        status: 'active',

        role: 'College Admin',

        joined: new Date().toISOString().split('T')[0]

      };

      setAdmins([newAdmin, ...admins]);

      showNotification("New admin created successfully.");

    }

    setIsModalOpen(false);

  };



  // Show Login Page if not authenticated

  if (!isAuthenticated) {

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

                placeholder="sysadmin@eduquery.com"

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



          <div className="mt-6 text-center pt-4 border-t border-slate-100">

            <p className="text-xs text-slate-500">


            </p>

          </div>

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

          <NavItem active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} icon={<Activity size={20} />} label="Global Overview" />

          <NavItem active={activeTab === 'admins'} onClick={() => setActiveTab('admins')} icon={<Users size={20} />} label="Admin Management" />

          <NavItem active={activeTab === 'colleges'} onClick={() => setActiveTab('colleges')} icon={<School size={20} />} label="Colleges" />

          <div className="pt-4 pb-2 px-4 text-[10px] font-bold uppercase tracking-widest text-slate-500">System</div>

          <NavItem active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} icon={<Settings size={20} />} label="Document Log" />

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

              {activeTab === 'settings' && 'Document Log'}

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

              <p className="text-xs text-slate-500">sysadmin@eduquery.com</p>

            </div>

            <div className="h-12 w-12 rounded-2xl bg-slate-900 flex items-center justify-center text-white font-bold border-4 border-white shadow-xl">

              SA

            </div>

          </div>

        </header>



        {notification && (

          <div className={`fixed top-8 right-8 z-[100] px-6 py-3 rounded-xl shadow-2xl flex items-center gap-3 border animate-in fade-in slide-in-from-top-4 duration-300 ${notification.type === 'success' ? 'bg-white border-green-100 text-green-800' : 'bg-white border-red-100 text-red-800'}`}>

            <div className={`p-1 rounded-full ${notification.type === 'success' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}`}>

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



            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

              <div className="lg:col-span-2 bg-white p-8 rounded-3xl border border-slate-200 shadow-sm">

                <div className="flex justify-between items-center mb-8">

                  <h3 className="text-xl font-bold">Query Volume (Last 24h)</h3>

                  <div className="flex gap-2">

                    <span className="px-3 py-1 bg-green-50 text-green-700 text-xs font-bold rounded-full border border-green-100 flex items-center gap-1">

                      <Activity size={12} /> Normal Traffic

                    </span>

                  </div>

                </div>

                {/* Mock Chart Area */}

                <div className="h-64 w-full bg-slate-50 rounded-2xl border border-slate-100 flex items-end justify-between p-6 gap-2">

                  {[40, 60, 45, 90, 65, 80, 55, 70, 85, 45, 50, 95].map((h, i) => (

                    <div key={i} className="flex-1 bg-blue-500/20 hover:bg-blue-500 rounded-t-lg transition-all cursor-help relative group" style={{ height: `${h}%` }}>

                      <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-slate-900 text-white text-[10px] px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">

                        {h * 120} Qs

                      </div>

                    </div>

                  ))}

                </div>

                <div className="flex justify-between mt-4 text-[10px] font-bold text-slate-400 uppercase tracking-widest px-2">

                  <span>12:00 AM</span>

                  <span>12:00 PM</span>

                  <span>Now</span>

                </div>

              </div>



              <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm flex flex-col">

                <h3 className="text-xl font-bold mb-6">Recent Activity</h3>

                <div className="space-y-6 flex-1">

                  {[

                    { type: 'admin', user: 'Harvey Specter', action: 'Uploaded 45 docs', time: '2m ago' },

                    { type: 'system', user: 'Root Admin', action: 'Enabled MIT Pune node', time: '14m ago' },

                    { type: 'alert', user: 'Oxford Uni', action: 'API limit warning', time: '1h ago' },

                    { type: 'admin', user: 'John Doe', action: 'Modified system prompt', time: '3h ago' },

                  ].map((act, i) => (

                    <div key={i} className="flex gap-4">

                      <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${

                        act.type === 'admin' ? 'bg-blue-50 text-blue-600' : 

                        act.type === 'system' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'

                      }`}>

                        {act.type === 'admin' ? <Users size={18} /> : act.type === 'system' ? <Check size={18} /> : <AlertTriangle size={18} />}

                      </div>

                      <div>

                        <p className="text-sm font-bold text-slate-800">{act.user}</p>

                        <p className="text-xs text-slate-500">{act.action}</p>

                        <span className="text-[10px] text-slate-400 mt-1 block font-medium">{act.time}</span>

                      </div>

                    </div>

                  ))}

                </div>

                <button className="mt-6 w-full py-3 bg-slate-50 hover:bg-slate-100 text-slate-600 text-xs font-bold rounded-xl transition-all">

                  View Audit Logs

                </button>

              </div>

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

                onClick={() => handleOpenModal()}

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

                  {admins.filter(a => 

                    a.name.toLowerCase().includes(searchTerm.toLowerCase()) || 

                    a.college.toLowerCase().includes(searchTerm.toLowerCase()) ||

                    a.email.toLowerCase().includes(searchTerm.toLowerCase())

                  ).map((admin) => (

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

                            onClick={() => handleOpenModal(admin)}

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

                          <button className="p-2 text-slate-400 hover:text-slate-900 rounded-xl transition-all">

                            <MoreVertical size={18} />

                          </button>

                        </div>

                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

              {admins.length === 0 && (

                <div className="py-20 text-center">

                  <div className="bg-slate-50 h-16 w-16 rounded-3xl mx-auto flex items-center justify-center text-slate-300 mb-4">

                    <Users size={32} />

                  </div>

                  <h3 className="text-slate-800 font-bold">No administrators found</h3>

                  <p className="text-slate-500 text-sm mt-1">Try adjusting your search or create a new account.</p>

                </div>

              )}

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

                className="w-full sm:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 font-bold transition-all"

              >

                <Plus size={20} />

                Add New College

              </button>

            </div>



            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

              {INITIAL_COLLEGES.filter(college => 

                college.toLowerCase().includes(searchTerm.toLowerCase())

              ).map((college, index) => {

                // Count admins for this college

                const adminCount = admins.filter(admin => admin.college === college).length;

                return (

                  <div key={index} className="bg-white rounded-3xl border border-slate-200 shadow-sm p-8 hover:border-slate-300 transition-all group">

                    <div className="flex items-start justify-between mb-6">

                      <div className="p-4 bg-blue-50 rounded-2xl border border-blue-100 group-hover:scale-110 transition-transform duration-300">

                        <School className="text-blue-600" size={24} />

                      </div>

                      <button className="p-2 text-slate-400 hover:text-slate-900 rounded-xl transition-all">

                        <MoreVertical size={18} />

                      </button>

                    </div>



                    <div className="space-y-4">

                      <div>

                        <h3 className="text-xl font-bold text-slate-900 mb-2">{college}</h3>

                        <div className="flex items-center gap-4 text-sm">

                          <div className="flex items-center gap-2">

                            <Users size={16} className="text-slate-400" />

                            <span className="text-slate-500 font-medium">{adminCount} Admin{adminCount !== 1 ? 's' : ''}</span>

                          </div>

                        </div>

                      </div>



                      <div className="pt-4 border-t border-slate-100 flex gap-2">

                        <button className="flex-1 px-4 py-2 bg-slate-50 hover:bg-slate-100 text-slate-600 text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-2">

                          <Edit2 size={14} />

                          Edit

                        </button>

                        <button className="flex-1 px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-2">

                          <Activity size={14} />

                          View Details

                        </button>

                      </div>

                    </div>

                  </div>

                );

              })}

            </div>



            {INITIAL_COLLEGES.filter(college => 

              college.toLowerCase().includes(searchTerm.toLowerCase())

            ).length === 0 && (

              <div className="py-20 text-center">

                <div className="bg-slate-50 h-16 w-16 rounded-3xl mx-auto flex items-center justify-center text-slate-300 mb-4">

                  <School size={32} />

                </div>

                <h3 className="text-slate-800 font-bold">No colleges found</h3>

                <p className="text-slate-500 text-sm mt-1">Try adjusting your search or add a new college.</p>

              </div>

            )}

          </div>

        )}



        {/* Document Log Content */}

        {activeTab === 'settings' && (

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

              {/* Group documents by college and admin */}

              {(() => {

                // Group documents by college and admin

                const grouped = INITIAL_DOCUMENTS.reduce((acc, doc) => {

                  const key = `${doc.college}|${doc.adminId}`;

                  if (!acc[key]) {

                    acc[key] = {

                      college: doc.college,

                      adminId: doc.adminId,

                      adminName: doc.adminName,

                      documents: []

                    };

                  }

                  acc[key].documents.push(doc);

                  return acc;

                }, {});



                // Filter based on search term

                const filtered = Object.values(grouped).filter(group => 

                  group.college.toLowerCase().includes(searchTerm.toLowerCase()) || 

                  group.adminName.toLowerCase().includes(searchTerm.toLowerCase()) ||

                  group.documents.some(doc => doc.name.toLowerCase().includes(searchTerm.toLowerCase()))

                );



                // Filter documents within each group if searching

                const processed = filtered.map(group => ({

                  ...group,

                  documents: searchTerm 

                    ? group.documents.filter(doc => 

                        doc.name.toLowerCase().includes(searchTerm.toLowerCase()) ||

                        group.college.toLowerCase().includes(searchTerm.toLowerCase()) ||

                        group.adminName.toLowerCase().includes(searchTerm.toLowerCase())

                      )

                    : group.documents

                }));



                return processed.length > 0 ? processed.map((group, idx) => (

                  <div key={idx} className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">

                    {/* College and Admin Header */}

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

                              <span className="text-sm text-slate-600 font-medium">{group.adminName}</span>

                            </div>

                          </div>

                        </div>

                        <div className="text-right">

                          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Documents</span>

                          <p className="text-2xl font-extrabold text-slate-900 mt-1">{group.documents.length}</p>

                        </div>

                      </div>

                    </div>



                    {/* Documents List */}

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

                                  {doc.uploadedAt}

                                </span>

                                <span className="flex items-center gap-1">

                                  <span className="px-2 py-0.5 bg-slate-200 rounded text-slate-600 font-medium text-[10px] uppercase">

                                    {doc.type}

                                  </span>

                                </span>

                                <span className="text-slate-400">{doc.size}</span>

                              </div>

                            </div>

                            <div className="flex gap-2">

                              <button className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all">

                                <MoreVertical size={18} />

                              </button>

                            </div>

                          </div>

                        ))}

                      </div>

                    </div>

                  </div>

                )) : (

                  <div className="py-20 text-center">

                    <div className="bg-slate-50 h-16 w-16 rounded-3xl mx-auto flex items-center justify-center text-slate-300 mb-4">

                      <FileText size={32} />

                    </div>

                    <h3 className="text-slate-800 font-bold">No documents found</h3>

                    <p className="text-slate-500 text-sm mt-1">Try adjusting your search or upload new documents.</p>

                  </div>

                );

              })()}

            </div>

          </div>

        )}



        {/* Modal for Create/Edit Admin */}

        {isModalOpen && (

          <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6">

            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={() => setIsModalOpen(false)}></div>

            <div className="relative bg-white w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden border border-white/20 animate-in zoom-in-95 duration-200">

              <div className="px-8 py-6 bg-slate-50 border-b border-slate-100 flex justify-between items-center">

                <h3 className="text-xl font-bold text-slate-900">

                  {editingAdmin ? 'Edit College Admin' : 'Create New Admin Account'}

                </h3>

                <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-900 transition-colors">

                  <X size={24} />

                </button>

              </div>

              <form onSubmit={handleSubmit} className="p-8 space-y-6">

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

                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none appearance-none"

                    value={formData.college}

                    onChange={(e) => setFormData({...formData, college: e.target.value})}

                  >

                    {INITIAL_COLLEGES.map(c => <option key={c} value={c}>{c}</option>)}

                  </select>

                </div>

                

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

                    className="flex-[2] py-4 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-2xl shadow-lg shadow-blue-600/20 transition-all"

                  >

                    {editingAdmin ? 'Save Changes' : 'Create Account'}

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



// Sub-components

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
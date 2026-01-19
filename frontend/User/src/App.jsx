import { useState, useEffect } from "react"
import ChatInterface from "./components/ChatInterface"
import SuperAdminPanel from "./components/SuperAdminPanel"
import Login from "./components/Login"
import { AuthProvider, useAuth } from "./context/AuthContext"
import "./index.css"

function AppContent() {
  const [showAdmin, setShowAdmin] = useState(false)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const { user, logout, loading } = useAuth()

  useEffect(() => {
    if (user?.role === 'super_admin') {
      setShowAdmin(true);
    }
  }, [user]);

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center">Loading...</div>
  }

  if (user?.role === 'college_admin') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 gap-6 p-4">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-slate-800 mb-2">College Admin Dashboard</h1>
          <p className="text-slate-600">Your dashboard is hosted on a separate secure portal.</p>
        </div>
        
        <a 
          href="http://localhost:5174" 
          target="_blank" 
          rel="noopener noreferrer"
          className="flex items-center gap-2 bg-indigo-600 text-white px-8 py-4 rounded-xl font-bold text-lg shadow-xl hover:bg-indigo-700 transition-all hover:scale-105"
        >
          Launch Admin Dashboard 
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
        </a>

        <button 
          onClick={logout} 
          className="mt-4 text-slate-500 hover:text-red-600 font-semibold underline decoration-2 underline-offset-4 transition-colors"
        >
          Sign Out
        </button>
      </div>
    )
  }

  if (showAdmin) {
    return (
      <div className="relative">
        <button 
          onClick={() => setShowAdmin(false)}
          className="fixed bottom-4 right-4 z-[300] bg-slate-800 text-white px-4 py-2 rounded-lg shadow-lg font-bold text-xs"
        >
          Exit Admin
        </button>
        <SuperAdminPanel />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="fixed top-4 right-4 flex gap-2">
        {user?.role === 'super_admin' && (
          <button 
            onClick={() => setShowAdmin(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg font-bold text-xs hover:bg-blue-700 transition-colors"
          >
            Go to Super Admin
          </button>
        )}
        {user ? (
          <button 
            onClick={logout}
            className="bg-slate-200 text-slate-700 px-4 py-2 rounded-lg shadow-lg font-bold text-xs hover:bg-slate-300 transition-colors"
          >
            Logout
          </button>
        ) : (
          <button 
            onClick={() => setShowAuthModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg font-bold text-xs hover:bg-blue-700 transition-colors"
          >
            Login / Sign up
          </button>
        )}
      </div>
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 flex items-center justify-between">
           <h1 className="text-3xl font-bold">College Information Chatbot</h1>
           <span className="text-sm text-slate-500">
             {user ? `Logged in as: ${user.role}` : 'Chatting as guest'}
           </span>
        </div>
        <ChatInterface />
      </div>

      {showAuthModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 p-4">
          <div className="relative w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <button
              onClick={() => setShowAuthModal(false)}
              className="absolute right-3 top-3 text-slate-400 hover:text-slate-700"
            >
              ✕
            </button>
            <Login onSuccess={() => setShowAuthModal(false)} />
          </div>
        </div>
      )}
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App

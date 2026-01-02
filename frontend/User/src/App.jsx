import { useState } from "react"
import ChatInterface from "./components/ChatInterface"
import SuperAdminPanel from "./components/SuperAdminPanel"
import Login from "./components/Login"
import { AuthProvider, useAuth } from "./context/AuthContext"
import "./index.css"

function AppContent() {
  const [showAdmin, setShowAdmin] = useState(false)
  const { user, logout, loading } = useAuth()

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center">Loading...</div>
  }

  if (!user) {
    return <Login />
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
        {user.role === 'super_admin' && (
          <button 
            onClick={() => setShowAdmin(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg font-bold text-xs hover:bg-blue-700 transition-colors"
          >
            Go to Super Admin
          </button>
        )}
        <button 
          onClick={logout}
          className="bg-slate-200 text-slate-700 px-4 py-2 rounded-lg shadow-lg font-bold text-xs hover:bg-slate-300 transition-colors"
        >
          Logout
        </button>
      </div>
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 flex items-center justify-between">
           <h1 className="text-3xl font-bold">College Information Chatbot</h1>
           <span className="text-sm text-slate-500">Logged in as: {user.role}</span>
        </div>
        <ChatInterface />
      </div>
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

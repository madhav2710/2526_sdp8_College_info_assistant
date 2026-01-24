import { useState, useEffect } from "react"
import ChatInterface from "./components/ChatInterface"
import ChatHistorySidebar from "./components/ChatHistorySidebar"
import SuperAdminPanel from "./components/SuperAdminPanel"
import Login from "./components/Login"
import ProfileCard from "./components/ProfileCard"
import { AuthProvider, useAuth } from "./context/AuthContext"
import { Sparkles, MessageSquare, GraduationCap, Menu, X } from "lucide-react"
import "./index.css"

function AppContent() {
  const [showAdmin, setShowAdmin] = useState(false)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [currentConversationId, setCurrentConversationId] = useState(null)
  const { user, logout, loading } = useAuth()

  // Auto-open sidebar on desktop when user logs in
  useEffect(() => {
    if (user && window.innerWidth >= 1024) {
      setSidebarOpen(true)
    }
  }, [user])

  useEffect(() => {
    if (user?.role === 'super_admin') {
      setShowAdmin(true);
    }
  }, [user]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-2 border-blue-600 border-t-transparent mx-auto mb-4"></div>
          <p className="text-slate-600 font-medium">Loading...</p>
        </div>
      </div>
    )
  }

  if (user?.role === 'college_admin') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 gap-6 p-4">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl mb-4 shadow-xl">
            <GraduationCap className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-2">
            College Admin Dashboard
          </h1>
          <p className="text-slate-600 text-lg">Your dashboard is hosted on a separate secure portal.</p>
        </div>

        <a
          href="http://localhost:5174"
          target="_blank"
          rel="noopener noreferrer"
          className="group flex items-center gap-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-8 py-4 rounded-2xl font-bold text-lg shadow-2xl hover:shadow-indigo-500/50 transition-all hover:scale-105"
        >
          <span>Launch Admin Dashboard</span>
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:translate-x-1 transition-transform">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
            <polyline points="15 3 21 3 21 9"></polyline>
            <line x1="10" y1="14" x2="21" y2="3"></line>
          </svg>
        </a>

        <button
          onClick={logout}
          className="mt-4 text-slate-600 hover:text-red-600 font-semibold underline decoration-2 underline-offset-4 transition-colors"
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
          className="fixed bottom-4 right-4 z-[300] bg-slate-800 text-white px-4 py-2 rounded-lg shadow-lg font-bold text-xs hover:bg-slate-900 transition-colors"
        >
          Exit Admin
        </button>
        <SuperAdminPanel />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white relative overflow-hidden">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white shadow-sm">
        <div className={`px-4 sm:px-6 lg:px-8 transition-all duration-300 ${
          user && sidebarOpen
            ? sidebarCollapsed 
              ? 'lg:pl-[calc(4rem+1rem)]' 
              : 'lg:pl-[calc(16rem+1rem)]'
            : ''
        }`}>
          <div className="flex items-center justify-between h-16 max-w-7xl mx-auto">
            {/* Logo and Title */}
            <div className="flex items-center gap-3">
              {user && (
                <button
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                  className="p-2 hover:bg-slate-100 rounded-lg transition-colors lg:hidden text-slate-600"
                  aria-label="Toggle sidebar"
                >
                  {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                </button>
              )}
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-xl flex items-center justify-center shadow-md">
                <MessageSquare className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">
                  College Information Chatbot
                </h1>
                {!user && (
                  <p className="text-xs text-slate-500 font-medium">Chatting as guest</p>
                )}
              </div>
            </div>

            {/* Right side actions */}
            <div className="flex items-center gap-3 relative z-[1001]">
              {user?.role === 'super_admin' && (
                <button
                  onClick={() => setShowAdmin(true)}
                  className="hidden sm:flex items-center gap-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white px-4 py-2 rounded-lg shadow-lg font-semibold text-sm hover:shadow-xl transition-all hover:scale-105"
                >
                  <Sparkles className="w-4 h-4" />
                  Super Admin
                </button>
              )}
              {user ? (
                <ProfileCard />
              ) : (
                <button
                  onClick={() => setShowAuthModal(true)}
                  className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-2 rounded-lg shadow-lg font-semibold text-sm hover:shadow-xl transition-all hover:scale-105"
                >
                  Login / Sign up
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Chat History Sidebar */}
      {user && (
        <ChatHistorySidebar
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          onSelectConversation={(conversationId) => {
            setCurrentConversationId(conversationId);
            // Only close sidebar on mobile (screen width < 1024px)
            if (window.innerWidth < 1024) {
              setSidebarOpen(false);
            }
          }}
          currentConversationId={currentConversationId}
          onNewChat={() => {
            setCurrentConversationId(null);
            // Only close sidebar on mobile (screen width < 1024px)
            if (window.innerWidth < 1024) {
              setSidebarOpen(false);
            }
          }}
          onCollapseChange={(collapsed) => setSidebarCollapsed(collapsed)}
        />
      )}

      {/* Main Content - Slides based on sidebar state */}
      <main className={`relative z-0 transition-all duration-300 w-full ${
        user && sidebarOpen
          ? sidebarCollapsed 
            ? 'lg:ml-16' 
            : 'lg:ml-64'
          : ''
      }`}>
        <ChatInterface
          conversationId={currentConversationId}
          onConversationChange={(convId) => setCurrentConversationId(convId)}
        />
      </main>

      {/* Auth Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500"></div>
            <div className="p-6">
              <button
                onClick={() => setShowAuthModal(false)}
                className="absolute right-4 top-4 text-slate-400 hover:text-slate-700 transition-colors w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <Login onSuccess={() => setShowAuthModal(false)} />
            </div>
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

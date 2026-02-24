import { useEffect, useState } from "react";
import { GraduationCap, Menu, MessageSquare, Sparkles, X } from "lucide-react";

import { AuthProvider, useAuth } from "./context/AuthContext";
import ChatHistorySidebar from "./components/ChatHistorySidebar";
import ChatInterface from "./components/ChatInterface";
import Login from "./components/Login";
import ProfileCard from "./components/ProfileCard";
import "./index.css";

function RolePortalCard({ icon, title, description, href, cta, onLogout }) {
  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] px-4 py-10">
      <div className="mx-auto mt-16 max-w-xl surface-primary p-8 text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-[16px] bg-[var(--bg-subtle)] text-[var(--accent)]">
          {icon}
        </div>
        <h1 className="type-h2 text-[var(--text-primary)]">{title}</h1>
        <p className="mt-3 type-body text-[var(--text-secondary)]">
          {description}
        </p>

        <div className="mt-8 flex flex-col items-center gap-3">
          <a
            href={href}
            className="btn-primary inline-flex w-full max-w-sm items-center justify-center px-6"
          >
            {cta}
          </a>
          <button
            onClick={onLogout}
            className="btn-secondary w-full max-w-sm px-6"
          >
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}

function AppContent() {
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const { user, logout, loading } = useAuth();

  useEffect(() => {
    if (user && window.innerWidth >= 1024) {
      setSidebarOpen(true);
    }
  }, [user]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-canvas)]">
        <div className="surface-primary px-8 py-6 text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
          <p className="mt-3 type-small text-[var(--text-secondary)]">
            Loading workspace...
          </p>
        </div>
      </div>
    );
  }

  if (user?.role === "college_admin") {
    return (
      <RolePortalCard
        icon={<GraduationCap className="h-8 w-8" />}
        title="College Admin Workspace"
        description="Your operational dashboard is available in the admin portal."
        href="/admin"
        cta="Open Admin Portal"
        onLogout={logout}
      />
    );
  }

  if (user?.role === "super_admin") {
    return (
      <RolePortalCard
        icon={<Sparkles className="h-8 w-8" />}
        title="Super Admin Workspace"
        description="Governance and approvals are available in the super admin portal."
        href="/super"
        cta="Open Super Admin Portal"
        onLogout={logout}
      />
    );
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <header className="sticky top-0 z-50 border-b border-[var(--border-soft)] bg-[var(--bg-canvas)]/95">
        <div
          className={`mx-auto h-16 max-w-[1280px] px-4 transition-all duration-[220ms] sm:px-6 lg:px-8 ${
            user && sidebarOpen
              ? sidebarCollapsed
                ? "lg:pl-[calc(4rem+1rem)]"
                : "lg:pl-[calc(16rem+1rem)]"
              : ""
          }`}
        >
          <div className="flex h-full items-center justify-between">
            <div className="flex items-center gap-3">
              {user && (
                <button
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                  className="rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-surface)] p-2 text-[var(--text-secondary)] transition-colors duration-[140ms] hover:bg-[var(--bg-subtle)] lg:hidden"
                  aria-label="Toggle sidebar"
                >
                  {sidebarOpen ? (
                    <X className="h-5 w-5" />
                  ) : (
                    <Menu className="h-5 w-5" />
                  )}
                </button>
              )}

              <div className="flex h-10 w-10 items-center justify-center rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-surface)] text-[var(--accent)]">
                <MessageSquare className="h-5 w-5" />
              </div>

              <div>
                <h1 className="font-serif-display text-[22px] leading-[1.2]">
                  College Information Assistant
                </h1>
                {!user && (
                  <p className="type-meta text-[var(--text-muted)]">
                    Guest Session
                  </p>
                )}
              </div>
            </div>

            <div className="relative z-[1001] flex items-center gap-3">
              {user ? (
                <ProfileCard />
              ) : (
                <button
                  onClick={() => setShowAuthModal(true)}
                  className="btn-primary px-5 text-sm"
                >
                  Login / Sign Up
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {user && (
        <ChatHistorySidebar
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          onSelectConversation={(conversationId) => {
            setCurrentConversationId(conversationId);
            if (window.innerWidth < 1024) setSidebarOpen(false);
          }}
          currentConversationId={currentConversationId}
          onNewChat={() => {
            setCurrentConversationId(null);
            if (window.innerWidth < 1024) setSidebarOpen(false);
          }}
          onCollapseChange={(collapsed) => setSidebarCollapsed(collapsed)}
        />
      )}

      <main
        className={`relative z-0 w-full transition-all duration-[220ms] ${
          user && sidebarOpen
            ? sidebarCollapsed
              ? "lg:ml-16"
              : "lg:ml-64"
            : ""
        }`}
      >
        <ChatInterface
          conversationId={currentConversationId}
          onConversationChange={(convId) => setCurrentConversationId(convId)}
        />
      </main>

      {showAuthModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-[#1f1f1c]/45 p-4">
          <div className="relative w-full max-w-md surface-primary overflow-hidden p-6">
            <button
              onClick={() => setShowAuthModal(false)}
              className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-surface)] text-[var(--text-muted)] transition-colors duration-[140ms] hover:bg-[var(--bg-subtle)]"
            >
              <X className="h-4 w-4" />
            </button>
            <Login onSuccess={() => setShowAuthModal(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;

import React, { useEffect, useState } from "react";
import {
  ChevronLeft,
  Clock,
  Loader2,
  MessageSquare,
  Plus,
  Search,
  Trash2,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { userAPI } from "../services/api";

const ChatHistorySidebar = ({
  isOpen,
  onToggle,
  onSelectConversation,
  currentConversationId,
  onNewChat,
  onCollapseChange,
}) => {
  const { user } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    if (onCollapseChange && isOpen) onCollapseChange(isCollapsed);
  }, [isCollapsed, isOpen, onCollapseChange]);

  useEffect(() => {
    if (user?.userId && isOpen) fetchConversations();
  }, [user?.userId, isOpen]);

  const fetchConversations = async () => {
    if (!user?.userId) return;
    setLoading(true);
    try {
      const data = await userAPI.getChatHistory(user.userId);
      setConversations(data || []);
    } catch (error) {
      console.error("Failed to fetch chat history:", error);
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteConversation = async (conversationId, e) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this conversation?")) return;
    setConversations((prev) => prev.filter((conv) => conv.id !== conversationId));
  };

  const formatDate = (dateString) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  const getConversationTitle = (conversation) => conversation.title || "New Conversation";

  const filteredConversations = conversations.filter((conv) => {
    if (!searchQuery) return true;
    return getConversationTitle(conv).toLowerCase().includes(searchQuery.toLowerCase());
  });

  if (!user) return null;

  const sidebarWidth = isCollapsed ? "w-16" : "w-64";

  return (
    <>
      <div
        className={`${sidebarWidth} fixed left-0 top-16 z-40 flex h-[calc(100vh-4rem)] flex-col border-r border-[#514b3f] bg-[#2f2a21] text-[#ebe6db] transition-all duration-[220ms] ${
          isOpen ? "translate-x-0" : "-translate-x-full lg:-translate-x-full"
        }`}
      >
        {isCollapsed ? (
          <div className="flex min-h-[64px] items-center justify-center border-b border-[#514b3f] p-4">
            <button
              onClick={() => {
                const next = !isCollapsed;
                setIsCollapsed(next);
                if (onCollapseChange) onCollapseChange(next);
              }}
              className="rounded-[10px] border border-[#5f584a] bg-[#3a342a] p-2 text-[#d6cfbf] transition-colors duration-[140ms] hover:bg-[#474032]"
              title="Expand chat history"
            >
              <MessageSquare className="h-5 w-5" />
            </button>
          </div>
        ) : (
          <div className="flex min-h-[64px] items-center justify-between border-b border-[#514b3f] px-4 py-3">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-[#d8c5a2]" />
              <span className="type-small text-[#f4efe2]">Chat History</span>
            </div>
            <button
              onClick={() => {
                const next = !isCollapsed;
                setIsCollapsed(next);
                if (onCollapseChange) onCollapseChange(next);
              }}
              className="rounded-[10px] border border-[#5f584a] bg-[#3a342a] p-1.5 text-[#d6cfbf] transition-colors duration-[140ms] hover:bg-[#474032]"
              title="Collapse"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
        )}

        {!isCollapsed && (
          <div className="border-b border-[#514b3f] p-3">
            <button
              onClick={onNewChat}
              className="inline-flex w-full items-center justify-center gap-2 rounded-[12px] border border-[#5f584a] bg-[#3f382d] px-3 py-2.5 text-sm font-semibold text-[#f7f2e5] transition-colors duration-[140ms] hover:bg-[#4b4335]"
            >
              <Plus className="h-4 w-4" />
              New Chat
            </button>
          </div>
        )}

        {!isCollapsed && (
          <div className="border-b border-[#514b3f] p-3">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#aea696]" />
              <input
                type="text"
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-[12px] border border-[#5f584a] bg-[#3a342a] py-2 pl-9 pr-3 text-sm text-[#f4efe2] placeholder:text-[#aea696]"
              />
            </label>
          </div>
        )}

        {!isCollapsed && (
          <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center p-8">
                <Loader2 className="h-5 w-5 animate-spin text-[#aea696]" />
              </div>
            ) : filteredConversations.length === 0 ? (
              <div className="p-4 text-center type-small text-[#aea696]">
                {searchQuery ? "No conversations found" : "No chat history yet"}
              </div>
            ) : (
              <div className="p-2">
                <div className="type-meta px-2 py-2 text-[#978f7f]">Your Chats</div>
                {filteredConversations.map((conversation) => {
                  const isActive = conversation.id === currentConversationId;
                  const title = getConversationTitle(conversation);
                  return (
                    <div
                      key={conversation.id}
                      onClick={() => onSelectConversation(conversation.id)}
                      className={`group relative mb-1 cursor-pointer rounded-[12px] border px-3 py-2.5 transition-colors ${
                        isActive
                          ? "border-[#d8c5a2] bg-[#3f382d]"
                          : "border-transparent hover:border-[#5f584a] hover:bg-[#3a342a]"
                      }`}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-2 h-8 w-[3px] rounded-r-full bg-[var(--accent)]" />
                      )}
                      <div className="flex items-start gap-2 pl-1">
                        <MessageSquare className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#b8af9e]" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-[#f4efe2]">{title}</div>
                          <div className="mt-0.5 flex items-center gap-1 text-xs text-[#aea696]">
                            <Clock className="h-3 w-3" />
                            {formatDate(conversation.created_at)}
                          </div>
                        </div>
                        <button
                          onClick={(e) => handleDeleteConversation(conversation.id, e)}
                          className="rounded-[8px] p-1 text-[#caa2a2] opacity-0 transition-all duration-[140ms] hover:bg-[#55463c] group-hover:opacity-100"
                          title="Delete conversation"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {!isCollapsed && (
          <div className="border-t border-[#514b3f] p-3">
            <div className="flex items-center gap-2 rounded-[12px] border border-[#5f584a] bg-[#3a342a] px-2 py-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#4c4436] text-xs font-semibold text-[#f4efe2]">
                {user?.fullName ? user.fullName.substring(0, 2).toUpperCase() : "U"}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-[#f4efe2]">
                  {user?.fullName || "User"}
                </div>
                <div className="truncate text-xs text-[#aea696]">{user?.email || ""}</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {isOpen && <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={onToggle} />}
    </>
  );
};

export default ChatHistorySidebar;

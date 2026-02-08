import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { userAPI } from '../services/api';
import { 
    MessageSquare, 
    Plus, 
    Search, 
    Trash2, 
    ChevronLeft, 
    ChevronRight,
    Clock,
    Loader2
} from 'lucide-react';

const ChatHistorySidebar = ({ isOpen, onToggle, onSelectConversation, currentConversationId, onNewChat, onCollapseChange }) => {
    const { user } = useAuth();
    const [conversations, setConversations] = useState([]);
    const [loading, setLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [isCollapsed, setIsCollapsed] = useState(false);

    // Notify parent when collapse state changes
    useEffect(() => {
        if (onCollapseChange && isOpen) {
            onCollapseChange(isCollapsed);
        }
    }, [isCollapsed, isOpen, onCollapseChange]);

    useEffect(() => {
        if (user?.userId && isOpen) {
            fetchConversations();
        }
    }, [user?.userId, isOpen]);

    const fetchConversations = async () => {
        if (!user?.userId) return;
        
        setLoading(true);
        try {
            const data = await userAPI.getChatHistory(user.userId);
            setConversations(data || []);
        } catch (error) {
            console.error('Failed to fetch chat history:', error);
            setConversations([]);
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteConversation = async (conversationId, e) => {
        e.stopPropagation();
        if (!window.confirm('Are you sure you want to delete this conversation?')) {
            return;
        }
        
        try {
            await userAPI.deleteConversation(conversationId);
            setConversations(prev => prev.filter(conv => conv.id !== conversationId));
            if (currentConversationId === conversationId && onNewChat) {
                onNewChat();
            }
        } catch (error) {
            console.error('Failed to delete conversation:', error);
        }
    };

    const formatDate = (dateString) => {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diffTime = Math.abs(now - date);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    const getConversationTitle = (conversation) => {
        if (conversation.title) return conversation.title;
        return 'New Conversation';
    };

    const filteredConversations = conversations.filter(conv => {
        if (!searchQuery) return true;
        const title = getConversationTitle(conv).toLowerCase();
        return title.includes(searchQuery.toLowerCase());
    });

    if (!user) return null;

    const sidebarWidth = isCollapsed ? 'w-16' : 'w-64';

    return (
        <>
            {/* Sidebar */}
            <div className={`${sidebarWidth} fixed left-0 top-16 h-[calc(100vh-4rem)] bg-slate-900 text-white transition-all duration-300 z-40 flex flex-col border-r border-slate-800 ${isOpen ? 'translate-x-0' : '-translate-x-full lg:-translate-x-full'}`}>
                {/* Header */}
                {isCollapsed ? (
                    <div className="p-4 border-b border-slate-800 flex items-center justify-center min-h-[64px]">
                        <button
                            onClick={() => {
                                const newCollapsed = !isCollapsed;
                                setIsCollapsed(newCollapsed);
                                if (onCollapseChange) {
                                    onCollapseChange(newCollapsed);
                                }
                            }}
                            className="p-2 hover:bg-slate-800 rounded-lg transition-colors text-slate-300 hover:text-white"
                            title="Expand chat history"
                        >
                            <MessageSquare className="w-5 h-5" />
                        </button>
                    </div>
                ) : (
                    <div className="p-4 border-b border-slate-800 flex items-center justify-between min-h-[64px]">
                        <div className="flex items-center gap-2">
                            <MessageSquare className="w-5 h-5 text-blue-400" />
                            <span className="font-semibold text-sm text-white">Chat History</span>
                        </div>
                        <button
                            onClick={() => {
                                const newCollapsed = !isCollapsed;
                                setIsCollapsed(newCollapsed);
                                if (onCollapseChange) {
                                    onCollapseChange(newCollapsed);
                                }
                            }}
                            className="p-1.5 hover:bg-slate-800 rounded-lg transition-colors text-slate-300 hover:text-white"
                            title="Collapse"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                    </div>
                )}

                {/* New Chat Button */}
                {!isCollapsed && (
                    <div className="p-3 border-b border-slate-800">
                        <button
                            onClick={onNewChat}
                            className="w-full flex items-center gap-2 px-3 py-2.5 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium text-sm text-white transition-colors shadow-sm"
                        >
                            <Plus className="w-4 h-4" />
                            <span>New Chat</span>
                        </button>
                    </div>
                )}

                {/* Search */}
                {!isCollapsed && (
                    <div className="p-3 border-b border-slate-800">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <input
                                type="text"
                                placeholder="Search chats..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full pl-9 pr-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                            />
                        </div>
                    </div>
                )}

                {/* Conversations List - Only show when expanded */}
                {!isCollapsed && (
                    <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0">
                        {loading ? (
                            <div className="flex items-center justify-center p-8">
                                <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
                            </div>
                        ) : filteredConversations.length === 0 ? (
                            <div className="p-4 text-center text-slate-400 text-sm">
                                {searchQuery ? 'No conversations found' : 'No chat history yet'}
                            </div>
                        ) : (
                            <div className="p-2">
                                <div className="px-2 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                    Your chats
                                </div>
                                {filteredConversations.map((conversation) => {
                                    const isActive = conversation.id === currentConversationId;
                                    const title = getConversationTitle(conversation);
                                    
                                    return (
                                        <div
                                            key={conversation.id}
                                            onClick={() => onSelectConversation(conversation.id)}
                                            className={`group relative flex items-center gap-2 px-3 py-2.5 rounded-lg mb-1 cursor-pointer transition-colors ${
                                                isActive 
                                                    ? 'bg-slate-800 text-white' 
                                                    : 'hover:bg-slate-800/50 text-slate-300'
                                            }`}
                                        >
                                            <MessageSquare className="w-4 h-4 flex-shrink-0 text-slate-400" />
                                            <div className="flex-1 min-w-0">
                                                <div className="text-sm font-medium truncate">{title}</div>
                                                <div className="flex items-center gap-1 text-xs text-slate-500 mt-0.5">
                                                    <Clock className="w-3 h-3" />
                                                    <span>{formatDate(conversation.created_at)}</span>
                                                </div>
                                            </div>
                                            <button
                                                onClick={(e) => handleDeleteConversation(conversation.id, e)}
                                                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-700 rounded transition-all"
                                                title="Delete conversation"
                                            >
                                                <Trash2 className="w-3.5 h-3.5 text-red-400" />
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                )}

                {/* User Profile at Bottom */}
                {!isCollapsed && (
                    <div className="p-3 border-t border-slate-800">
                        <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-800/50">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white">
                                {user?.fullName ? user.fullName.substring(0, 2).toUpperCase() : 'U'}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium truncate text-white">{user?.fullName || 'User'}</div>
                                <div className="text-xs text-slate-400 truncate">{user?.email || ''}</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Overlay for mobile */}
            {isOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-30 lg:hidden"
                    onClick={onToggle}
                ></div>
            )}
        </>
    );
};

export default ChatHistorySidebar;

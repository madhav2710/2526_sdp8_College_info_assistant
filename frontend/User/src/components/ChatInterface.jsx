import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { userAPI } from '../services/api';
import {
    ArrowUpIcon,
    User,
    Bot,
    FileText,
    AlertCircle,
    Clock,
    CheckCircle,
    Sparkles,
    Loader2,
    Send
} from "lucide-react";

const ChatInterface = ({ conversationId, onConversationChange }) => {
    const { user } = useAuth();
    const [inputValue, setInputValue] = useState("");
    const [messages, setMessages] = useState([]);
    const [isSending, setIsSending] = useState(false);
    const [isProcessingRAG, setIsProcessingRAG] = useState(false);
    const conversationIdRef = useRef(conversationId || window.crypto.randomUUID());
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);
    const messagesContainerRef = useRef(null);

    // Update conversation ID when prop changes
    useEffect(() => {
        if (conversationId) {
            conversationIdRef.current = conversationId;
            loadConversation(conversationId);
        } else {
            conversationIdRef.current = window.crypto.randomUUID();
            setMessages([]);
        }
    }, [conversationId]);

    const loadConversation = async (convId) => {
        if (!user?.userId || !convId) return;

        try {
            const data = await userAPI.getConversationMessages(convId);
            if (data && data.messages) {
                const formattedMessages = data.messages.map(msg => ({
                    role: msg.role,
                    content: msg.content,
                    timestamp: msg.created_at,
                    sources: msg.metadata?.sources || [],
                    isRAGResponse: msg.metadata?.rag_enabled || false,
                    fallbackUsed: msg.metadata?.fallback_used || false,
                    chunksUsed: msg.metadata?.chunks_used || 0,
                    processingTime: msg.metadata?.processing_time_ms || 0,
                    responseType: msg.metadata?.response_type || 'unknown',
                    metadata: msg.metadata || {}
                }));
                setMessages(formattedMessages);
            } else {
                setMessages([]);
            }
        } catch (error) {
            console.error('Failed to load conversation:', error);
            setMessages([]);
        }
    };

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        const trimmed = inputValue.trim();
        if (!trimmed || isSending) return;

        const userMessage = { role: 'user', content: trimmed, timestamp: new Date() };
        setMessages(prev => [...prev, userMessage]);
        setInputValue("");
        setIsSending(true);
        setIsProcessingRAG(true);

        try {
            const data = await userAPI.sendMessage(
                conversationIdRef.current,
                user?.userId,
                user?.collegeId,
                trimmed
            );

            const assistantMessage = {
                role: 'assistant',
                content: data.content || data.response || "No response received",
                sources: data.sources || [],
                metadata: data.metadata || {},
                isRAGResponse: data.metadata?.rag_enabled || false,
                fallbackUsed: data.metadata?.fallback_used || false,
                chunksUsed: data.metadata?.chunks_used || 0,
                processingTime: data.metadata?.processing_time_ms || 0,
                responseType: data.metadata?.response_type || 'unknown',
                timestamp: new Date()
            };

            setMessages(prev => [...prev, assistantMessage]);

            if (onConversationChange) {
                onConversationChange(conversationIdRef.current);
            }
        } catch (error) {
            console.error("Error sending message:", error);

            let errorMessage = "I'm sorry, I encountered an error while processing your request.";

            if (error.message.includes("AI service")) {
                errorMessage = "The AI service is temporarily unavailable. Please try again in a moment.";
            } else if (error.message.includes("Document search")) {
                errorMessage = "Document search is temporarily unavailable. I can still help with general questions.";
            } else if (error.message.includes("temporarily unavailable")) {
                errorMessage = "The chat service is temporarily unavailable. Please try again shortly.";
            } else if (error.message.includes("rate limit")) {
                errorMessage = "You're sending messages too quickly. Please wait a moment before trying again.";
            }

            setMessages(prev => [...prev, {
                role: 'assistant',
                content: errorMessage,
                isError: true,
                originalError: error.message,
                timestamp: new Date()
            }]);
        } finally {
            setIsSending(false);
            setIsProcessingRAG(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // Source Display Component
    const SourceDisplay = ({ sources, chunksUsed }) => {
        if (!sources || sources.length === 0) return null;

        return (
            <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <div className="flex items-center gap-2 text-xs font-semibold text-blue-700 mb-2">
                    <FileText className="w-3.5 h-3.5" />
                    <span>Sources ({sources.length})</span>
                    {chunksUsed > 0 && (
                        <span className="text-blue-600/70 font-normal">• {chunksUsed} chunks</span>
                    )}
                </div>
                <div className="flex flex-wrap gap-1.5">
                    {sources.map((source, index) => (
                        <span
                            key={index}
                            className="inline-flex items-center px-2.5 py-1 bg-white text-blue-800 text-xs font-medium rounded-md border border-blue-200"
                        >
                            {source}
                        </span>
                    ))}
                </div>
            </div>
        );
    };

    // Response Type Indicator
    const ResponseTypeIndicator = ({ isRAGResponse, fallbackUsed, processingTime }) => {
        if (!isRAGResponse && !fallbackUsed) return null;

        const getIndicatorConfig = () => {
            if (isRAGResponse && !fallbackUsed) {
                return {
                    icon: <CheckCircle className="w-3.5 h-3.5" />,
                    text: "Document-based response",
                    bgColor: "bg-emerald-50",
                    textColor: "text-emerald-700",
                    borderColor: "border-emerald-200",
                    iconColor: "text-emerald-600"
                };
            } else if (fallbackUsed) {
                return {
                    icon: <AlertCircle className="w-3.5 h-3.5" />,
                    text: "Basic response",
                    bgColor: "bg-amber-50",
                    textColor: "text-amber-700",
                    borderColor: "border-amber-200",
                    iconColor: "text-amber-600"
                };
            }
            return null;
        };

        const config = getIndicatorConfig();
        if (!config) return null;

        return (
            <div className={`mt-2 flex items-center gap-2 px-2.5 py-1 rounded-md border ${config.bgColor} ${config.borderColor} ${config.textColor} text-xs font-medium`}>
                <span className={config.iconColor}>{config.icon}</span>
                <span>{config.text}</span>
                {processingTime > 0 && (
                    <>
                        <Clock className="w-3 h-3 ml-1 opacity-70" />
                        <span className="text-xs opacity-75">{processingTime}ms</span>
                    </>
                )}
            </div>
        );
    };

    // Loading Indicator
    const RAGLoadingIndicator = () => {
        if (!isProcessingRAG) return null;

        return (
            <div className="flex items-start gap-3 mb-6">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="flex-1 bg-slate-50 rounded-lg p-3 border border-slate-200">
                    <div className="flex items-center gap-2 mb-2">
                        <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                        <span className="text-sm text-slate-700 font-medium">Searching documents and generating response...</span>
                    </div>
                    <div className="h-1 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full animate-pulse" style={{ width: '60%' }}></div>
                    </div>
                </div>
            </div>
        );
    };

    // Empty State
    const EmptyState = () => (
        <div className="flex flex-col items-center justify-center h-full min-h-[60vh] text-center px-4 py-12">
            <div className="max-w-2xl mx-auto w-full space-y-8">
                <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-500 rounded-2xl flex items-center justify-center mx-auto shadow-lg">
                    <Sparkles className="w-10 h-10 text-white" />
                </div>
                <div className="space-y-4">
                    <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 leading-tight">
                        Welcome to College Information Chatbot
                    </h2>
                    <p className="text-slate-600 text-base sm:text-lg max-w-xl mx-auto leading-relaxed">
                        Ask me anything about your college! I can help with admissions, courses, facilities, and more.
                    </p>
                </div>
                <div className="flex flex-col sm:flex-row flex-wrap gap-3 justify-center pt-2">
                    {["What courses are available?", "Tell me about admission requirements", "What facilities does the college have?"].map((suggestion, i) => (
                        <button
                            key={i}
                            onClick={() => {
                                setInputValue(suggestion);
                                inputRef.current?.focus();
                            }}
                            className="px-5 py-3 bg-white hover:bg-slate-50 border border-slate-300 hover:border-blue-400 rounded-lg text-sm font-medium text-slate-700 hover:text-blue-700 transition-all duration-200 shadow-sm hover:shadow-md"
                        >
                            {suggestion}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );

    return (
        <div className="flex flex-col h-[calc(100vh-180px)] w-full max-w-4xl mx-auto">
            {/* Messages Container */}
            <div 
                className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6 custom-scrollbar min-h-0" 
                ref={messagesContainerRef}
            >
                {messages.length === 0 && <EmptyState />}

                {messages.map((msg, i) => (
                    <div
                        key={i}
                        className={`flex items-start gap-3 sm:gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        {msg.role === 'assistant' && (
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center shadow-sm">
                                <Bot className="w-4 h-4 text-white" />
                            </div>
                        )}

                        <div className={`flex flex-col gap-2 max-w-[85%] sm:max-w-[75%] lg:max-w-[70%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                            <div className={`rounded-2xl px-4 py-3 shadow-sm ${
                                msg.role === 'user'
                                    ? 'bg-blue-600 text-white'
                                    : msg.isError
                                        ? 'bg-red-50 text-red-800 border border-red-200'
                                        : 'bg-white text-slate-900 border border-slate-200'
                            }`}>
                                <p className="text-[15px] sm:text-base leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
                            </div>

                            {/* Metadata for assistant messages */}
                            {msg.role === 'assistant' && !msg.isError && (
                                <div className="w-full space-y-2">
                                    <SourceDisplay
                                        sources={msg.sources}
                                        chunksUsed={msg.chunksUsed}
                                    />
                                    <ResponseTypeIndicator
                                        isRAGResponse={msg.isRAGResponse}
                                        fallbackUsed={msg.fallbackUsed}
                                        processingTime={msg.processingTime}
                                    />
                                </div>
                            )}
                        </div>

                        {msg.role === 'user' && (
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-500 flex items-center justify-center shadow-sm">
                                <User className="w-4 h-4 text-white" />
                            </div>
                        )}
                    </div>
                ))}

                <RAGLoadingIndicator />
                <div ref={messagesEndRef} className="h-4" />
            </div>

            {/* Input Area - Fixed at bottom with proper spacing */}
            <div className="flex-shrink-0 border-t border-slate-200 bg-white px-4 sm:px-6 lg:px-8 py-4 sm:py-5">
                <div className="max-w-3xl mx-auto w-full">
                    <div className="relative flex items-center">
                        <div className="flex-1 relative">
                            <textarea
                                ref={inputRef}
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyPress={handleKeyPress}
                                placeholder={isSending ? "Processing your message..." : "Ask me anything about the college..."}
                                disabled={isSending}
                                rows={1}
                                className="w-full px-4 py-3.5 pr-12 bg-slate-50 border-2 border-slate-300 rounded-2xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all resize-none text-[15px] sm:text-base placeholder:text-slate-500 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                                style={{ minHeight: '56px', maxHeight: '200px' }}
                                onInput={(e) => {
                                    e.target.style.height = 'auto';
                                    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
                                }}
                            />
                            <button
                                onClick={handleSend}
                                disabled={!inputValue.trim() || isSending}
                                className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-xl bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center shadow-md hover:shadow-lg disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:scale-105 active:scale-95"
                            >
                                {isSending ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <Send className="w-4 h-4" />
                                )}
                            </button>
                        </div>
                    </div>
                    <p className="text-xs text-slate-500 text-center mt-3">
                        Press <kbd className="px-2 py-1 bg-slate-100 rounded text-xs font-mono border border-slate-200">Enter</kbd> to send, <kbd className="px-2 py-1 bg-slate-100 rounded text-xs font-mono border border-slate-200">Shift+Enter</kbd> for new line
                    </p>
                </div>
            </div>
        </div>
    );
};

export default ChatInterface;

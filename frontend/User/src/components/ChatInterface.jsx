import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { userAPI } from '../services/api';
import {
  PromptInput,
  PromptInputActions,
  PromptInputTextarea,
} from "./ui/prompt-input";
import { Button } from "./ui/button";
import { ArrowUpIcon, User, Bot, FileText, AlertCircle, Clock, CheckCircle } from "lucide-react";

const ChatInterface = () => {
    const { user } = useAuth();
    const [inputValue, setInputValue] = useState("");
    const [messages, setMessages] = useState([]);
    const [isSending, setIsSending] = useState(false);
    const [isProcessingRAG, setIsProcessingRAG] = useState(false);
    const conversationIdRef = useRef(window.crypto.randomUUID());
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        const trimmed = inputValue.trim();
        if (!trimmed || isSending) return;

        const userMessage = { role: 'user', content: trimmed };
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
            
            // Handle enhanced RAG response format
            const assistantMessage = {
                role: 'assistant',
                content: data.content || data.response || "No response received",
                sources: data.sources || [],
                metadata: data.metadata || {},
                isRAGResponse: data.metadata?.rag_enabled || false,
                fallbackUsed: data.metadata?.fallback_used || false,
                chunksUsed: data.metadata?.chunks_used || 0,
                processingTime: data.metadata?.processing_time_ms || 0,
                responseType: data.metadata?.response_type || 'unknown'
            };
            
            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            console.error("Error sending message:", error);
            
            // Handle RAG-specific error messages gracefully
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
                originalError: error.message
            }]);
        } finally {
            setIsSending(false);
            setIsProcessingRAG(false);
        }
    };

    // Component for displaying source documents
    const SourceDisplay = ({ sources, chunksUsed, responseType }) => {
        if (!sources || sources.length === 0) return null;

        return (
            <div className="mt-2 p-2 bg-slate-50 rounded-md border-l-4 border-blue-200">
                <div className="flex items-center space-x-2 text-xs text-slate-600 mb-1">
                    <FileText size={12} />
                    <span className="font-medium">Sources ({sources.length})</span>
                    {chunksUsed > 0 && (
                        <span className="text-slate-500">• {chunksUsed} chunks used</span>
                    )}
                </div>
                <div className="flex flex-wrap gap-1">
                    {sources.map((source, index) => (
                        <span 
                            key={index}
                            className="inline-block px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full"
                        >
                            {source}
                        </span>
                    ))}
                </div>
            </div>
        );
    };

    // Component for displaying response type indicator
    const ResponseTypeIndicator = ({ isRAGResponse, fallbackUsed, responseType, processingTime }) => {
        if (!isRAGResponse && !fallbackUsed) return null;

        const getIndicatorConfig = () => {
            if (isRAGResponse && !fallbackUsed) {
                return {
                    icon: <CheckCircle size={12} />,
                    text: "Document-based response",
                    bgColor: "bg-green-100",
                    textColor: "text-green-700",
                    borderColor: "border-green-200"
                };
            } else if (fallbackUsed) {
                return {
                    icon: <AlertCircle size={12} />,
                    text: "Basic response (documents unavailable)",
                    bgColor: "bg-yellow-100",
                    textColor: "text-yellow-700",
                    borderColor: "border-yellow-200"
                };
            }
            return null;
        };

        const config = getIndicatorConfig();
        if (!config) return null;

        return (
            <div className={`mt-1 px-2 py-1 rounded-md border ${config.bgColor} ${config.borderColor}`}>
                <div className={`flex items-center space-x-1 text-xs ${config.textColor}`}>
                    {config.icon}
                    <span>{config.text}</span>
                    {processingTime > 0 && (
                        <>
                            <Clock size={10} />
                            <span>{processingTime}ms</span>
                        </>
                    )}
                </div>
            </div>
        );
    };

    // Component for displaying loading state during RAG processing
    const RAGLoadingIndicator = () => {
        if (!isProcessingRAG) return null;

        return (
            <div className="flex items-start space-x-2 max-w-[80%]">
                <div className="mt-1">
                    <Bot size={16} />
                </div>
                <div className="bg-slate-100 text-slate-800 rounded-lg p-3">
                    <div className="flex items-center space-x-2">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                        <span className="text-sm">Searching documents and generating response...</span>
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="flex h-[calc(100vh-200px)] flex-col">
            {/* Messages Display */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && (
                    <div className="flex h-full items-center justify-center text-slate-400">
                        Ask me anything about the college...
                    </div>
                )}
                {messages.map((msg, i) => (
                    <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                        <div className={`flex max-w-[80%] items-start space-x-2 rounded-lg p-3 ${
                            msg.role === 'user' 
                                ? 'bg-blue-600 text-white' 
                                : msg.isError 
                                    ? 'bg-red-100 text-red-800 border border-red-200'
                                    : 'bg-slate-100 text-slate-800'
                        }`}>
                            <div className="mt-1">
                                {msg.role === 'user' ? (
                                    <User size={16} />
                                ) : msg.isError ? (
                                    <AlertCircle size={16} />
                                ) : (
                                    <Bot size={16} />
                                )}
                            </div>
                            <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                        </div>
                        
                        {/* Enhanced source display for assistant messages */}
                        {msg.role === 'assistant' && !msg.isError && (
                            <div className="w-full max-w-[80%] mt-1">
                                <SourceDisplay 
                                    sources={msg.sources} 
                                    chunksUsed={msg.chunksUsed}
                                    responseType={msg.responseType}
                                />
                                <ResponseTypeIndicator 
                                    isRAGResponse={msg.isRAGResponse}
                                    fallbackUsed={msg.fallbackUsed}
                                    responseType={msg.responseType}
                                    processingTime={msg.processingTime}
                                />
                            </div>
                        )}
                    </div>
                ))}
                
                {/* Show loading indicator during RAG processing */}
                <RAGLoadingIndicator />
                
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="mt-4 p-4">
                <PromptInput
                    className="border-input bg-background border shadow-xs"
                    value={inputValue}
                    onValueChange={setInputValue}
                    onSubmit={handleSend}
                >
                    <PromptInputTextarea 
                        placeholder={isSending ? "Processing your message..." : "Type a message..."} 
                        disabled={isSending} 
                    />
                    <PromptInputActions className="justify-end">
                        <Button
                            size="sm"
                            className="size-9 cursor-pointer rounded-full"
                            onClick={handleSend}
                            disabled={!inputValue.trim() || isSending}
                        >
                            {isSending ? (
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                            ) : (
                                <ArrowUpIcon className="h-4 w-4" />
                            )}
                        </Button>
                    </PromptInputActions>
                </PromptInput>
            </div>
        </div>
    );
};

export default ChatInterface;
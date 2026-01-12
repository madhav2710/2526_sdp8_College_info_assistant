import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { userAPI } from '../services/api';
import {
  PromptInput,
  PromptInputActions,
  PromptInputTextarea,
} from "./ui/prompt-input";
import { Button } from "./ui/button";
import { ArrowUpIcon, User, Bot } from "lucide-react";

const ChatInterface = () => {
    const { user } = useAuth();
    const [inputValue, setInputValue] = useState("");
    const [messages, setMessages] = useState([]);
    const [isSending, setIsSending] = useState(false);
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

        try {
            const data = await userAPI.sendMessage(
                conversationIdRef.current,
                user.userId,
                trimmed
            );
            
            // Handle new RAG response format
            const assistantMessage = {
                role: 'assistant',
                content: data.content || data.response || "No response received",
                sources: data.sources || []
            };
            
            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            console.error("Error sending message:", error);
            setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${error.message}` }]);
        } finally {
            setIsSending(false);
        }
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
                            msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-800'
                        }`}>
                            <div className="mt-1">
                                {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                            </div>
                            <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                        </div>
                        {/* Show sources if available */}
                        {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                            <div className="mt-1 px-2 text-xs text-slate-500">
                                Sources: {msg.sources.join(', ')}
                            </div>
                        )}
                    </div>
                ))}
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
                    <PromptInputTextarea placeholder="Type a message..." disabled={isSending} />
                    <PromptInputActions className="justify-end">
                        <Button
                            size="sm"
                            className="size-9 cursor-pointer rounded-full"
                            onClick={handleSend}
                            disabled={!inputValue.trim() || isSending}
                        >
                            <ArrowUpIcon className="h-4 w-4" />
                        </Button>
                    </PromptInputActions>
                </PromptInput>
            </div>
        </div>
    );
};

export default ChatInterface;
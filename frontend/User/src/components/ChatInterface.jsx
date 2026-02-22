import React, { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle,
  Clock,
  FileText,
  Loader2,
  Send,
  User,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { userAPI } from "../services/api";
import CollegeSelector from "./CollegeSelector";
import MarkdownRenderer from "./MarkdownRenderer";

const ChatInterface = ({ conversationId, onConversationChange }) => {
  const { user } = useAuth();
  const [inputValue, setInputValue] = useState("");
  const [messages, setMessages] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const [isProcessingRAG, setIsProcessingRAG] = useState(false);
  const [selectedCollegeId, setSelectedCollegeId] = useState(() => {
    if (user?.collegeId) return user.collegeId;
    const saved = localStorage.getItem("selectedCollegeId");
    return saved || null;
  });

  // UUID generation fallback for non-secure contexts (HTTP)
  const generateUUID = () => {
    if (typeof window !== "undefined" && window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
      (
        c ^
        (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))
      ).toString(16)
    );
  };

  const conversationIdRef = useRef(conversationId || generateUUID());
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const messagesContainerRef = useRef(null);

  useEffect(() => {
    if (user?.collegeId) setSelectedCollegeId(user.collegeId);
  }, [user?.collegeId]);

  useEffect(() => {
    if (!user && selectedCollegeId) localStorage.setItem("selectedCollegeId", selectedCollegeId);
    if (!user && !selectedCollegeId) localStorage.removeItem("selectedCollegeId");
  }, [selectedCollegeId, user]);

  useEffect(() => {
    if (conversationId) {
      conversationIdRef.current = conversationId;
      loadConversation(conversationId);
    } else {
      conversationIdRef.current = generateUUID();
      setMessages([]);
    }
  }, [conversationId]);

  const loadConversation = async (convId) => {
    if (!user?.userId || !convId) return;
    try {
      const data = await userAPI.getConversationMessages(convId);
      if (data && data.messages) {
        const formattedMessages = data.messages.map((msg) => ({
          role: msg.role,
          content: msg.content,
          timestamp: msg.created_at,
          sources: msg.metadata?.sources || [],
          isRAGResponse: msg.metadata?.rag_enabled || false,
          fallbackUsed: msg.metadata?.fallback_used || false,
          chunksUsed: msg.metadata?.chunks_used || 0,
          processingTime: msg.metadata?.processing_time_ms || 0,
          responseType: msg.metadata?.response_type || "unknown",
          metadata: msg.metadata || {},
        }));
        setMessages(formattedMessages);
      } else {
        setMessages([]);
      }
    } catch (error) {
      console.error("Failed to load conversation:", error);
      setMessages([]);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || isSending) return;

    if (!selectedCollegeId && !user?.collegeId) {
      alert("Please select a college first to get accurate information.");
      return;
    }

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      },
    ]);
    setInputValue("");
    setIsSending(true);
    setIsProcessingRAG(true);

    try {
      const collegeIdToUse = selectedCollegeId || user?.collegeId;
      const data = await userAPI.sendMessage(
        conversationIdRef.current,
        user?.userId,
        collegeIdToUse,
        trimmed,
      );

      const assistantMessage = {
        role: "assistant",
        content: data.content || data.response || "No response received",
        sources: data.sources || [],
        metadata: data.metadata || {},
        isRAGResponse: data.metadata?.rag_enabled || false,
        fallbackUsed: data.metadata?.fallback_used || false,
        chunksUsed: data.metadata?.chunks_used || 0,
        processingTime: data.metadata?.processing_time_ms || 0,
        responseType: data.metadata?.response_type || "unknown",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      if (onConversationChange) onConversationChange(conversationIdRef.current);
    } catch (error) {
      console.error("Error sending message:", error);
      let errorMessage = "I encountered an error while processing your request.";

      if (error.message.includes("AI service")) {
        errorMessage = "The AI service is temporarily unavailable. Please try again shortly.";
      } else if (error.message.includes("Document search")) {
        errorMessage = "Document search is temporarily unavailable. You can try again in a moment.";
      } else if (error.message.includes("temporarily unavailable")) {
        errorMessage = "The chat service is temporarily unavailable. Please try again shortly.";
      } else if (error.message.includes("rate limit")) {
        errorMessage = "You're sending messages too quickly. Please wait and try again.";
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: errorMessage,
          isError: true,
          originalError: error.message,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsSending(false);
      setIsProcessingRAG(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const SourceDisplay = ({ sources, chunksUsed }) => {
    if (!sources || sources.length === 0) return null;
    return (
      <div className="mt-3 rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-subtle)] p-3">
        <div className="type-meta mb-2 flex items-center gap-1.5 text-[var(--text-secondary)]">
          <FileText className="h-3.5 w-3.5" />
          Sources ({sources.length})
          {chunksUsed > 0 && <span className="normal-case tracking-normal">• {chunksUsed} chunks</span>}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {sources.map((source, index) => (
            <span
              key={index}
              className="inline-flex items-center rounded-full border border-[var(--border-soft)] bg-[var(--bg-surface)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)]"
            >
              {source}
            </span>
          ))}
        </div>
      </div>
    );
  };

  const ResponseTypeIndicator = ({ isRAGResponse, fallbackUsed, processingTime }) => {
    if (!isRAGResponse && !fallbackUsed) return null;

    const cfg = isRAGResponse && !fallbackUsed
      ? {
        icon: <CheckCircle className="h-3.5 w-3.5" />,
        text: "Document-based response",
        color: "text-[var(--success)]",
        border: "border-[var(--border-soft)]",
        bg: "bg-[var(--bg-subtle)]",
      }
      : {
        icon: <AlertCircle className="h-3.5 w-3.5" />,
        text: "Basic response",
        color: "text-[var(--warning)]",
        border: "border-[var(--border-soft)]",
        bg: "bg-[var(--bg-subtle)]",
      };

    return (
      <div
        className={`mt-2 inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium ${cfg.color} ${cfg.border} ${cfg.bg}`}
      >
        {cfg.icon}
        <span>{cfg.text}</span>
        {processingTime > 0 && (
          <>
            <Clock className="h-3 w-3 opacity-70" />
            <span className="font-mono-ui opacity-75">{processingTime}ms</span>
          </>
        )}
      </div>
    );
  };

  const RAGLoadingIndicator = () => {
    if (!isProcessingRAG) return null;
    return (
      <div className="mb-5 flex items-start gap-3">
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border border-[var(--border-soft)] bg-[var(--bg-surface)] text-[var(--accent)]">
          <Bot className="h-4 w-4" />
        </div>
        <div className="surface-primary flex-1 px-4 py-3">
          <div className="mb-2 flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-[var(--accent)]" />
            <span className="type-small text-[var(--text-secondary)]">Searching documents and composing response...</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-[var(--bg-subtle)]">
            <div className="h-full w-[62%] rounded-full bg-[var(--accent)]" />
          </div>
        </div>
      </div>
    );
  };

  const EmptyState = () => (
    <div className="flex min-h-[56vh] flex-col items-center justify-center px-4 py-12 text-center">
      <div className="mx-auto w-full max-w-2xl space-y-6">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-[16px] border border-[var(--border-soft)] bg-[var(--bg-surface)] text-[var(--accent)]">
          <Bot className="h-7 w-7" />
        </div>
        <div className="space-y-3">
          <h2 className="type-h2">Ask about your college</h2>
          <p className="mx-auto max-w-xl type-body text-[var(--text-secondary)]">
            Select a college and ask clear, specific questions. Answers are organized for quick reading and citation review.
          </p>
        </div>
        <div className="mx-auto flex max-w-2xl flex-col gap-2.5 pt-2 sm:flex-row sm:flex-wrap sm:justify-center">
          {[
            "Summarize admission requirements for undergraduate applicants.",
            "What are the tuition and scholarship options?",
            "List top facilities and student support services.",
          ].map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => {
                setInputValue(suggestion);
                inputRef.current?.focus();
              }}
              className="rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-surface)] px-4 py-2.5 text-sm text-[var(--text-secondary)] transition-colors duration-[140ms] hover:bg-[var(--bg-subtle)]"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="mx-auto flex h-[calc(100vh-128px)] w-full max-w-[1100px] flex-col">
      <div className="px-4 pb-2 pt-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-[840px]">
          <CollegeSelector selectedCollegeId={selectedCollegeId} onCollegeChange={setSelectedCollegeId} />
          {!selectedCollegeId && !user?.collegeId && (
            <p className="mt-2 flex items-center gap-1 text-xs text-[var(--warning)]">
              <AlertCircle className="h-3 w-3" />
              Please select a college to receive institution-specific answers.
            </p>
          )}
        </div>
      </div>

      <div
        className="custom-scrollbar min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 lg:px-8"
        ref={messagesContainerRef}
      >
        <div className="mx-auto flex w-full max-w-[840px] flex-col gap-5">
          {messages.length === 0 && <EmptyState />}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`message-enter flex items-start gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "assistant" && (
                <div className="mt-1 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-[var(--border-soft)] bg-[var(--bg-surface)] text-[var(--accent)]">
                  <Bot className="h-3.5 w-3.5" />
                </div>
              )}

              <div className={`flex max-w-[86%] flex-col gap-2 ${msg.role === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`rounded-[16px] px-4 py-3 shadow-[0_1px_2px_rgba(31,31,28,0.06)] ${msg.role === "user"
                      ? "border border-[var(--accent)] bg-[var(--accent)] text-[#f8f8f6]"
                      : msg.isError
                        ? "border border-[#d9b4b4] bg-[#f8ecec] text-[var(--danger)]"
                        : "border border-[var(--border-soft)] bg-[var(--bg-surface)] text-[var(--text-primary)]"
                    }`}
                >
                  {msg.role === "assistant" && !msg.isError ? (
                    <MarkdownRenderer content={msg.content} className="text-[16px]" />
                  ) : (
                    <p className="type-body whitespace-pre-wrap break-words">{msg.content}</p>
                  )}
                </div>

                {msg.role === "assistant" && !msg.isError && (
                  <div className="w-full">
                    <SourceDisplay sources={msg.sources} chunksUsed={msg.chunksUsed} />
                    <ResponseTypeIndicator
                      isRAGResponse={msg.isRAGResponse}
                      fallbackUsed={msg.fallbackUsed}
                      processingTime={msg.processingTime}
                    />
                  </div>
                )}
              </div>

              {msg.role === "user" && (
                <div className="mt-1 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-[var(--border-soft)] bg-[var(--bg-subtle)] text-[var(--text-secondary)]">
                  <User className="h-3.5 w-3.5" />
                </div>
              )}
            </div>
          ))}

          <RAGLoadingIndicator />
          <div ref={messagesEndRef} className="h-4" />
        </div>
      </div>

      <div className="flex-shrink-0 border-t border-[var(--border-soft)] bg-[var(--bg-canvas)] px-4 py-4 sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-[840px]">
          <div className="surface-primary relative rounded-[16px] px-3 py-3">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder={isSending ? "Processing your message..." : "Ask a focused question about your selected college..."}
              disabled={isSending}
              rows={1}
              className="max-h-[200px] min-h-[52px] w-full resize-none border-0 bg-transparent px-2 py-2 pr-12 text-[16px] leading-[1.7] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
              onInput={(e) => {
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
              }}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || isSending}
              className="absolute right-3 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-[12px] border border-[var(--accent)] bg-[var(--accent)] text-white transition-colors duration-[140ms] hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </div>

          <p className="mt-2 text-center text-xs text-[var(--text-muted)]">
            Press <span className="font-mono-ui">Enter</span> to send and <span className="font-mono-ui">Shift+Enter</span> for a new line.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;

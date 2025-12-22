"use client"

import {
  PromptInput,
  PromptInputActions,
  PromptInputTextarea,
} from "@/components/ui/prompt-input"
import { Button } from "@/components/ui/button"
import { ArrowUpIcon } from "lucide-react"
import { useState, useRef } from "react"

/**
 * Example showing PromptInput without suggestions
 */
export function PromptSuggestionBasic() {
  const [inputValue, setInputValue] = useState("")
  const conversationIdRef = useRef(window.crypto.randomUUID())

  const handleSend = async () => {
    const trimmed = inputValue.trim()
    if (!trimmed) return

    try {
      const response = await fetch("http://127.0.0.1:8000/chat/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conversation_id: conversationIdRef.current,
          role: "user",
          content: trimmed,
        }),
      })

      if (!response.ok) {
        console.error("Failed to send message:", await response.text())
        return
      }

      const data = await response.json()
      console.log("Saved to database:", data)
      setInputValue("")
    } catch (error) {
      console.error("Error sending message:", error)
    }
  }

  return (
    <div className="flex w-full flex-col space-y-4">
      <PromptInput
        className="border-input bg-background border shadow-xs"
        value={inputValue}
        onValueChange={setInputValue}
        onSubmit={handleSend}
      >
        <PromptInputTextarea placeholder="Type a message..." />
        <PromptInputActions className="justify-end">
          <Button
            size="sm"
            className="size-9 cursor-pointer rounded-full"
            onClick={handleSend}
            disabled={!inputValue.trim()}
            aria-label="Send"
          >
            <ArrowUpIcon className="h-4 min-h-4  min-w-4 w-4" />
          </Button>
        </PromptInputActions>
      </PromptInput>
    </div>
  )
}


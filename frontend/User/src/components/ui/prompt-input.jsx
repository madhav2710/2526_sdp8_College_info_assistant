import * as React from "react"
import { cn } from "@/lib/utils"

const PromptInputContext = React.createContext({
  value: "",
  onValueChange: () => {},
})

export function PromptInput({ className, value, onValueChange, onSubmit, children, ...props }) {
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      if (onSubmit && value.trim()) {
        onSubmit()
      }
    }
  }

  return (
    <PromptInputContext.Provider value={{ value, onValueChange }}>
      <div
        className={cn("flex w-full flex-col gap-2 rounded-lg p-3", className)}
        onKeyDown={handleKeyDown}
        {...props}
      >
        {children}
      </div>
    </PromptInputContext.Provider>
  )
}

export function PromptInputTextarea({ className, placeholder, ...props }) {
  const { value, onValueChange } = React.useContext(PromptInputContext)
  
  return (
    <textarea
      className={cn(
        "min-h-[60px] w-full resize-none bg-transparent px-1 py-2 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
      {...props}
    />
  )
}

export function PromptInputActions({ className, ...props }) {
  return (
    <div
      className={cn("flex items-center", className)}
      {...props}
    />
  )
}


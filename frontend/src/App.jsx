import { useState } from "react"
import { PromptSuggestionBasic } from "./components/demo"
import SuperAdminPanel from "./components/SuperAdminPanel"
import "./index.css"

function App() {
  const [showAdmin, setShowAdmin] = useState(false)

  if (showAdmin) {
    return (
      <div className="relative">
        <button 
          onClick={() => setShowAdmin(false)}
          className="fixed bottom-4 right-4 z-[300] bg-slate-800 text-white px-4 py-2 rounded-lg shadow-lg font-bold text-xs"
        >
          Exit Admin
        </button>
        <SuperAdminPanel />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background p-8">
      <button 
        onClick={() => setShowAdmin(true)}
        className="fixed top-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg font-bold text-xs hover:bg-blue-700 transition-colors"
      >
        Go to Super Admin
      </button>
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-8 text-3xl font-bold">College Information Chatbot</h1>
        <PromptSuggestionBasic />
      </div>
    </div>
  )
}

export default App


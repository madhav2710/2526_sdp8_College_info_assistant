import { PromptSuggestionBasic } from "./components/demo"
import "./index.css"

function App() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-8 text-3xl font-bold">College Information Chatbot</h1>
        <PromptSuggestionBasic />
      </div>
    </div>
  )
}

export default App


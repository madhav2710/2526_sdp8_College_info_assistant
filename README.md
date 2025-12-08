🎓 CollegeInfo-Agent: RAG-Based Multi-College Academic Assistant

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![React](https://img.shields.io/badge/Frontend-React-%2361DAFB)
![RAG](https://img.shields.io/badge/Architecture-RAG-green)
![ChromaDB](https://img.shields.io/badge/DB-ChromaDB-purple)
![FastAPI](https://img.shields.io/badge/API-FastAPI-teal)

## 📖 Project Overview

**CollegeInfo-Agent** is an intelligent, multi-tenant academic assistant that automates student and faculty queries for multiple colleges.

The system uses **Retrieval-Augmented Generation (RAG)** to ingest unstructured institutional data such as:

- 📄 Syllabus PDFs
- 📢 Placement notices
- 🗓 Academic calendars
- 🏫 College overview / brochures

and then answers questions using **LLMs** grounded in a **local ChromaDB vector store** to minimize hallucinations and provide **source-backed answers**.

This version introduces a **React frontend**, a **Python backend**, and a **multi-level admin system** with **Super Admin + College Admins**.

---

## 🌟 Key Features

### 🔍 RAG-Powered Q&A

- Ask questions about syllabus, subjects, placement stats, timelines, rules, etc.
- Answers are grounded in documents stored in **ChromaDB**.
- Each answer can include **citations / source snippets**.

### 🏫 Multi-College Support

- Each college has its **own isolated knowledge base**.
- College-level configuration and branding (name, logo, basic info).

### 👤 College Admin Panel

- One **Admin per college**.
- Admin can:
  - Upload documents (syllabus, placement PDFs, notices, college overview, etc.).
  - Trigger ingestion of files into ChromaDB for that specific college.
  - View and manage uploaded documents.
  - Optionally monitor query history for their college.

### 🛡 Super Admin Panel

- **Super Admin** oversees the whole platform.
- Super Admin can:
  - Create / Read / Update / Delete (**CRUD**) college admins.
  - Associate admins with specific colleges.
  - Disable/enable admins.
  - View high-level system stats (number of colleges, documents, queries).

### 💻 Modern React Frontend

- Separate **React** frontend application.
- Role-based views:
  - 🎓 Student/Faculty: Ask questions via chat-like UI.
  - 👤 College Admin: Document upload & ingestion dashboard.
  - 🛡 Super Admin: Admin management dashboard.

### 🧠 Backend Intelligence (Python)

- Python backend (e.g. **FastAPI**) handles:
  - File uploads.
  - PDF text extraction.
  - Chunking & embedding.
  - Storage & retrieval from **ChromaDB**.
  - Orchestrating calls to **LLMs** (OpenAI / Google Gemini / others via LangChain).

---

## 🛠️ Technology Stack

| Component        | Technology                          | Role                                 |
| :--------------- | :---------------------------------- | :----------------------------------- |
| Language         | Python 3.10+                        | Backend logic                        |
| Backend          | FastAPI (or Flask)                  | REST API for frontend & ingestion    |
| Frontend         | React (Vite/CRA)                    | Web UI (Students, Admin, SuperAdmin) |
| RAG Orchestrator | LangChain / langgraph (optional)    | RAG pipeline                         |
| Vector DB        | ChromaDB (service / local)          | Document embeddings & retrieval      |
| LLM              | OpenAI / Google Gemini / compatible | Answer generation                    |
| ETL              | PyPDF / pdfplumber                  | PDF text extraction                  |
| Config           | python-dotenv                       | Secrets & env vars                   |
| Auth (optional)  | JWT / OAuth2                        | Role-based authentication            |

---

### 💬 Student Q&A Flow

1. Student selects their college.
2. Asks a question: _“What is the 5th semester syllabus for IT?”_
3. Backend:
   - Filters ChromaDB documents by `college_id`.
   - Retrieves top-k relevant chunks.
   - Builds a context prompt.
   - Calls LLM (OpenAI / Gemini) via LangChain.
   - Returns answer + optionally sources.
4. Frontend displays:
   - AI answer in chat bubble.
   - “Sources” section with document titles / snippets.

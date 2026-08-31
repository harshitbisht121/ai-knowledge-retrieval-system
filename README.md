# AI-Based Knowledge Retrieval Platform with Query Resolution System

An AI-powered Retrieval-Augmented Generation (RAG) platform that enables users to upload knowledge-base documents and query them using natural language. The project combines a multi-agent LangGraph workflow with persistent MySQL conversation memory, clarification handling, browser-based voice input/output, and response transparency.

> **Detailed Documentation:** See **`PROJECT_GUIDE.md`** for the complete architecture, workflow diagrams, backend/frontend design, API documentation, Milestone 2 and Milestone 3 implementation details, testing flow, and development guidelines.

## Features

- 📄 Upload PDF, DOCX, TXT, and CSV documents
- 🔍 Semantic document retrieval using ChromaDB and Sentence Transformers
- 🧠 Query Understanding Agent for normalization, entity/keyword extraction and query classification
- 🔎 Hybrid retrieval with semantic search and optional exact-term matching
- 📊 Query-aware relevance ranking and low-confidence filtering
- 🤖 Response Generation Agent for grounded answers
- 📚 Source attribution and retrieval-aware confidence scoring
- 🔗 LangGraph orchestration of the multi-agent workflow
- ❓ Clarification Agent for ambiguous queries and query refinement
- 💬 Persistent multi-turn conversation memory using MySQL and `conversation_id`
- 🧠 Context-aware follow-up resolution such as `What about its ranking?`
- 🎙️ Browser speech-to-text using the Web Speech API
- 🔊 Browser text-to-speech using Speech Synthesis API
- 🔍 Response transparency with citations, source details, confidence and retrieved chunk inspection
- 💻 React-based conversational interface
- 🗂️ Document management (view and delete indexed documents)
- 📈 Background document processing with upload status tracking

## Technology Stack

### Frontend

- React 19
- Vite
- JavaScript
- Vanilla CSS
- Web Speech API
- Browser Speech Synthesis API

### Backend

- Python 3
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy
- PyMySQL

### AI & Agent Layer

- LangChain
- LangGraph
- langchain-groq
- Groq LLM
- Sentence Transformers (`all-MiniLM-L6-v2`)
- ChromaDB
- Retrieval-Augmented Generation (RAG)

### Document Processing

- pypdf
- python-docx
- pandas
- LangChain text splitters

### API & File Handling

- python-multipart

## Project Structure

The project contains a single authoritative backend at the repository root. Do not place or maintain a second backend copy inside `frontend/`.

```text
AI-Based Knowledge Retrieval Platform with Query Resolution System/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── documents.py
│   │   │   ├── health.py
│   │   │   ├── query.py
│   │   │   ├── conversations.py
│   │   │   └── upload.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── llm.py
│   │   │   └── database.py
│   │   ├── models/
│   │   │   ├── request_models.py
│   │   │   ├── response_models.py
│   │   │   └── conversation.py
│   │   ├── rag/
│   │   │   ├── chromadb_service.py
│   │   │   ├── chunking.py
│   │   │   ├── embedding.py
│   │   │   └── extractor.py
│   │   ├── services/
│   │   │   ├── document_service.py
│   │   │   ├── metadata_service.py
│   │   │   ├── query_service.py
│   │   │   └── upload_service.py
│   │   ├── agents/
│   │   │   ├── query_understanding/
│   │   │   ├── retrieval/
│   │   │   ├── response_generation/
│   │   │   ├── clarification/
│   │   │   └── memory/
│   │   ├── voice/
│   │   │   ├── input.py
│   │   │   ├── output.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── transparency/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── test/
│   │   │   └── test_memory.py
│   │   └── orchestration/
│   │       ├── state.py
│   │       ├── nodes.py
│   │       ├── query_router.py
│   │       └── workflow.py
│   ├── chroma_db/
│   ├── metadata/
│   ├── uploads/
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   └── create_memory_tables.py
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatBubble.jsx
│   │   │   ├── CitationDisplay.jsx
│   │   │   ├── FileUploader.jsx
│   │   │   ├── Footer.jsx
│   │   │   ├── GroundingEvidenceView.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   ├── VoiceInput.jsx
│   │   │   └── speechtotext.jsx
│   │   ├── hooks/
│   │   │   └── useSpeechRecognition.js
│   │   ├── pages/
│   │   │   ├── ChatPage.jsx
│   │   │   └── UploadPage.jsx
│   │   ├── services/
│   │   │   └── api.js
│   │   ├── App.css
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── .env
│   ├── .env.example
│   ├── package.json
│   └── vite.config.js
├── PROJECT_GUIDE.md
└── README.md
```

## Milestone 2 Architecture

The validated Milestone 2 path is:

```text
User Query
    ↓
Query Understanding Agent
    ↓
Query Router
    ↓
Retrieval Agent
    ├── Semantic Search
    ├── Optional Exact Search
    ├── Query-aware Reranking
    └── Low-confidence Filtering
    ↓
Response Generation Agent
    ├── Grounded Answer
    ├── Source Citations
    └── Confidence
    ↓
FastAPI JSON Response
    ↓
React Frontend
    └── Context Inspector
```

## Milestone 3 Architecture

Milestone 3 preserves the M2 retrieval/response path and adds memory, clarification and browser voice capabilities:

```text
User Text / Voice Transcript
            ↓
     Conversation Memory
            ↓
Context-aware Follow-up Resolution
            ↓
    Query Understanding Agent
            ↓
       Query Router
       ↙          ↘
 Clarification    Retrieval
      ↓              ↓
 refined query   ranked chunks
      └──────→ Retrieval
                    ↓
          Response Generation
                    ↓
            Save Conversation
                    ↓
              React Frontend
```

### Clarification route

```text
Ambiguous Query
      ↓
Query Router
      ↓
Clarification Agent
      ↓
Clarification Question
      ↓
User Response
      ↓
Query Refinement
      ↓
Query Understanding
      ↓
Retrieval → Response
```

### Conversation Memory
Conversation turns are associated with a persistent `conversation_id` and stored in MySQL.

A contextual follow-up such as:

```text
What does the Retrieval Agent do?
What about its ranking?
```

can be resolved using the previous conversation before the normal retrieval workflow runs.

### Voice
Voice is browser-based:

```text
Microphone
   ↓
Web Speech API
   ↓
Transcript
   ↓
POST /query
   ↓
Same M3 workflow
   ↓
Answer
   ↓
Browser Speech Synthesis
```

The backend receives text, not microphone audio, in the current architecture.

### Response Transparency
The backend also contains a dedicated transparency service at `backend/app/transparency/`. It converts the existing retrieval result into structured evidence containing the source document, optional page, chunk ID, retrieved content, relevance score and a human-readable citation. It also returns a transparency-specific confidence value and `High`/`Medium`/`Low` confidence level.

`query.py` adds this object to the normal `/query` response under `transparency`; it does not replace the existing `response.confidence` or create a separate retrieval pipeline. No standalone `/transparency` request is required in the current architecture.

The frontend exposes:

- generated answer
- citation references
- source documents
- relevance scores
- confidence
- retrieved chunk IDs
- retrieved chunk content
- semantic score information

## Installation & Setup

### Backend

```bash
python -m venv .venv
```

Windows:

```cmd
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

Create `backend/.env` with the project's required Groq and MySQL settings. At minimum the project uses:

```env
GROQ_API_KEY=<your-key>
GROQ_MODEL=<configured-model>
DATABASE_URL=mysql+pymysql://<user>:<password>@localhost:<port>/<database>
```

Use the actual variable names defined by your local `app/core/database.py` configuration.

### Start MySQL

For a local Windows setup, start **MySQL** from XAMPP before using conversation memory.

### Create Conversation Tables

```bash
cd backend
python create_memory_tables.py
```

### Start FastAPI

```bash
uvicorn app.main:app --reload
```

Backend:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

### Frontend

Create:

```text
frontend/.env
```

Example:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not place `GROQ_API_KEY`, MySQL credentials, or any other backend secrets in the frontend environment.

Install and start:

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

## Usage

1. Start MySQL.
2. Start the FastAPI backend.
3. Start the React frontend.
4. Upload one or more supported documents.
5. Wait for document processing to complete.
6. Start a conversation through the chat interface.
7. Ask a question about the indexed documents.
8. Continue with contextual follow-ups without restating the previous topic.
9. Test ambiguous questions to trigger clarification.
10. Use the microphone to submit a voice transcript.
11. Inspect citations, confidence and retrieved context in the Context Inspector.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/documents` | List indexed documents |
| POST | `/upload` | Upload a document |
| GET | `/upload/status/{job_id}` | Check upload status |
| POST | `/query` | Run the Milestone 3 query workflow |
| DELETE | `/documents/{document_id}` | Delete an indexed document |
| POST | `/conversations` | Create a conversation |
| GET | `/conversations` | List conversations |
| GET | `/conversations/{conversation_id}` | Get a conversation and messages |
| GET | `/conversations/{conversation_id}/context` | Get memory context |
| DELETE | `/conversations/{conversation_id}` | Delete a conversation |

### `/query` normal request

```json
{
  "query": "What does the Retrieval Agent do?",
  "k": 3
}
```

### `/query` memory-enabled request

```json
{
  "query": "What about its ranking?",
  "k": 3,
  "conversation_id": "<conversation-id>"
}
```

### `/query` clarification follow-up

```json
{
  "query": "The Retrieval Agent",
  "k": 3,
  "conversation_id": "<conversation-id>",
  "clarification_answer": "The Retrieval Agent",
  "clarification_question": "Which agent are you referring to?",
  "original_query": "Tell me more about that."
}
```

### `/query` response

A successful response contains:

```text
success
query
conversation_id
query_understanding
route
route_reason
clarification_required
clarification_question
retrieval
response
transparency
```

The `transparency` object is built from the existing retrieval results and contains structured evidence such as source document, optional page, chunk ID, content, relevance score, citation, transparency confidence and confidence level.

For a normal answer:

```text
response.answer
response.sources
response.confidence
```

For an ambiguity-first response:

```text
clarification_required = true
clarification_question = "..."
```

`response` may be `null` until clarification has been completed.

## Conversation Memory Example

Create a conversation:

```text
POST /conversations
```

Use the returned ID for the first query:

```json
{
  "query": "What does the Retrieval Agent do?",
  "k": 3,
  "conversation_id": "1e7cb423-b494-417d-bacc-2b3ca46ead2b"
}
```

Then use the same ID for the follow-up:

```json
{
  "query": "What about its ranking?",
  "k": 3,
  "conversation_id": "1e7cb423-b494-417d-bacc-2b3ca46ead2b"
}
```

Expected behavior:

```text
First query
    ↓
Retrieval + Answer
    ↓
Stored in MySQL

Second query
    ↓
Memory Context
    ↓
Contextual Query Resolution
    ↓
Retrieval + Answer
    ↓
Stored in MySQL
```

## Voice Input Example

The current frontend does not upload audio to FastAPI. It uses the browser Web Speech API to obtain a transcript, then sends that transcript through the ordinary query API.

Example spoken query:

```text
What does the Retrieval Agent do?
```

The backend receives the equivalent of:

```json
{
  "query": "What does the Retrieval Agent do?",
  "k": 3,
  "conversation_id": "<conversation-id>"
}
```

## Supported File Types

- PDF
- DOCX
- TXT
- CSV

## Milestone 3 Validation

The current Milestone 3 implementation has been validated with:

- ambiguous query → Clarification Agent routing
- clarification question generation
- persistent conversation IDs
- MySQL-backed conversation storage
- multi-turn conversation history
- contextual follow-up resolution
- `What about its ranking?` being resolved in the context of the previous Retrieval Agent discussion
- clear queries continuing through the existing Retrieval and Response Generation path
- grounded responses with source citations and confidence
- `chunk_id` consistency between retrieval results and response sources
- Context Inspector source-to-chunk mapping
- frontend conversation creation
- frontend memory-enabled query submission
- browser Web Speech API integration in ChatPage
- speech transcript submission through the normal `/query` path
- dedicated transparency object generation from existing retrieval results
- transparency source/chunk evidence and confidence-level mapping
- Conversation Memory integration testing through `backend/app/test/test_memory.py`

## Troubleshooting

### Send and microphone buttons are disabled
The frontend waits for a backend `conversation_id`. Make sure MySQL is running and `POST /conversations` returns `200 OK`.

### `Can't connect to MySQL server on 'localhost'` / `WinError 10061`
Start MySQL from XAMPP and verify that the configured database exists and that the username/password/port in the backend environment match the local MySQL server.

### Retrieval returns no relevant results
Verify that the intended knowledge-base document is uploaded and indexed into the current ChromaDB before changing retrieval thresholds or reranking logic.

### Voice input does not start
Check browser Web Speech API support and microphone permissions. Voice recognition is performed in the browser, not by FastAPI.

## Security

Do not commit:

- `backend/.env`
- `frontend/.env`
- real Groq API keys
- MySQL passwords
- other backend-only secrets

Use `.env.example` files for safe placeholder configuration only.

## Documentation

For complete technical documentation, architecture diagrams, implementation details, API flow, RAG pipeline, Milestone 3 workflow, conversation memory, clarification, voice integration, response transparency, testing procedures, and development guidelines, refer to:

- **PROJECT_GUIDE.md**

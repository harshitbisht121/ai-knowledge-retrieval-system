/*
 * QueryNest API Service
 *
 * Centralized communication layer for the FastAPI backend.
 *
 * Responsibilities:
 * - Authentication
 * - Documents
 * - Conversations
 * - RAG queries
 * - Milestone 3 clarification/memory support
 */

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '');

let useMock = false;

const mockDocuments = [];


/* ------------------------------------------------------------------ */
/* Mock mode                                                          */
/* ------------------------------------------------------------------ */

export const setMockMode = (enable) => {
  useMock = Boolean(enable);
};

export const getMockMode = () => useMock;


/* ------------------------------------------------------------------ */
/* Authentication helpers                                             */
/* ------------------------------------------------------------------ */

/*
 * Return the currently stored authentication token.
 *
 * localStorage is checked first because that is the normal
 * authenticated session storage used by QueryNest.
 */
export const getAuthToken = () => {
  return (
    localStorage.getItem('qn_auth_token') ||
    sessionStorage.getItem('qn_auth_token')
  );
};


/*
 * Build common authenticated headers.
 *
 * The backend expects:
 * Authorization: Bearer <token>
 */
export function getAuthHeaders(includeJsonContentType = false) {
  const headers = {};

  if (includeJsonContentType) {
    headers['Content-Type'] = 'application/json';
  }

  headers.Accept = 'application/json';

  const token = getAuthToken();

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
};


/* ------------------------------------------------------------------ */
/* Response handling                                                   */
/* ------------------------------------------------------------------ */

async function parseResponse(response) {
  let data = {};

  try {
    data = await response.json();
  } catch {
    // Some responses may not contain JSON.
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;

    if (typeof data?.detail === 'string') {
      message = data.detail;
    } else if (typeof data?.message === 'string') {
      message = data.message;
    } else if (Array.isArray(data?.detail)) {
      message = data.detail
        .map((item) => item?.msg || 'Invalid request.')
        .join(', ');
    }

    const error = new Error(message);
    error.status = response.status;
    error.data = data;

    throw error;
  }

  return data;
}


/*
 * Handle authentication failures consistently.
 */
export const isUnauthorizedError = (error) => {
  return error?.status === 401;
};


/* ------------------------------------------------------------------ */
/* Authentication APIs                                                 */
/* ------------------------------------------------------------------ */


/*
 * Log in an existing user.
 */
export async function loginUser(email, password) {
  const response = await fetch(
    `${API_BASE_URL}/auth/login`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        email: email.trim(),
        password,
      }),
    },
  );

  return parseResponse(response);
}


/*
 * Register a new user.
 */
export async function registerUser(
  fullName,
  email,
  password,
) {
  const response = await fetch(
    `${API_BASE_URL}/auth/register`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      }),
    },
  );

  return parseResponse(response);
}


/*
 * Validate the saved token and retrieve the current user.
 */
export async function getCurrentUser() {
  const token = getAuthToken();

  if (!token) {
    throw new Error('Authentication token not found.');
  }

  const response = await fetch(
    `${API_BASE_URL}/auth/me`,
    {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
    },
  );

  return parseResponse(response);
}


/*
 * Log out the current user on the backend.
 *
 * JWT is currently stateless, so local session data is also
 * cleared by AuthContext after this request.
 */
export async function logoutUser(token = null) {
  const authToken = token || getAuthToken();

  if (!authToken) {
    return {
      success: true,
      message: 'Already signed out.',
    };
  }

  const response = await fetch(
    `${API_BASE_URL}/auth/logout`,
    {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${authToken}`,
      },
    },
  );

  return parseResponse(response);
}


/* ------------------------------------------------------------------ */
/* Knowledge Base / Document APIs                                      */
/* ------------------------------------------------------------------ */


/*
 * Normalize the backend Knowledge Base document shape into the shape
 * expected by the existing UploadPage/FileUploader UI.
 *
 * Backend:
 *   id, filename, original_filename, file_type, file_size,
 *   status, created_at, updated_at
 *
 * Frontend compatibility:
 *   id, name, size, status(indexed|parsing|failed),
 *   uploadedAt, etc.
 */
function normalizeKnowledgeBaseDocument(document) {
  if (!document || typeof document !== 'object') {
    return null;
  }

  const backendStatus = String(document.status || '').toLowerCase();

  let uiStatus = 'parsing';
  let stage = 'processing';
  let progress = 50;

  if (backendStatus === 'completed' || backendStatus === 'indexed') {
    uiStatus = 'indexed';
    stage = 'completed';
    progress = 100;
  } else if (backendStatus === 'failed') {
    uiStatus = 'failed';
    stage = 'failed';
    progress = 100;
  }

  return {
    id: document.id,
    name:
      document.original_filename ||
      document.filename ||
      'Unnamed document',
    size: Number(document.file_size || 0),
    status: uiStatus,
    stage,
    progress,
    message:
      backendStatus === 'completed' || backendStatus === 'indexed'
        ? 'Document processed successfully.'
        : backendStatus === 'failed'
          ? 'Document processing failed.'
          : 'Document is being processed.',
    uploadedAt: document.created_at,
    updatedAt: document.updated_at,
    fileType: document.file_type,
    filename: document.filename,
    originalFilename: document.original_filename,
  };
}


/*
 * Fetch documents belonging ONLY to the currently authenticated user.
 */
export async function getKnowledgeBaseDocuments() {
  if (useMock) {
    return [...mockDocuments];
  }

  const response = await fetch(
    `${API_BASE_URL}/knowledge-base/documents`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    },
  );

  const data = await parseResponse(response);
  const documents = Array.isArray(data)
    ? data
    : (Array.isArray(data?.documents) ? data.documents : []);

  return documents
    .map(normalizeKnowledgeBaseDocument)
    .filter(Boolean);
}


/*
 * Backward-compatible alias used by the existing UploadPage.
 */
export async function getDocuments() {
  return getKnowledgeBaseDocuments();
}


/*
 * Upload a document to the user's private Knowledge Base.
 *
 * The backend returns HTTP 202 with document_id and then processes
 * extraction/chunking/embedding in the background.
 */
export async function uploadKnowledgeBaseDocument(
  file,
  onProgress = () => {},
) {
  if (useMock) {
    onProgress(100);

    const doc = {
      id: crypto.randomUUID(),
      name: file.name,
      size: file.size,
      status: 'indexed',
      stage: 'completed',
      progress: 100,
      message: 'Document processed successfully.',
      uploadedAt: new Date().toISOString(),
      chunksCount: 0,
      embeddingsCount: 0,
      vectorsStored: 0,
    };

    mockDocuments.unshift(doc);

    return {
      accepted: true,
      jobId: doc.id,
      documentId: doc.id,
      filename: file.name,
      message: doc.message,
    };
  }

  const formData = new FormData();
  formData.append('file', file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.open(
      'POST',
      `${API_BASE_URL}/knowledge-base/documents`,
    );

    const token = getAuthToken();

    if (token) {
      xhr.setRequestHeader(
        'Authorization',
        `Bearer ${token}`,
      );
    }

    xhr.setRequestHeader(
      'Accept',
      'application/json',
    );

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round(
          (event.loaded / event.total) * 100,
        );

        onProgress(percent);
      }
    };

    xhr.onload = () => {
      let data = {};

      try {
        data = JSON.parse(xhr.responseText || '{}');
      } catch {
        const error = new Error(
          'The backend returned an invalid response.',
        );
        error.status = xhr.status;
        reject(error);
        return;
      }

      if (
        xhr.status >= 200 &&
        xhr.status < 300 &&
        data.status === 'accepted' &&
        data.document_id
      ) {
        onProgress(100);

        resolve({
          accepted: true,
          jobId: data.document_id,
          documentId: data.document_id,
          filename: file.name,
          message: data.message,
          status: data.status,
        });

        return;
      }

      const message =
        data.message ||
        data.detail ||
        `Upload failed (${xhr.status})`;

      const error = new Error(message);
      error.status = xhr.status;
      error.data = data;
      reject(error);
    };

    xhr.onerror = () => {
      reject(
        new Error(
          'Could not connect to the FastAPI backend.',
        ),
      );
    };

    xhr.onabort = () => {
      reject(
        new Error(
          'The upload was cancelled.',
        ),
      );
    };

    xhr.send(formData);
  });
}


/*
 * Backward-compatible alias used by the existing FileUploader.
 */
export async function uploadDocument(
  file,
  onProgress = () => {},
) {
  return uploadKnowledgeBaseDocument(file, onProgress);
}


/*
 * Check processing status for a Knowledge Base document.
 *
 * The new backend does not expose /upload/status/{jobId}; instead the
 * document itself exposes its current status through GET /knowledge-base.
 */
export async function getKnowledgeBaseDocument(documentId) {
  if (!documentId) {
    throw new Error('documentId is required.');
  }

  if (useMock) {
    const document = mockDocuments.find(
      (item) => item.id === documentId,
    );

    return document || null;
  }

  const response = await fetch(
    `${API_BASE_URL}/knowledge-base/documents/${encodeURIComponent(documentId)}`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    },
  );

  const data = await parseResponse(response);
  return normalizeKnowledgeBaseDocument(data);
}


/*
 * Backward-compatible status shape for the existing FileUploader.
 */
export async function getUploadStatus(jobId) {
  const document = await getKnowledgeBaseDocument(jobId);

  if (!document) {
    return {
      jobId,
      documentId: jobId,
      filename: '',
      status: 'failed',
      stage: 'completed',
      progress: 100,
      message: 'Document not found.',
      error: 'Document not found.',
    };
  }

  const completed = document.status === 'indexed';
  const failed = document.status === 'failed';

  /*
   * The current Knowledge Base backend exposes only:
   *   processing / completed / failed
   *
   * FileUploader.jsx, however, expects one of:
   *   uploaded / extracting / chunking / embedding / storing / completed
   *
   * While processing, use "extracting" as the active stage so the
   * existing FileUploader stage UI continues to work.
   */
  return {
    jobId: document.id,
    documentId: document.id,
    filename: document.name,

    status: completed
      ? 'completed'
      : failed
        ? 'failed'
        : 'processing',

    stage: completed
      ? 'completed'
      : failed
        ? 'completed'
        : 'extracting',

    progress: completed || failed ? 100 : 50,

    message: document.message,

    error: failed
      ? document.message
      : null,
  };
}

/*
 * Backward-compatible alias used by the existing UploadPage.
 */
export async function deleteDocument(id) {
  return deleteKnowledgeBaseDocument(id);
}


/*
 * Standalone semantic search against the authenticated user's private KB.
 */
export async function searchKnowledgeBase(
  query,
  k = 3,
) {
  if (!query || !query.trim()) {
    throw new Error('Knowledge Base search query cannot be empty.');
  }

  const response = await fetch(
    `${API_BASE_URL}/knowledge-base/search`,
    {
      method: 'POST',
      headers: getAuthHeaders(true),
      body: JSON.stringify({
        query: query.trim(),
        k,
      }),
    },
  );

  return parseResponse(response);
}


/* ------------------------------------------------------------------ */
/* Conversation APIs                                                   */
/* ------------------------------------------------------------------ */


/*
 * Create a new persistent conversation.
 *
 * IMPORTANT:
 * The backend now generates the conversation UUID.
 * The frontend does not send a conversation_id.
 */
export async function createConversation() {
  if (useMock) {
    return {
      success: true,
      conversation_id: crypto.randomUUID(),
    };
  }

  const response = await fetch(
    `${API_BASE_URL}/conversations`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
    },
  );

  return parseResponse(response);
}


/*
 * Fetch all conversations belonging to the logged-in user.
 */
export async function getConversations() {
  if (useMock) {
    return {
      success: true,
      count: 0,
      conversations: [],
    };
  }

  const response = await fetch(
    `${API_BASE_URL}/conversations`,
    {
      headers: getAuthHeaders(),
    },
  );

  return parseResponse(response);
}


/*
 * Fetch one conversation with its messages.
 */
export async function getConversation(
  conversationId,
) {
  if (!conversationId) {
    throw new Error(
      'conversationId is required.',
    );
  }

  if (useMock) {
    return {
      success: true,
      conversation_id: conversationId,
      messages: [],
    };
  }

  const response = await fetch(
    `${API_BASE_URL}/conversations/${encodeURIComponent(
      conversationId,
    )}`,
    {
      headers: getAuthHeaders(),
    },
  );

  return parseResponse(response);
}


/*
 * Fetch structured memory context for a conversation.
 */
export async function getConversationContext(
  conversationId,
) {
  if (!conversationId) {
    throw new Error(
      'conversationId is required.',
    );
  }

  if (useMock) {
    return {
      success: true,
      conversation_id: conversationId,
      context: [],
    };
  }

  const response = await fetch(
    `${API_BASE_URL}/conversations/${encodeURIComponent(
      conversationId,
    )}/context`,
    {
      headers: getAuthHeaders(),
    },
  );

  return parseResponse(response);
}


/*
 * Delete a saved conversation.
 */
export async function deleteConversation(
  conversationId,
) {
  if (!conversationId) {
    throw new Error(
      'conversationId is required.',
    );
  }

  if (useMock) {
    return {
      success: true,
      conversation_id: conversationId,
      message: 'Conversation deleted successfully.',
    };
  }

  const response = await fetch(
    `${API_BASE_URL}/conversations/${encodeURIComponent(
      conversationId,
    )}`,
    {
      method: 'DELETE',
      headers: getAuthHeaders(),
    },
  );

  return parseResponse(response);
}


/*
 * Save a conversation turn manually.
 */
export async function saveConversationTurn(
  conversationId,
  userQuery,
  aiResponse = null,
) {
  if (!conversationId) {
    throw new Error(
      'conversationId is required.',
    );
  }

  const response = await fetch(
    `${API_BASE_URL}/conversations/${encodeURIComponent(
      conversationId,
    )}/turns`,
    {
      method: 'POST',
      headers: getAuthHeaders(true),
      body: JSON.stringify({
        user_query: userQuery,
        ai_response: aiResponse,
      }),
    },
  );

  return parseResponse(response);
}


/* ------------------------------------------------------------------ */
/* RAG / Milestone 3 Query API                                        */
/* ------------------------------------------------------------------ */


/*
 * Send a text or voice-transcribed query.
 *
 * conversationId enables persistent memory.
 * clarification fields continue a clarification flow.
 */
export async function sendChatMessage(
  message,
  _history = [],
  conversationId = null,
  clarificationAnswer = null,
  clarificationQuestion = null,
  originalQuery = null,
) {
  if (!message || !message.trim()) {
    throw new Error('Message cannot be empty.');
  }

  if (useMock) {
    return {
      success: true,
      query: message,
      conversation_id: conversationId || null,
      query_understanding: null,
      route: 'retrieval',
      route_reason: 'Mock response',
      clarification_required: false,
      clarification_question: null,
      retrieval: {
        results: [],
        retrieval: {
          semantic_candidates: 0,
          exact_candidates: 0,
          merged_candidates: 0,
          returned_results: 0,
          completeness_query: false,
        },
      },
      response: {
        answer:
          'Mock mode is enabled. Connect the FastAPI backend to retrieve real document context.',
        sources: [],
        confidence: 0,
      },
    };
  }

  const requestBody = {
    query: message,
    k: 3,
  };

  if (conversationId) {
    requestBody.conversation_id = conversationId;
  }

  if (clarificationAnswer) {
    requestBody.clarification_answer =
      clarificationAnswer;
  }

  if (clarificationQuestion) {
    requestBody.clarification_question =
      clarificationQuestion;
  }

  if (originalQuery) {
    requestBody.original_query =
      originalQuery;
  }

  const response = await fetch(
    `${API_BASE_URL}/query`,
    {
      method: 'POST',
      headers: getAuthHeaders(true),
      body: JSON.stringify(requestBody),
    },
  );

  const data = await parseResponse(response);

  if (!data.success) {
    throw new Error(
      data.detail ||
      data.message ||
      'Query failed.',
    );
  }

  return data;
}
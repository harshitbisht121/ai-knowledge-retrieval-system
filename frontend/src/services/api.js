const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '');

let useMock = false;

const mockDocuments = [];

export const setMockMode = (enable) => {
  useMock = enable;
};

export const getMockMode = () => useMock;


async function parseResponse(response) {
  let data = {};

  try {
    data = await response.json();
  } catch {
    // Keep an empty object when the response has no JSON body.
  }

  if (!response.ok) {
    throw new Error(
      data.detail ||
      data.message ||
      `Request failed (${response.status})`
    );
  }

  return data;
}


// Fetch indexed documents.
export async function getDocuments() {
  if (useMock) {
    return [...mockDocuments];
  }

  const response = await fetch(
    `${API_BASE_URL}/documents`
  );

  const data = await parseResponse(response);

  return Array.isArray(data)
    ? data
    : (data.documents || []);
}


// Upload and index a document.
export async function uploadDocument(
  file,
  onProgress = () => {}
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
    };
  }

  const formData = new FormData();

  formData.append('file', file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.open(
      'POST',
      `${API_BASE_URL}/upload`
    );

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round(
          (event.loaded / event.total) * 100
        );

        onProgress(percent);
      }
    };

    xhr.onload = () => {
      let data = {};

      try {
        data = JSON.parse(
          xhr.responseText
        );
      } catch {
        reject(
          new Error(
            'The backend returned an invalid response.'
          )
        );

        return;
      }

      if (
        xhr.status >= 200 &&
        xhr.status < 300 &&
        data.status === 'accepted' &&
        data.jobId
      ) {
        onProgress(100);

        resolve({
          accepted: true,
          jobId: data.jobId,
          documentId: data.documentId,
          filename:
            data.filename || file.name,
          message: data.message,
        });

        return;
      }

      reject(
        new Error(
          data.message ||
          data.detail ||
          `Upload failed (${xhr.status})`
        )
      );
    };

    xhr.onerror = () => {
      reject(
        new Error(
          'Could not connect to the FastAPI backend.'
        )
      );
    };

    xhr.onabort = () => {
      reject(
        new Error(
          'The upload was cancelled.'
        )
      );
    };

    xhr.send(formData);
  });
}


// Check upload/indexing status.
export async function getUploadStatus(jobId) {
  if (useMock) {
    return {
      jobId,
      documentId: jobId,
      filename: 'Mock document',
      status: 'completed',
      stage: 'completed',
      progress: 100,
      message:
        'Document processed successfully.',
      chunksCount: 0,
      embeddingsCount: 0,
      vectorsStored: 0,
      error: null,
    };
  }

  const response = await fetch(
    `${API_BASE_URL}/upload/status/${encodeURIComponent(jobId)}`
  );

  return parseResponse(response);
}


// Delete an indexed document.
export async function deleteDocument(id) {
  if (useMock) {
    const index = mockDocuments.findIndex(
      (doc) => doc.id === id
    );

    if (index >= 0) {
      mockDocuments.splice(index, 1);
    }

    return {
      status: 'success',
    };
  }

  const response = await fetch(
    `${API_BASE_URL}/documents/${encodeURIComponent(id)}`,
    {
      method: 'DELETE',
    }
  );

  return parseResponse(response);
}


/*
 * Conversation APIs
 */

// Create a new persistent conversation.
export async function createConversation(
  conversationId = null
) {
  if (useMock) {
    return {
      success: true,
      conversation_id:
        conversationId || crypto.randomUUID(),
    };
  }

  const body = conversationId
    ? { conversation_id: conversationId }
    : {};

  const response = await fetch(
    `${API_BASE_URL}/conversations`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    }
  );

  return parseResponse(response);
}


// Fetch all saved conversations.
export async function getConversations() {
  if (useMock) {
    return {
      success: true,
      count: 0,
      conversations: [],
    };
  }

  const response = await fetch(
    `${API_BASE_URL}/conversations`
  );

  return parseResponse(response);
}


// Fetch one conversation with all messages.
export async function getConversation(
  conversationId
) {
  if (!conversationId) {
    throw new Error(
      'conversationId is required.'
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
      conversationId
    )}`
  );

  return parseResponse(response);
}


// Fetch memory context for a conversation.
export async function getConversationContext(
  conversationId
) {
  if (!conversationId) {
    throw new Error(
      'conversationId is required.'
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
      conversationId
    )}/context`
  );

  return parseResponse(response);
}


// Delete a saved conversation.
export async function deleteConversation(
  conversationId
) {
  if (!conversationId) {
    throw new Error(
      'conversationId is required.'
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
      conversationId
    )}`,
    {
      method: 'DELETE',
    }
  );

  return parseResponse(response);
}


/*
 * RAG query API
 */

// Send a text or voice-transcribed query through the M3 workflow.
//
// conversationId enables persistent conversation memory.
// clarification fields allow continuation after a clarification question.
export async function sendChatMessage(
  message,
  _history = [],
  conversationId = null,
  clarificationAnswer = null,
  clarificationQuestion = null,
  originalQuery = null
) {
  if (useMock) {
    return {
      success: true,
      query: message,
      conversation_id:
        conversationId || null,
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

  // Attach the conversation when available.
  if (conversationId) {
    requestBody.conversation_id =
      conversationId;
  }

  // Attach clarification data only when continuing a clarification flow.
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
      headers: {
        'Content-Type':
          'application/json',
        'Accept':
          'application/json',
      },
      body: JSON.stringify(
        requestBody
      ),
    }
  );

  const data =
    await parseResponse(response);

  if (!data.success) {
    throw new Error(
      data.detail ||
      data.message ||
      'Query failed.'
    );
  }

  return data;
}
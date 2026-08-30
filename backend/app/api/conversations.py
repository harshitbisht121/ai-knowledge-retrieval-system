"""
Conversation Memory API.

Provides FastAPI endpoints for:
- Creating conversations
- Listing conversations
- Reading conversation history
- Adding conversation turns
- Deleting conversations

This router delegates storage to the Conversation Memory layer.
It does not contain database business logic.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.memory.agent import ConversationMemoryAgent
from app.core.database import SessionLocal
from app.core.models import Conversation, ConversationMessage


router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)

memory_agent = ConversationMemoryAgent()


# ---------------------------------------------------------------------
# Database dependency
# ---------------------------------------------------------------------

def get_db():
    """
    Create and safely close a SQLAlchemy database session.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# ---------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------

class ConversationCreateRequest(BaseModel):
    """
    Request body for creating a conversation.

    conversation_id is optional. If omitted, the backend generates one.
    """

    conversation_id: str | None = Field(
        default=None,
        min_length=1,
    )


class ConversationTurnRequest(BaseModel):
    """
    Request body for adding a conversation turn.
    """

    user_query: str = Field(
        min_length=1,
    )

    ai_response: str | None = None


# ---------------------------------------------------------------------
# POST /conversations
# ---------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    request: ConversationCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new conversation.
    """

    conversation_id = (
        request.conversation_id
        or str(uuid4())
    )

    existing = db.get(
        Conversation,
        conversation_id,
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation already exists.",
        )

    conversation = Conversation(
        id=conversation_id,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return {
        "success": True,
        "conversation_id": conversation.id,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


# ---------------------------------------------------------------------
# GET /conversations
# ---------------------------------------------------------------------

@router.get("")
def list_conversations(
    db: Session = Depends(get_db),
):
    """
    Return all conversations.

    This is useful for the ChatGPT-like frontend sidebar.
    """

    conversations = (
        db.query(Conversation)
        .order_by(
            Conversation.updated_at.desc()
        )
        .all()
    )

    return {
        "success": True,
        "count": len(conversations),
        "conversations": [
            {
                "conversation_id": conversation.id,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
            }
            for conversation in conversations
        ],
    }


# ---------------------------------------------------------------------
# GET /conversations/{conversation_id}
# ---------------------------------------------------------------------

@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Return a conversation and its message history.
    """

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    messages = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id
            == conversation_id
        )
        .order_by(
            ConversationMessage.created_at.asc()
        )
        .all()
    )

    return {
        "success": True,
        "conversation_id": conversation.id,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
            }
            for message in messages
        ],
    }


# ---------------------------------------------------------------------
# GET /conversations/{conversation_id}/context
# ---------------------------------------------------------------------

@router.get("/{conversation_id}/context")
def get_conversation_context(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Return conversation history in the format expected
    by the Memory Agent / orchestration layer.
    """

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    context = memory_agent.get_context(
        db,
        conversation_id,
    )

    return {
        "success": True,
        "conversation_id": conversation_id,
        "context": context,
    }


# ---------------------------------------------------------------------
# POST /conversations/{conversation_id}/turns
# ---------------------------------------------------------------------

@router.post(
    "/{conversation_id}/turns",
    status_code=status.HTTP_201_CREATED,
)
def save_conversation_turn(
    conversation_id: str,
    request: ConversationTurnRequest,
    db: Session = Depends(get_db),
):
    """
    Save one user query and optional AI response
    using the Conversation Memory Agent.
    """

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    try:

        memory_agent.store_turn(
            db=db,
            conversation_id=conversation_id,
            user_query=request.user_query,
            ai_response=request.ai_response,
        )

        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "Conversation turn saved successfully.",
        }

    except Exception as error:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save conversation turn: {error}",
        ) from error


# ---------------------------------------------------------------------
# DELETE /conversations/{conversation_id}
# ---------------------------------------------------------------------

@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete a conversation and all related messages.
    """

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    try:

        db.delete(conversation)
        db.commit()

        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "Conversation deleted successfully.",
        }

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {error}",
        ) from error
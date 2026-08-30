from sqlalchemy.orm import Session

from app.core.models import Conversation, ConversationMessage
from .schemas import ConversationTurn


def save_turn(db: Session, turn: ConversationTurn):
    # Create the conversation if it doesn't exist
    conversation = db.get(Conversation, turn.conversation_id)

    if conversation is None:
        conversation = Conversation(
            id=turn.conversation_id
        )
        db.add(conversation)
        db.flush()

    # Store the user message
    user_message = ConversationMessage(
        conversation_id=turn.conversation_id,
        role="user",
        content=turn.user_query
    )
    db.add(user_message)

    # Store the AI response if available
    if turn.ai_response:
        assistant_message = ConversationMessage(
            conversation_id=turn.conversation_id,
            role="assistant",
            content=turn.ai_response
        )
        db.add(assistant_message)

    db.commit()


def get_history(db: Session, conversation_id: str):
    messages = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == conversation_id
        )
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )

    return messages
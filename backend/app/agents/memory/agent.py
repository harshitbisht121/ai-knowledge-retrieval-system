from sqlalchemy.orm import Session

from .storage import get_history, save_turn
from .schemas import ConversationTurn


class ConversationMemoryAgent:

    def store_turn(
        self,
        db: Session,
        conversation_id: str,
        user_query: str,
        ai_response: str | None = None
    ):
        turn = ConversationTurn(
            conversation_id=conversation_id,
            user_query=user_query,
            ai_response=str(ai_response) if ai_response is not None else None
        )

        save_turn(db, turn)

    def get_context(
        self,
        db: Session,
        conversation_id: str
    ):
        messages = get_history(db, conversation_id)

        context = []
        current_user_message = None

        for message in messages:
            if message.role == "user":
                current_user_message = message.content

            elif message.role == "assistant":
                context.append({
                    "user": current_user_message,
                    "assistant": message.content
                })
                current_user_message = None

        # Handle a user message that doesn't have an AI response yet
        if current_user_message is not None:
            context.append({
                "user": current_user_message,
                "assistant": None
            })

        return context
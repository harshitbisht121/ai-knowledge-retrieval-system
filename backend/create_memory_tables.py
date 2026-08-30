from app.core.database import Base, engine
from app.core.models import Conversation, ConversationMessage


def main() -> None:
    print("Creating conversation tables...")

    Base.metadata.create_all(bind=engine)

    print("Conversation tables created successfully.")


if __name__ == "__main__":
    main()
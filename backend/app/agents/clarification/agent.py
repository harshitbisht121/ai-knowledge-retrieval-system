from langchain_core.prompts import ChatPromptTemplate

from app.core.llm import get_llm

from .detector import ClarificationDetector
from .prompts import (
    CLARIFICATION_QUESTION_PROMPT,
    QUERY_REFINEMENT_PROMPT,
)
from .schemas import (
    ClarificationRequest,
    ClarificationResult,
    QueryRefinementRequest,
    RefinedQueryResult,
)


class ClarificationAgent:
    """
    Clarification Agent for Milestone 3.

    Responsibilities:
    - Determine whether clarification is required.
    - Generate a clarification question.
    - Refine a query using the user's clarification.

    The agent does not own conversation memory.
    Conversation context is handled by the Conversation Memory Agent.
    """

    def __init__(self, llm=None):
        self.llm = llm or get_llm()
        self.detector = ClarificationDetector(self.llm)

    def check_query(
        self,
        request: ClarificationRequest,
    ) -> ClarificationResult:

        needs_clarification = (
            self.detector.needs_clarification(
                query=request.query,
                query_type=request.query_type,
            )
        )

        if not needs_clarification:
            return ClarificationResult(
                needs_clarification=False,
                refined_query=request.query,
            )

        question = self.generate_question(
            request.query
        )

        return ClarificationResult(
            needs_clarification=True,
            clarification_question=question,
        )

    def generate_question(
        self,
        query: str,
    ) -> str:

        prompt = ChatPromptTemplate.from_template(
            CLARIFICATION_QUESTION_PROMPT
        )

        messages = prompt.format_messages(
            query=query
        )

        response = self.llm.invoke(messages)

        question = getattr(
            response,
            "content",
            str(response),
        ).strip()

        return question

    def refine_query(
        self,
        request: QueryRefinementRequest,
    ) -> RefinedQueryResult:

        if not request.user_response.strip():
            raise ValueError(
                "Clarification response cannot be empty."
            )

        prompt = ChatPromptTemplate.from_template(
            QUERY_REFINEMENT_PROMPT
        )

        messages = prompt.format_messages(
            original_query=request.original_query,
            clarification_question=(
                request.clarification_question
            ),
            user_response=request.user_response,
        )

        response = self.llm.invoke(messages)

        refined_query = getattr(
            response,
            "content",
            str(response),
        ).strip()

        return RefinedQueryResult(
            conversation_id=request.conversation_id,
            original_query=request.original_query,
            clarification_question=(
                request.clarification_question
            ),
            user_response=request.user_response,
            refined_query=refined_query,
        )

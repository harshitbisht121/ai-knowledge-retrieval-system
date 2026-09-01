"""
LangGraph orchestration nodes.

Milestone 2:
    - Query Understanding
    - Routing
    - Retrieval
    - Response Generation

Milestone 3:
    - Load Conversation Memory
    - Context-aware follow-up query resolution
    - Clarification
    - Save Conversation Memory

Important:
    Agent business logic remains inside app/agents/.
    This module coordinates the agents and updates workflow state.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.query_understanding.agent import (
    QueryUnderstandingAgent,
)
from app.agents.query_understanding.schemas import (
    QueryUnderstandingResult,
)

from app.agents.retrieval.agent import (
    RetrievalAgent,
)

from app.agents.response_generation.agent import (
    generate_response,
)

from app.agents.clarification.agent import (
    ClarificationAgent,
)
from app.agents.clarification.schemas import (
    QueryRefinementRequest,
)

from app.agents.memory.agent import (
    ConversationMemoryAgent,
)

from app.core.llm import get_llm

from app.orchestration.query_router import (
    get_route_reason,
    route_query,
)

from app.orchestration.state import WorkflowState


# =====================================================================
# Shared agent instances
# =====================================================================

_llm = get_llm()

_query_understanding_agent = QueryUnderstandingAgent(
    _llm
)

_retrieval_agent = RetrievalAgent(
    default_k=3,
    semantic_candidate_multiplier=5,
    relevance_threshold=0.30,
    enable_diversification=True,
)

_clarification_agent = ClarificationAgent(
    _llm
)

_memory_agent = ConversationMemoryAgent()


# =====================================================================
# Internal helpers
# =====================================================================

def _get_db(
    state: WorkflowState,
) -> Session:
    """
    Get the SQLAlchemy session attached to the workflow state.
    """

    db = state.get("_db")

    if db is None:
        raise RuntimeError(
            "Database session is missing from workflow state."
        )

    return db


def _has_error(
    state: WorkflowState,
) -> bool:
    """Return True when a previous node has failed."""

    return bool(
        state.get("error")
    )


def _memory_has_context(
    state: WorkflowState,
) -> bool:
    """
    Return True when useful conversation context exists.
    """

    context = state.get(
        "memory_context",
        [],
    )

    return bool(context)


# =====================================================================
# Milestone 3 - Contextual Follow-up Resolution
# =====================================================================

def _resolve_contextual_query(
    query: str,
    memory_context: list[dict[str, Any]],
) -> str:
    """
    Convert a context-dependent follow-up query into a
    standalone query using recent conversation history.

    Example:

        Previous:
            User: What does the Retrieval Agent do?
            Assistant: It performs semantic search...

        Current:
            What about its ranking?

        Possible result:
            What is the ranking performed by the Retrieval Agent?

    If no conversation context exists, the original query is returned.
    """

    if not query.strip():
        return query

    if not memory_context:
        return query

    # Use the most recent few conversation turns.
    recent_context = memory_context[-3:]

    conversation_lines: list[str] = []

    for turn in recent_context:

        if not isinstance(
            turn,
            dict,
        ):
            continue

        user_message = turn.get(
            "user"
        )

        assistant_message = turn.get(
            "assistant"
        )

        if user_message:
            conversation_lines.append(
                f"User: {user_message}"
            )

        if assistant_message:
            conversation_lines.append(
                f"Assistant: {assistant_message}"
            )

    if not conversation_lines:
        return query

    conversation_text = "\n".join(
        conversation_lines
    )

    prompt = f"""
You are a query reformulation component in a RAG system.

Rewrite the current user query into a standalone search query
that can be understood without the previous conversation.

Use the previous conversation only to resolve references such as:
- it
- its
- this
- that
- they
- them
- the above
- the previous answer
- follow-up references

Do not answer the question.
Do not add information that is not supported by the conversation.
Keep the user's actual intent unchanged.

Previous conversation:
{conversation_text}

Current user query:
{query}

Return ONLY the standalone query.
"""

    try:
        response = _llm.invoke(
            prompt
        )

        standalone_query = getattr(
            response,
            "content",
            "",
        )

        if isinstance(
            standalone_query,
            list,
        ):
            standalone_query = " ".join(
                str(item)
                for item in standalone_query
            )

        if not isinstance(
            standalone_query,
            str,
        ):
            return query

        standalone_query = standalone_query.strip()

        if not standalone_query:
            return query

        return standalone_query

    except Exception:
        # Memory must never make a normal query fail.
        # Fall back to the original user query.
        return query


# =====================================================================
# Milestone 3 - Memory Node
# =====================================================================

def memory_node(
    state: WorkflowState,
) -> WorkflowState:
    """
    Load previous conversation context.

    No conversation_id:
        continue exactly like Milestone 2.

    Existing conversation_id:
        retrieve persisted context from the database.
    """

    if _has_error(state):
        return state

    conversation_id = state.get(
        "conversation_id"
    )

    # Preserve M2 behavior when memory is not requested.
    if not conversation_id:
        return {
            **state,
            "memory_context": [],
        }

    try:
        db = _get_db(
            state
        )

        context = _memory_agent.get_context(
            db=db,
            conversation_id=conversation_id,
        )

        return {
            **state,
            "memory_context": context,
        }

    except Exception as error:
        return {
            **state,
            "error": (
                f"Conversation Memory load failed: {error}"
            ),
        }


# =====================================================================
# Milestone 2 - Query Understanding Node
# =====================================================================

def query_understanding_node(
    state: WorkflowState,
) -> WorkflowState:
    """
    Run Query Understanding.

    For a normal M2 query:
        query -> Query Understanding

    For a context-dependent M3 follow-up:
        memory + query
            -> standalone query
            -> Query Understanding
    """

    try:
        query = state.get(
            "query",
            "",
        ).strip()

        if not query:
            raise ValueError(
                "Query cannot be empty."
            )

        # Resolve conversation context only for a normal query.
        # A clarification-refined query is already standalone and
        # must not be rewritten by memory a second time.

        memory_context = state.get(
            "memory_context",
            [],
        )

        if state.get("refined_query"):
            resolved_query = query
        else:
            resolved_query = _resolve_contextual_query(
                query=query,
                memory_context=memory_context,
            )

        # Keep the resolved query in the workflow state.
        result: WorkflowState = {
            **state,
            "query": resolved_query,
        }

        # -------------------------------------------------------------
        # Existing Query Understanding Agent remains unchanged.
        # -------------------------------------------------------------

        analysis = _query_understanding_agent.run(
            resolved_query
        )

        return {
            **result,
            "query_analysis": analysis,
        }

    except Exception as error:
        return {
            **state,
            "error": (
                f"Query Understanding failed: {error}"
            ),
        }


# =====================================================================
# Milestone 2 - Routing Node
# =====================================================================

def routing_node(
    state: WorkflowState,
) -> WorkflowState:
    """
    Run the deterministic query router.

    Clear queries:
        -> retrieval

    Ambiguous queries:
        -> clarification
    """

    if _has_error(state):
        return state

    analysis = state.get(
        "query_analysis"
    )

    if not isinstance(
        analysis,
        QueryUnderstandingResult,
    ):
        return {
            **state,
            "error": (
                "Invalid QueryUnderstandingResult "
                "received by router."
            ),
        }

    try:
        route = route_query(
            analysis
        )

        reason = get_route_reason(
            analysis
        )

        return {
            **state,
            "route": route,
            "route_reason": reason,
        }

    except Exception as error:
        return {
            **state,
            "error": (
                f"Query routing failed: {error}"
            ),
        }


# =====================================================================
# Milestone 3 - Clarification Node
# =====================================================================

def clarification_node(
    state: WorkflowState,
) -> WorkflowState:
    """
    Generate a clarification question or refine a query.

    First pass:
        ambiguous query
            -> clarification question

    Second pass:
        clarification answer
            -> refined query
    """

    if _has_error(state):
        return state

    clarification_answer = state.get(
        "clarification_answer",
        "",
    ).strip()

    original_query = state.get(
        "original_query",
        "",
    ).strip()

    clarification_question = state.get(
        "clarification_question",
        "",
    ).strip()

    # ================================================================
    # Case 1 - User answered clarification
    # ================================================================

    if clarification_answer:

        if not original_query:
            return {
                **state,
                "error": (
                    "Original query is required "
                    "for clarification refinement."
                ),
            }

        if not clarification_question:
            return {
                **state,
                "error": (
                    "Clarification question is required "
                    "for clarification refinement."
                ),
            }

        try:
            request = QueryRefinementRequest(
                conversation_id=state.get(
                    "conversation_id",
                    "",
                ),
                original_query=original_query,
                clarification_question=(
                    clarification_question
                ),
                user_response=clarification_answer,
            )

            result = (
                _clarification_agent.refine_query(
                    request
                )
            )

            refined_query = (
                result.refined_query.strip()
            )

            if not refined_query:
                raise ValueError(
                    "Clarification Agent returned "
                    "an empty refined query."
                )

            return {
                **state,
                "query": refined_query,
                "refined_query": refined_query,
                "clarification_required": False,
                "clarification_answer": "",
            }

        except Exception as error:
            return {
                **state,
                "error": (
                    f"Query Refinement failed: {error}"
                ),
            }

    # ================================================================
    # Case 2 - Generate clarification question
    # ================================================================

    query = state.get(
        "query",
        "",
    ).strip()

    if not query:
        return {
            **state,
            "error": (
                "Cannot generate clarification "
                "for an empty query."
            ),
        }

    try:

        question = (
            _clarification_agent
            .generate_question(query)
        )

        if (
            not question
            or not question.strip()
        ):
            raise ValueError(
                "Clarification Agent returned "
                "an empty clarification question."
            )

        return {
            **state,
            "clarification_required": True,
            "clarification_question": (
                question.strip()
            ),
            "original_query": query,
        }

    except Exception as error:
        return {
            **state,
            "error": (
                f"Clarification Generation failed: {error}"
            ),
        }


# =====================================================================
# Milestone 2 - Retrieval Node
# =====================================================================

def retrieval_node(
    state: WorkflowState,
) -> WorkflowState:
    """
    Run the existing Retrieval Agent.

    The Retrieval Agent itself is unchanged.
    """

    if _has_error(state):
        return state

    analysis = state.get(
        "query_analysis"
    )

    if not isinstance(
        analysis,
        QueryUnderstandingResult,
    ):
        return {
            **state,
            "error": (
                "Retrieval requires a valid "
                "QueryUnderstandingResult."
            ),
        }

    try:
        k = state.get(
            "k",
            3,
        )

        retrieval_result = (
            _retrieval_agent.run(
                analysis,
                k=k,
            )
        )

        return {
            **state,
            "retrieval_result": retrieval_result,
        }

    except Exception as error:
        return {
            **state,
            "error": (
                f"Retrieval failed: {error}"
            ),
        }


# =====================================================================
# Milestone 2 - Response Generation Node
# =====================================================================

def response_generation_node(
    state: WorkflowState,
) -> WorkflowState:
    """
    Generate grounded response from retrieved chunks.
    """

    if _has_error(state):
        return state

    query = state.get(
        "query",
        "",
    ).strip()

    retrieval_result = state.get(
        "retrieval_result",
        {},
    )

    chunks = retrieval_result.get(
        "results",
        [],
    )

    try:
        response = generate_response(
            question=query,
            chunks=chunks,
        )

        return {
            **state,
            "response": response.model_dump(),
        }

    except Exception as error:
        return {
            **state,
            "error": (
                f"Response Generation failed: {error}"
            ),
        }


# =====================================================================
# Milestone 3 - Save Memory Node
# =====================================================================

def save_memory_node(
    state: WorkflowState,
) -> WorkflowState:
    """
    Save the completed user/assistant exchange.
    """

    if _has_error(state):
        return state

    conversation_id = state.get(
        "conversation_id"
    )

    # Preserve M2 behavior when no conversation is being used.
    if not conversation_id:
        return state

    response = state.get(
        "response",
        {},
    )

    if not response:
        return state

    query = state.get(
        "query",
        "",
    ).strip()

    answer = response.get(
        "answer"
    )

    if not query:
        return {
            **state,
            "error": (
                "Cannot save memory because query is empty."
            ),
        }

    if not answer:
        return {
            **state,
            "error": (
                "Cannot save memory because response "
                "answer is empty."
            ),
        }

    try:
        db = _get_db(
            state
        )

        _memory_agent.store_turn(
            db=db,
            conversation_id=conversation_id,
            user_query=query,
            ai_response=answer,
        )

        return state

    except Exception as error:
        return {
            **state,
            "error": (
                f"Conversation Memory save failed: {error}"
            ),
        }
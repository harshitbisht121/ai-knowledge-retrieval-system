"""
Milestone 3 - Query API with Response Transparency.

Flow:

    FastAPI
        ↓
    Database Session
        ↓
    LangGraph Workflow
        ↓
    Conversation Memory
        ↓
    Query Understanding
        ↓
    Conditional Routing
        ├── Retrieval
        │     ↓
        │  Response Generation
        │
        └── Clarification
              ↓
          Refined Query
              ↓
           Retrieval
              ↓
       Response Generation
        ↓
    Save Conversation
        ↓
    Response Transparency
        ↓
    Final JSON Response
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.request_models import QueryRequest
from app.orchestration.workflow import run_workflow
from app.core.database import get_db
from app.transparency.service import build_transparency
from app.voice.output import prepare_speech_text


router = APIRouter(
    tags=["Query"],
)


@router.post(
    "/query",
    summary="Query Documents",
    description=(
        "Run the Milestone 2 + Milestone 3 LangGraph workflow "
        "with conversation memory, clarification, and response transparency."
    ),
)
def query_documents(
    request: QueryRequest,
    db: Session = Depends(get_db),
):
    """
    Execute the complete M3 query workflow.

    A request without conversation_id remains compatible with
    the earlier single-query workflow.

    A request with conversation_id enables conversation memory.

    Clarification fields are used when continuing a previous
    clarification interaction.
    """

    # Validate retrieval count.
    if request.k < 1:
        raise HTTPException(
            status_code=400,
            detail="k must be at least 1.",
        )

    try:
        # Execute the existing M3 LangGraph workflow.
        result = run_workflow(
            query=request.query,
            k=request.k,
            conversation_id=request.conversation_id,
            clarification_answer=(
                request.clarification_answer
            ),
            clarification_question=(
                request.clarification_question
            ),
            original_query=(
                request.original_query
            ),
            db=db,
        )

        # Return workflow-level failures as API errors.
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result["error"],
            )

        # Convert QueryUnderstandingResult into JSON-safe data.
        query_analysis = result.get(
            "query_analysis"
        )

        query_understanding = None

        if query_analysis is not None:
            query_understanding = (
                query_analysis.model_dump()
            )

        # Get clarification information.
        clarification_required = result.get(
            "clarification_required",
            False,
        )

        clarification_question = result.get(
            "clarification_question"
        )

        # Get retrieval and generated-response data.
        retrieval_result = result.get(
            "retrieval_result"
        )

        response_result = result.get(
            "response"
        )

        # Build the dedicated transparency object from retrieval data.
        transparency = build_transparency(
            retrieval_result
        )

        speech_text = (
            prepare_speech_text(
                response_result.get("answer", "")
            )
            if response_result
            else None
        )

        return {
            "success": True,

            # Preserve the original user query in the API response.
            "query": request.query,

            "conversation_id": result.get(
                "conversation_id"
            ),

            "query_understanding": (
                query_understanding
            ),

            "route": result.get(
                "route"
            ),

            "route_reason": result.get(
                "route_reason"
            ),

            "clarification_required": (
                clarification_required
            ),

            "clarification_question": (
                clarification_question
            ),

            "retrieval": retrieval_result,

            "response": response_result,

            "speech_text": speech_text,

            # Dedicated Response Transparency information.
            "transparency": transparency,
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Query processing failed: {error}"
            ),
        ) from error
"""
Milestone 3 - Query API.

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

The existing Milestone 2 response structure is preserved.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.request_models import QueryRequest
from app.orchestration.workflow import run_workflow
from app.core.database import get_db


router = APIRouter(
    tags=["Query"],
)


# ---------------------------------------------------------------------
# POST /query
# ---------------------------------------------------------------------

@router.post(
    "/query",
    summary="Query Documents",
    description=(
        "Run the Milestone 2 + Milestone 3 LangGraph workflow.\n\n"
        "Flow: "
        "FastAPI → Conversation Memory → Query Understanding → "
        "Conditional Routing → Retrieval / Clarification → "
        "Response Generation → Conversation Memory"
    ),
)
def query_documents(
    request: QueryRequest,
    db: Session = Depends(get_db),
):
    """
    Execute the complete M2 + M3 query workflow.

    Milestone 2 remains backward compatible.

    A request without conversation_id behaves like the existing
    single-query M2 workflow.

    A request with conversation_id enables conversation memory.

    Clarification fields are used when continuing a previous
    clarification interaction.
    """

    # -------------------------------------------------------------
    # Validate request
    # -------------------------------------------------------------

    if request.k < 1:
        raise HTTPException(
            status_code=400,
            detail="k must be at least 1.",
        )

    # -------------------------------------------------------------
    # Run workflow
    # -------------------------------------------------------------

    try:

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

        # ---------------------------------------------------------
        # Workflow-level errors
        # ---------------------------------------------------------

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result["error"],
            )

        # ---------------------------------------------------------
        # Query Understanding result
        # ---------------------------------------------------------

        query_analysis = result.get(
            "query_analysis"
        )

        query_understanding = None

        if query_analysis is not None:
            query_understanding = (
                query_analysis.model_dump()
            )

        # ---------------------------------------------------------
        # Clarification information
        # ---------------------------------------------------------

        clarification_required = result.get(
            "clarification_required",
            False,
        )

        clarification_question = result.get(
            "clarification_question"
        )

        # ---------------------------------------------------------
        # Final response
        # ---------------------------------------------------------

        return {
            "success": True,

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

            "retrieval": result.get(
                "retrieval_result"
            ),

            "response": result.get(
                "response"
            ),
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Query processing failed: {error}"
            ),
        ) from error
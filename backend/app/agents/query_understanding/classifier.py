from .schemas import QueryClassification
from langchain_core.language_models import BaseChatModel


def classify_query(
    llm: BaseChatModel,
    query: str,
) -> QueryClassification:
    """
    Classify a user query into exactly one supported query type.

    The classifier distinguishes between clear queries and queries
    that require clarification before retrieval.
    """

    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    # Use native JSON Schema structured output.
    structured_llm = llm.with_structured_output(
        QueryClassification,
        method="json_schema",
        strict=True,
    )

    prompt = f"""
You are the query classification component of a knowledge
retrieval and conversational question-answering system.

Classify the user's query into EXACTLY ONE of these four categories:

1. factual
   - The user asks for a clearly identifiable fact, definition,
     explanation, event, person, entity, or specific information.
   - The subject of the question is sufficiently clear.
   - Examples:
       "What does the Retrieval Agent do?"
       "When was the Tribunals Reforms Bill passed?"
       "What is Agentic AI?"

2. procedural
   - The user asks how to perform something, how something works
     as a process, or asks for steps/instructions.
   - The subject and requested action are sufficiently clear.
   - Examples:
       "How does the retrieval pipeline work?"
       "How do I upload a document?"

3. comparative
   - The user explicitly asks to compare two or more identifiable
     entities, concepts, events, options, or items.
   - The entities being compared must be sufficiently clear.
   - Examples:
       "What is the difference between semantic and exact search?"
       "Compare the Retrieval Agent and Clarification Agent."

4. ambiguous
   - The query is unclear, incomplete, underspecified, or does not
     provide enough information to determine exactly what the user
     is referring to.
   - Use ambiguous when a human would need to ask a follow-up
     question before giving a precise answer.
   - This includes unresolved references such as:
       "it", "its", "that", "this", "they", "them", "the above",
       "the previous one", etc., when their referent is not explicitly
       identifiable from the query itself.
   - This includes underspecified entities when multiple possible
     entities could match the query.
   - This includes generic references such as:
       "the bill"
       "the law"
       "the committee"
       "the regulations"
       "the new policy"
       when the query does not identify which one.
   - This includes questions such as:
       "What happened in August?"
       when no specific topic or domain is identified.
   - This includes questions such as:
       "How did it affect companies?"
       when "it" has no explicit referent in the query.
   - This includes questions such as:
       "What is its significance?"
       when "its" has no explicit referent.
   - This includes questions such as:
       "Tell me about the bill."
       when multiple bills could be relevant.
   - This includes questions asking about a missing subject:
       "Tell me more."
       "Explain further."
       "What happened after that?"
   - A query can be ambiguous even when the knowledge base contains
     a likely answer. Do NOT select one likely interpretation simply
     because it appears frequently in the knowledge base.

IMPORTANT RULES:

- Return exactly ONE category.
- Do not use "ambiguous" merely because a query is short.
- Use "ambiguous" when the missing information prevents a precise
  answer or when multiple plausible interpretations exist.
- Do not guess the user's intended subject.
- Do not use knowledge-base content to silently choose between
  multiple possible interpretations.
- If the query explicitly names a single clear subject, do NOT mark
  it ambiguous merely because other topics also exist in the
  knowledge base.
- If a previous conversational context has already been used to
  resolve a follow-up query into a standalone query, classify the
  resolved query based on that resolved wording.
- A clear query about a named entity remains factual even if it is
  short.
- A query containing an unresolved pronoun/reference is ambiguous
  unless the referenced subject is explicitly present in the query.
- A query containing multiple independent requests should not be
  treated as a simple factual query. If the request cannot be
  interpreted unambiguously, classify it as ambiguous.

Examples for the current knowledge-base style:

"Who won India's 600th Test?"
→ factual

"What does the Retrieval Agent do?"
→ factual

"How does semantic retrieval work?"
→ procedural

"Compare semantic search and exact search."
→ comparative

"What about the new law?"
→ ambiguous

"Tell me about the bill."
→ ambiguous

"How did it affect companies?"
→ ambiguous

"Explain the new regulations."
→ ambiguous

"What is its significance?"
→ ambiguous

"Tell me about the committee."
→ ambiguous

"How much was approved and why?"
→ ambiguous

"What happened after that?"
→ ambiguous

"What happened in August?"
→ ambiguous

"What happened to AI and what happened in Indian sports?"
→ ambiguous

User query:
{query}
"""

    return structured_llm.invoke(prompt)
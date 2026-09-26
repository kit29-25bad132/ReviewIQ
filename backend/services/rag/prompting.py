"""Context-aware prompt construction for review analysis (V2-P3).

Guarantees:
* No context (RAG disabled or zero retrieved reviews) -> the prompt and system
  instruction are byte-identical to the original V1/P2 prompt.
* With context -> the original review is preserved verbatim in its own labeled
  section, retrieved reviews appear in a separate clearly-labeled section, and
  the system instruction gains explicit context-handling rules (source
  attribution only; no chain-of-thought is ever requested or logged).
"""

from typing import Optional, Tuple

from services.rag.context_builder import RagContext, render_context_block

BASE_PROMPT = 'Analyze this customer product review:\n\n"""\n{text}\n"""'

ORIGINAL_REVIEW_HEADER = "Original customer review:"
CONTEXT_HEADER = (
    "Retrieved contextual reviews (background context from semantic search):"
)

CONTEXT_SYSTEM_RULES = """
RETRIEVED CONTEXT RULES (apply only when the prompt contains a "Retrieved contextual reviews" section):
1. The prompt has two sections: the "Original customer review" (the review you must analyze) and optional "Retrieved contextual reviews" (other similar reviews retrieved by semantic search, provided as background context).
2. The original customer review is the ONLY source of truth. Analyze only that review.
3. Every "evidence" string must be text present in the original customer review. Never quote, paraphrase, or merge text from the retrieved contextual reviews into evidence, summary, aspects, pros, or cons.
4. Never attribute anything from the retrieved contextual reviews to the customer whose review is being analyzed, and never claim retrieved content appears in the original review.
5. Use retrieved contextual reviews only to interpret wording or aspect names when clearly relevant. If context conflicts with the original review, the original review wins. Ignore irrelevant context.
"""


def build_analysis_prompt(
    review_text: str,
    context: Optional[RagContext],
    base_system_instruction: str,
) -> Tuple[str, str]:
    """Return ``(prompt, system_instruction)`` for one analysis attempt."""
    if context is None or context.is_empty:
        return BASE_PROMPT.format(text=review_text), base_system_instruction
    block = render_context_block(context)
    prompt = (
        "Analyze this customer product review.\n\n"
        f"{ORIGINAL_REVIEW_HEADER}\n"
        f'"""\n{review_text}\n"""\n\n'
        f"{CONTEXT_HEADER}\n"
        f'"""\n{block}\n"""'
    )
    return prompt, base_system_instruction + CONTEXT_SYSTEM_RULES

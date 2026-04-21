import json

DECOMPOSE_PROMPT = """You are a search query expert. Given the user's question, generate 2-3 focused web search queries that together cover the most important aspects needed to fully answer the question.

Rules:
- Each query should target a distinct, specific aspect
- Keep queries concise (3-7 words)
- Use domain-specific terminology when relevant (e.g., "UAE FTA", "IFRS 15", "ISA 700")
- Output ONLY a JSON array of strings: ["query 1", "query 2", "query 3"]

User question: {question}
"""


async def decompose_query(question: str, llm_client) -> list[str]:
    """Use the LLM to break a question into 2-3 targeted search queries."""
    try:
        response = await llm_client.complete(
            DECOMPOSE_PROMPT.format(question=question),
            max_tokens=150,
            temperature=0.1,
        )
        queries = json.loads(response.strip())
        if isinstance(queries, list) and queries:
            return [str(q) for q in queries[:3]]
    except Exception:
        pass
    return [question]

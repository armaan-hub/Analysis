from __future__ import annotations
from collections.abc import AsyncGenerator
from core.council.personas import EXPERTS, SYNTHESIS_PROMPT


def _build_expert_prompt(expert, question: str, base_answer: str, prior_critiques: list) -> str:
    prior = "\n\n".join(
        f"## {name} ({role}) said:\n{content}"
        for name, role, content in prior_critiques
    ) or "(no prior critiques)"
    return (
        f"{expert.system_prompt}\n\n"
        f"USER QUESTION:\n{question}\n\n"
        f"PROPOSED BASE ANSWER:\n{base_answer}\n\n"
        f"PRIOR EXPERT CRITIQUES:\n{prior}\n\n"
        f"Provide YOUR critique now. Be specific and cite standards."
    )


def _build_synthesis_prompt(question: str, base_answer: str, all_critiques: list) -> str:
    blocks = "\n\n".join(
        f"## {name} ({role}):\n{content}"
        for name, role, content in all_critiques
    )
    return (
        f"{SYNTHESIS_PROMPT}\n\n"
        f"USER QUESTION:\n{question}\n\n"
        f"PROPOSED BASE ANSWER:\n{base_answer}\n\n"
        f"EXPERT CRITIQUES:\n{blocks}\n\n"
        f"Produce the final unified answer now."
    )


async def run_council(*, question: str, base_answer: str, llm) -> AsyncGenerator[dict, None]:
    """Sequential chain: each expert sees all prior experts' critiques."""
    error: str | None = None
    prior_critiques: list[tuple[str, str, str]] = []
    try:
        for expert in EXPERTS:
            yield {"type": "council_expert", "expert": expert.name, "role": expert.role, "status": "thinking"}
            prompt = _build_expert_prompt(expert, question, base_answer, prior_critiques)
            buf: list[str] = []
            async for piece in llm.stream(prompt, max_tokens=600, temperature=0.3):
                buf.append(piece)
                yield {"type": "council_expert", "expert": expert.name, "delta": piece}
            full = "".join(buf)
            yield {"type": "council_expert", "expert": expert.name, "content": full, "final": True}
            prior_critiques.append((expert.name, expert.role, full))

        synth_prompt = _build_synthesis_prompt(question, base_answer, prior_critiques)
        synth_buf: list[str] = []
        async for piece in llm.stream(synth_prompt, max_tokens=800, temperature=0.2):
            synth_buf.append(piece)
        yield {"type": "council_synthesis", "content": "".join(synth_buf), "final": True}
    except GeneratorExit:
        return
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        yield {"type": "council_error", "error": error}

    payload: dict = {"type": "done"}
    if error:
        payload["error"] = error
    yield payload

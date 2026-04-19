# Legal Studio Modes, Doc UX, and Template Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement four-bundle overhaul: Legal Studio chat modes + domain classifier (Bundle A), Deep Research mode (Bundle B), Legal Studio docs + UI rework (Bundle C), Template Studio preview (Bundle D).

**Architecture:** Backend adds a new classifier + deep-research orchestrator + auditor agent + summarizer + template preview endpoints. Frontend rebuilds Legal Studio as a 3-pane layout (Sources | Chat | Preview) with mode dropdown and domain chip, and adds a template preview modal to Template Studio. Phases ship independently; each phase leaves the app runnable.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pytest, Alembic (migrations); React 18 + TypeScript + Vite, PDF.js (via `pdfjs-dist`); SSE for streaming.

**Phase Order:** Bundle A → Bundle B → Bundle C → Bundle D. Bundle D is independent and can be done in parallel by a second developer. Bundle B depends on Bundle A's mode selector. Bundle C depends on Bundle A's chat flow.

---

## Phase 1 — Bundle A: Chat Modes + Domain Classifier

Ship mode dropdown, domain chip, classifier, and fix for VAT→Law routing bug.

### Task 1: Domain classifier enum + data model

**Files:**
- Create: `backend/core/chat/domain_classifier.py`
- Test: `backend/tests/test_domain_classifier.py`

- [ ] **Step 1: Write failing test for enum + result model**

```python
# backend/tests/test_domain_classifier.py
from backend.core.chat.domain_classifier import DomainLabel, ClassifierResult

def test_domain_label_values():
    assert DomainLabel.VAT.value == "vat"
    assert DomainLabel.CORPORATE_TAX.value == "corporate_tax"
    assert DomainLabel.PEPPOL.value == "peppol"
    assert DomainLabel.E_INVOICING.value == "e_invoicing"
    assert DomainLabel.LABOUR.value == "labour"
    assert DomainLabel.COMMERCIAL.value == "commercial"
    assert DomainLabel.IFRS.value == "ifrs"
    assert DomainLabel.GENERAL_LAW.value == "general_law"

def test_classifier_result_shape():
    r = ClassifierResult(
        domain=DomainLabel.VAT,
        confidence=0.92,
        alternatives=[(DomainLabel.CORPORATE_TAX, 0.05)],
    )
    assert r.domain == DomainLabel.VAT
    assert r.confidence == 0.92
    assert r.alternatives[0][0] == DomainLabel.CORPORATE_TAX
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_domain_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create enum + result model**

```python
# backend/core/chat/domain_classifier.py
from enum import Enum
from pydantic import BaseModel

class DomainLabel(str, Enum):
    VAT = "vat"
    CORPORATE_TAX = "corporate_tax"
    PEPPOL = "peppol"
    E_INVOICING = "e_invoicing"
    LABOUR = "labour"
    COMMERCIAL = "commercial"
    IFRS = "ifrs"
    GENERAL_LAW = "general_law"

class ClassifierResult(BaseModel):
    domain: DomainLabel
    confidence: float
    alternatives: list[tuple[DomainLabel, float]]
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd backend && pytest tests/test_domain_classifier.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/chat/domain_classifier.py backend/tests/test_domain_classifier.py
git commit -m "feat(chat): add DomainLabel enum and ClassifierResult model"
```

---

### Task 2: Classifier prompt file

**Files:**
- Create: `backend/core/chat/prompts/domain_classifier.md`

- [ ] **Step 1: Write the classifier prompt**

```markdown
# backend/core/chat/prompts/domain_classifier.md
You are a classifier for UAE accounting and legal questions. Return ONLY valid JSON matching this schema:
{"domain": "<label>", "confidence": <0..1>, "alternatives": [["<label>", <0..1>], ...]}

Labels (choose exactly one primary, plus up to 2 alternatives):
- vat: UAE VAT, FTA filings, input/output tax, refunds, reverse charge, VAT groups.
- corporate_tax: UAE CT 9%, qualifying free zone, small business relief, CT returns.
- peppol: Peppol infrastructure, PINT AE, access-service-provider (ASP), network onboarding.
- e_invoicing: UAE e-invoicing mandate, DCTCE format rules, e-invoice issuance.
- labour: MOHRE, WPS, gratuity, labour contracts, visas.
- commercial: UAE Commercial Companies Law, licensing, shareholding, liquidation.
- ifrs: financial reporting standards, disclosures, accounting treatment.
- general_law: UAE federal/emirate law that does not fit the above labels.

Examples:
Q: "How do I claim input VAT on imports?"
A: {"domain": "vat", "confidence": 0.96, "alternatives": [["e_invoicing", 0.03]]}

Q: "Is my free zone entity exempt from 9% CT?"
A: {"domain": "corporate_tax", "confidence": 0.94, "alternatives": [["vat", 0.03]]}

Q: "Which Peppol ASP should I register with for UAE mandate?"
A: {"domain": "peppol", "confidence": 0.95, "alternatives": [["e_invoicing", 0.04]]}

Q: "When is gratuity payable for limited contracts?"
A: {"domain": "labour", "confidence": 0.97, "alternatives": [["general_law", 0.02]]}

Q: "What disclosures are required under IAS 16?"
A: {"domain": "ifrs", "confidence": 0.96, "alternatives": [["general_law", 0.02]]}

Q: "Can a UAE LLC convert to a PJSC?"
A: {"domain": "commercial", "confidence": 0.93, "alternatives": [["general_law", 0.05]]}

Q: "What does the DCTCE format require?"
A: {"domain": "e_invoicing", "confidence": 0.94, "alternatives": [["peppol", 0.04]]}

Q: "What is the limitation period for civil claims in UAE?"
A: {"domain": "general_law", "confidence": 0.9, "alternatives": [["commercial", 0.07]]}

Output rules:
- Respond with JSON only. No prose. No markdown fencing.
- Choose labels from the list above. Do not invent new ones.
- If uncertain, pick best guess and lower confidence; do not refuse.
```

- [ ] **Step 2: Commit**

```bash
git add backend/core/chat/prompts/domain_classifier.md
git commit -m "feat(chat): add UAE domain classifier prompt"
```

---

### Task 3: Classifier function (LLM call + parse)

**Files:**
- Modify: `backend/core/chat/domain_classifier.py`
- Test: `backend/tests/test_domain_classifier.py` (extend)

- [ ] **Step 1: Write failing test with LLM mock**

```python
# Append to backend/tests/test_domain_classifier.py
import json
from unittest.mock import patch
from backend.core.chat.domain_classifier import classify_domain

def test_classify_vat_query(monkeypatch):
    fake_json = '{"domain": "vat", "confidence": 0.95, "alternatives": [["corporate_tax", 0.03]]}'
    with patch("backend.core.chat.domain_classifier._llm_complete", return_value=fake_json):
        r = classify_domain("How do I reclaim input VAT on UAE imports?")
    assert r.domain == DomainLabel.VAT
    assert r.confidence == 0.95
    assert r.alternatives[0][0] == DomainLabel.CORPORATE_TAX

def test_classify_fallback_on_bad_json(monkeypatch):
    with patch("backend.core.chat.domain_classifier._llm_complete", return_value="not json"):
        r = classify_domain("ambiguous query")
    assert r.domain == DomainLabel.GENERAL_LAW
    assert r.confidence <= 0.5
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd backend && pytest tests/test_domain_classifier.py -v`
Expected: FAIL with `ImportError: classify_domain`.

- [ ] **Step 3: Implement classify_domain**

```python
# Append to backend/core/chat/domain_classifier.py
import json
import logging
from pathlib import Path
from backend.core.llm_manager import LLMManager  # existing module

logger = logging.getLogger(__name__)
_PROMPT_PATH = Path(__file__).parent / "prompts" / "domain_classifier.md"

def _llm_complete(user_query: str) -> str:
    """Call cheap/fast model with the classifier prompt. Return raw text."""
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    llm = LLMManager.get_fast_model()  # use existing helper; see LLMManager
    return llm.complete(system=system_prompt, user=user_query, max_tokens=200)

def classify_domain(query: str) -> ClassifierResult:
    try:
        raw = _llm_complete(query)
        parsed = json.loads(raw)
        domain = DomainLabel(parsed["domain"])
        confidence = float(parsed.get("confidence", 0.0))
        alts = [(DomainLabel(label), float(score)) for label, score in parsed.get("alternatives", [])]
        return ClassifierResult(domain=domain, confidence=confidence, alternatives=alts)
    except Exception as e:
        logger.warning("Domain classifier failed, falling back to general_law: %s", e)
        return ClassifierResult(
            domain=DomainLabel.GENERAL_LAW, confidence=0.3, alternatives=[]
        )
```

> **Note:** If `LLMManager.get_fast_model()` does not yet exist, add it as a thin accessor returning whichever provider the codebase already uses for cheap completions (Haiku/Gemini Flash/NVIDIA small). Match the return contract expected by existing chat code.

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && pytest tests/test_domain_classifier.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add backend/core/chat/domain_classifier.py backend/tests/test_domain_classifier.py
git commit -m "feat(chat): implement classify_domain with fallback"
```

---

### Task 4: Classifier accuracy fixture

**Files:**
- Create: `backend/tests/fixtures/domain_queries.json`
- Test: `backend/tests/test_domain_classifier_accuracy.py`

- [ ] **Step 1: Write fixture**

```json
[
  {"q": "Can I claim VAT on business fuel?", "expected": "vat"},
  {"q": "Due date for first VAT return?", "expected": "vat"},
  {"q": "Reverse charge for import of services UAE?", "expected": "vat"},
  {"q": "Qualifying free zone person under CT?", "expected": "corporate_tax"},
  {"q": "How is CT computed on 9%?", "expected": "corporate_tax"},
  {"q": "Small business relief threshold?", "expected": "corporate_tax"},
  {"q": "Peppol BIS 3.0 rules in UAE?", "expected": "peppol"},
  {"q": "Onboarding with Peppol ASP?", "expected": "peppol"},
  {"q": "UAE e-invoicing mandate timeline?", "expected": "e_invoicing"},
  {"q": "DCTCE schema fields?", "expected": "e_invoicing"},
  {"q": "MOHRE WPS penalty for late salary?", "expected": "labour"},
  {"q": "Gratuity for unlimited contract?", "expected": "labour"},
  {"q": "Visa cancellation labour process?", "expected": "labour"},
  {"q": "LLC to PJSC conversion steps?", "expected": "commercial"},
  {"q": "Minimum shareholders for LLC UAE?", "expected": "commercial"},
  {"q": "Free zone licensing transfer?", "expected": "commercial"},
  {"q": "IAS 36 impairment indicators?", "expected": "ifrs"},
  {"q": "IFRS 15 revenue recognition stages?", "expected": "ifrs"},
  {"q": "Disclosures under IFRS 16?", "expected": "ifrs"},
  {"q": "UAE civil limitation period?", "expected": "general_law"},
  {"q": "Enforcement of foreign judgments UAE?", "expected": "general_law"},
  {"q": "UAE data privacy law scope?", "expected": "general_law"}
]
```

- [ ] **Step 2: Write accuracy test**

```python
# backend/tests/test_domain_classifier_accuracy.py
import json
import os
from pathlib import Path
import pytest
from backend.core.chat.domain_classifier import classify_domain, DomainLabel

FIXTURE = Path(__file__).parent / "fixtures" / "domain_queries.json"

@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_LLM_TESTS") != "1", reason="Set RUN_LLM_TESTS=1 to run")
def test_classifier_accuracy_threshold():
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    hits = 0
    for row in rows:
        got = classify_domain(row["q"]).domain.value
        if got == row["expected"]:
            hits += 1
    accuracy = hits / len(rows)
    assert accuracy >= 0.9, f"Accuracy {accuracy:.2%} below 90% threshold"
```

- [ ] **Step 3: Run with real LLM**

Run: `cd backend && RUN_LLM_TESTS=1 pytest tests/test_domain_classifier_accuracy.py -v`
Expected: PASS at ≥90%. If below, tune prompt in Task 2 and rerun.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/fixtures/domain_queries.json backend/tests/test_domain_classifier_accuracy.py
git commit -m "test(chat): add UAE domain classifier accuracy fixture"
```

---

### Task 5: Remove default='law' fallback in prompt router

**Files:**
- Modify: `backend/core/chat/prompt_router.py`
- Test: `backend/tests/test_prompt_router.py`

- [ ] **Step 1: Inspect current router**

Run: `cd backend && grep -n "default" core/chat/prompt_router.py`
Read the function that selects a prompt by domain. Identify where `law` is assigned as fallback.

- [ ] **Step 2: Write failing test**

```python
# backend/tests/test_prompt_router.py
import pytest
from backend.core.chat.prompt_router import route_prompt
from backend.core.chat.domain_classifier import DomainLabel

def test_route_vat_returns_vat_prompt():
    p = route_prompt(DomainLabel.VAT)
    assert "vat" in p.lower() or "value-added tax" in p.lower()

def test_route_general_law_returns_general_law_prompt():
    p = route_prompt(DomainLabel.GENERAL_LAW)
    assert p  # non-empty
    assert "law" in p.lower()

def test_router_requires_enum_not_string():
    with pytest.raises((TypeError, ValueError, KeyError)):
        route_prompt("unknown_string")  # type: ignore[arg-type]
```

- [ ] **Step 3: Run test to verify fail**

Run: `cd backend && pytest tests/test_prompt_router.py -v`
Expected: FAIL if current router accepts strings with default fallback.

- [ ] **Step 4: Refactor router**

Rewrite `route_prompt` to accept `DomainLabel` enum, look up the matching prompt, and raise on unknown values. Example target:

```python
# backend/core/chat/prompt_router.py
from backend.core.chat.domain_classifier import DomainLabel

# existing 9 domain prompt strings imported or defined here
_PROMPTS: dict[DomainLabel, str] = {
    DomainLabel.VAT: VAT_PROMPT,
    DomainLabel.CORPORATE_TAX: CORPORATE_TAX_PROMPT,
    DomainLabel.PEPPOL: PEPPOL_PROMPT,
    DomainLabel.E_INVOICING: E_INVOICING_PROMPT,
    DomainLabel.LABOUR: LABOUR_PROMPT,
    DomainLabel.COMMERCIAL: COMMERCIAL_PROMPT,
    DomainLabel.IFRS: IFRS_PROMPT,
    DomainLabel.GENERAL_LAW: GENERAL_LAW_PROMPT,
}

def route_prompt(domain: DomainLabel) -> str:
    if not isinstance(domain, DomainLabel):
        raise TypeError(f"domain must be DomainLabel, got {type(domain)}")
    return _PROMPTS[domain]
```

Remove any `default="law"` branch.

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && pytest tests/test_prompt_router.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/core/chat/prompt_router.py backend/tests/test_prompt_router.py
git commit -m "refactor(chat): route_prompt takes DomainLabel, drop 'law' default"
```

---

### Task 6: Chat endpoint wires classifier + domain_override + mode

**Files:**
- Modify: `backend/api/chat.py`
- Test: `backend/tests/test_chat_endpoint_domain.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_chat_endpoint_domain.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.chat.domain_classifier import DomainLabel, ClassifierResult

client = TestClient(app)

def _stub_classifier(domain: DomainLabel):
    return ClassifierResult(domain=domain, confidence=0.95, alternatives=[])

def test_send_message_uses_classifier(monkeypatch):
    with patch("backend.api.chat.classify_domain",
               return_value=_stub_classifier(DomainLabel.VAT)):
        r = client.post("/api/chat/send_message",
                        json={"message": "How to file UAE VAT return?"})
    assert r.status_code == 200
    body = r.json()
    assert body["classifier"]["domain"] == "vat"

def test_send_message_honors_domain_override(monkeypatch):
    with patch("backend.api.chat.classify_domain") as m:
        r = client.post("/api/chat/send_message",
                        json={"message": "anything",
                              "domain_override": "corporate_tax"})
        m.assert_not_called()
    assert r.status_code == 200
    body = r.json()
    assert body["classifier"]["domain"] == "corporate_tax"
    assert body["classifier"]["confidence"] == 1.0

def test_send_message_accepts_mode(monkeypatch):
    r = client.post("/api/chat/send_message",
                    json={"message": "hi", "mode": "normal"})
    assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd backend && pytest tests/test_chat_endpoint_domain.py -v`
Expected: FAIL (classifier not called, no override support).

- [ ] **Step 3: Update request schema + endpoint**

```python
# backend/api/chat.py (modify existing)
from typing import Literal, Optional
from pydantic import BaseModel
from backend.core.chat.domain_classifier import classify_domain, DomainLabel, ClassifierResult
from backend.core.chat.prompt_router import route_prompt

Mode = Literal["normal", "deep_research", "analyst"]

class SendMessageRequest(BaseModel):
    message: str
    mode: Mode = "normal"
    domain_override: Optional[DomainLabel] = None
    selected_document_ids: list[str] = []

@router.post("/send_message")
async def send_message(req: SendMessageRequest):
    if req.domain_override is not None:
        classifier = ClassifierResult(
            domain=req.domain_override, confidence=1.0, alternatives=[]
        )
    else:
        classifier = classify_domain(req.message)

    prompt = route_prompt(classifier.domain)
    # existing generation call, now passing `prompt` instead of hardcoded 'law' prompt
    answer = await _generate_chat_response(
        system_prompt=prompt,
        user_message=req.message,
        document_ids=req.selected_document_ids,
    )
    return {
        "answer": answer,
        "classifier": classifier.model_dump(),
        "mode": req.mode,
    }
```

> If `/send_message` currently streams, keep streaming and attach classifier result as a leading event or trailing metadata. Do not change response shape for non-stream callers.

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && pytest tests/test_chat_endpoint_domain.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/chat.py backend/tests/test_chat_endpoint_domain.py
git commit -m "feat(chat): wire classifier, domain_override, and mode into /send_message"
```

---

### Task 7: Frontend ModeDropdown component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/ModeDropdown.tsx`

- [ ] **Step 1: Implement component**

```tsx
// frontend/src/components/studios/LegalStudio/ModeDropdown.tsx
import { useState } from "react";

export type ChatMode = "normal" | "deep_research" | "analyst";

const OPTIONS: { value: ChatMode; label: string; icon: string }[] = [
  { value: "normal", label: "Normal", icon: "⚡" },
  { value: "deep_research", label: "Deep Research", icon: "🔍" },
  { value: "analyst", label: "Analyst", icon: "📊" },
];

interface Props {
  value: ChatMode;
  onChange: (v: ChatMode) => void;
}

export function ModeDropdown({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const current = OPTIONS.find(o => o.value === value) ?? OPTIONS[0];
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 rounded-full bg-slate-800 text-sm text-white hover:bg-slate-700"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{current.icon}</span>
        <span>{current.label}</span>
        <span>▾</span>
      </button>
      {open && (
        <ul role="listbox" className="absolute z-20 mt-1 min-w-[200px] rounded-md bg-slate-900 shadow-lg">
          {OPTIONS.map(o => (
            <li key={o.value}>
              <button
                type="button"
                onClick={() => { onChange(o.value); setOpen(false); }}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-800 ${o.value === value ? "bg-slate-800" : ""}`}
              >
                {o.icon} {o.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Manual verify**

Render inside any existing page temporarily; click the pill, verify options appear and clicking updates state.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ModeDropdown.tsx
git commit -m "feat(legal-studio): add ModeDropdown component"
```

---

### Task 8: Frontend DomainChip component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/DomainChip.tsx`

- [ ] **Step 1: Implement component**

```tsx
// frontend/src/components/studios/LegalStudio/DomainChip.tsx
import { useState } from "react";

export type DomainLabel =
  | "vat" | "corporate_tax" | "peppol" | "e_invoicing"
  | "labour" | "commercial" | "ifrs" | "general_law";

const ALL: DomainLabel[] = [
  "vat", "corporate_tax", "peppol", "e_invoicing",
  "labour", "commercial", "ifrs", "general_law",
];

const LABELS: Record<DomainLabel, string> = {
  vat: "VAT",
  corporate_tax: "Corporate Tax",
  peppol: "Peppol",
  e_invoicing: "E-Invoicing",
  labour: "Labour",
  commercial: "Commercial",
  ifrs: "IFRS",
  general_law: "General Law",
};

interface Props {
  value: DomainLabel;
  editable: boolean;
  onChange?: (v: DomainLabel) => void;
}

export function DomainChip({ value, editable, onChange }: Props) {
  const [open, setOpen] = useState(false);
  if (!editable) {
    return <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-violet-600/30 text-violet-200 text-xs">{LABELS[value]}</span>;
  }
  return (
    <div className="relative inline-block">
      <button
        type="button"
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-violet-600/30 text-violet-200 text-xs hover:bg-violet-600/50"
        onClick={() => setOpen(!open)}
      >
        Domain: {LABELS[value]} ✎
      </button>
      {open && (
        <ul className="absolute z-20 mt-1 rounded-md bg-slate-900 shadow-lg text-xs">
          {ALL.map(d => (
            <li key={d}>
              <button
                type="button"
                className={`w-full text-left px-3 py-1.5 hover:bg-slate-800 ${d === value ? "bg-slate-800" : ""}`}
                onClick={() => { onChange?.(d); setOpen(false); }}
              >
                {LABELS[d]}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/DomainChip.tsx
git commit -m "feat(legal-studio): add DomainChip component"
```

---

### Task 9: Wire mode + domain into ChatInput and LegalStudio

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ChatInput.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

- [ ] **Step 1: Extend ChatInput to render ModeDropdown and emit mode**

Edit `ChatInput.tsx`:
- Accept props `mode: ChatMode`, `onModeChange: (m: ChatMode) => void`, `domainOverride: DomainLabel | null`, `onDomainOverrideChange: (d: DomainLabel | null) => void`.
- Render `<ModeDropdown>` to the left of the send button.
- Render `<DomainChip>` above the input when `domainOverride` is set (read-only if not set; editable via a small gear/edit action).

Example shape:

```tsx
import { ModeDropdown, ChatMode } from "./ModeDropdown";
import { DomainChip, DomainLabel } from "./DomainChip";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  mode: ChatMode;
  onModeChange: (m: ChatMode) => void;
  domainOverride: DomainLabel | null;
  onDomainOverrideChange: (d: DomainLabel | null) => void;
}

export function ChatInput(p: Props) {
  return (
    <div className="flex flex-col gap-2">
      {p.domainOverride && (
        <DomainChip value={p.domainOverride} editable onChange={p.onDomainOverrideChange} />
      )}
      <div className="flex items-center gap-2">
        <ModeDropdown value={p.mode} onChange={p.onModeChange} />
        <input value={p.value} onChange={e => p.onChange(e.target.value)} className="flex-1 ..." />
        <button onClick={p.onSubmit}>Send</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Thread state through LegalStudio**

In `LegalStudio.tsx`:
- Add `const [mode, setMode] = useState<ChatMode>("normal")`.
- Add `const [domainOverride, setDomainOverride] = useState<DomainLabel | null>(null)`.
- Pass into `<ChatInput>`.
- In submit handler, include `mode` and `domain_override` in the POST body.
- On response, read `classifier.domain` and render a read-only `<DomainChip>` on the answer bubble.

- [ ] **Step 3: Manual verify**

Run: `cd frontend && npm run dev`
- Open Legal Studio.
- Verify mode pill appears, default "Normal".
- Click pill; all 3 options show; selecting one persists visually.
- Type "How to file VAT?" and send; chip shows detected domain.
- Edit chip to different domain via click; next send uses override.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ChatInput.tsx frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat(legal-studio): wire mode dropdown and domain chip into chat"
```

---

### Task 10: Reproduce + fix on-screen error (screenshot #1)

**Files:**
- Modify: whichever file root-cause lives in.

- [ ] **Step 1: Reproduce**

Run backend (`cd backend && uv run python main.py`) and frontend (`cd frontend && npm run dev`). Open Legal Studio, ask a VAT question, capture the exact error text (UI + browser console + backend log).

- [ ] **Step 2: Record root cause**

In a scratch note, record: which layer emits the error (frontend fetch, backend exception, router misrouting), the stack trace, and the minimal failing input.

- [ ] **Step 3: Write a failing test that reproduces it**

Prefer a backend pytest if the error is server-side, or a direct call from the frontend using `curl` / a quick script. Add to `backend/tests/test_chat_endpoint_domain.py` or create a new file.

- [ ] **Step 4: Fix the root cause**

Apply the minimal fix. Do not refactor surrounding code.

- [ ] **Step 5: Run test + manual reproduce again**

Expected: PASS, UI no longer shows the error.

- [ ] **Step 6: Commit**

```bash
git add <touched-files>
git commit -m "fix(legal-studio): <root-cause summary>"
```

### Phase 1 Gate

- [ ] All Phase 1 tests green: `cd backend && pytest tests/test_domain_classifier.py tests/test_prompt_router.py tests/test_chat_endpoint_domain.py -v`
- [ ] Manual smoke: send VAT question → chip shows VAT (not General Law).
- [ ] On-screen error from screenshot #1 gone.
- [ ] Tag: `git tag phase-1-bundle-a`.

---

## Phase 2 — Bundle B: Deep Research Mode

Add background-job orchestrator with SSE streaming and saveable final report.

### Task 11: DB migration — research_jobs table

**Files:**
- Create: `backend/db/migrations/NNNN_research_jobs.py`
- Modify: `backend/db/models.py`

- [ ] **Step 1: Add model**

```python
# Append to backend/db/models.py
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Enum as SAEnum
import enum, uuid
from datetime import datetime

class ResearchJobStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"

class ResearchJob(Base):
    __tablename__ = "research_jobs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    thread_id = Column(String, nullable=True)
    query = Column(String, nullable=False)
    status = Column(SAEnum(ResearchJobStatus), default=ResearchJobStatus.running, nullable=False)
    plan_json = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
```

> Adjust foreign keys to match the codebase's existing user model; if no user model, drop the FK and keep `user_id` nullable String.

- [ ] **Step 2: Generate Alembic migration**

Run: `cd backend && alembic revision --autogenerate -m "research_jobs table"`
Review generated migration, keep only the new table.

- [ ] **Step 3: Apply migration**

Run: `cd backend && alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade ... research_jobs table`

- [ ] **Step 4: Commit**

```bash
git add backend/db/models.py backend/db/migrations/
git commit -m "feat(db): add research_jobs table"
```

---

### Task 12: Deep research orchestrator (skeleton + event bus)

**Files:**
- Create: `backend/core/chat/deep_research.py`
- Test: `backend/tests/test_deep_research_orchestrator.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_deep_research_orchestrator.py
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from backend.core.chat.deep_research import run_research, ResearchEventBus

@pytest.mark.asyncio
async def test_orchestrator_emits_lifecycle_events():
    bus = ResearchEventBus()
    events = []

    async def collect():
        async for e in bus.subscribe():
            events.append(e)

    with patch("backend.core.chat.deep_research.plan_query",
               new=AsyncMock(return_value=["sub1"])), \
         patch("backend.core.chat.deep_research.rag_search",
               new=AsyncMock(return_value=[{"title": "r", "url": None, "rag_id": "r1"}])), \
         patch("backend.core.chat.deep_research.web_fallback_search",
               new=AsyncMock(return_value=[])), \
         patch("backend.core.chat.deep_research.synthesize_stream") as syn:
        async def _fake(*a, **k):
            yield "Hello "
            yield "world"
        syn.return_value = _fake()

        task = asyncio.create_task(collect())
        await run_research("job1", "Q", source_ids=[], bus=bus)
        await asyncio.sleep(0)
        bus.close()
        await task

    kinds = [e["event"] for e in events]
    assert "plan" in kinds
    assert "source_found" in kinds
    assert any(e["event"] == "token" for e in events)
    assert kinds[-1] == "done"
```

- [ ] **Step 2: Run — expect fail**

Run: `cd backend && pytest tests/test_deep_research_orchestrator.py -v`

- [ ] **Step 3: Implement**

```python
# backend/core/chat/deep_research.py
import asyncio
from typing import AsyncIterator, Optional
from backend.db.models import ResearchJob, ResearchJobStatus
from backend.db.database import SessionLocal

class ResearchEventBus:
    def __init__(self) -> None:
        self._q: asyncio.Queue[Optional[dict]] = asyncio.Queue()

    def emit(self, event: dict) -> None:
        self._q.put_nowait(event)

    def close(self) -> None:
        self._q.put_nowait(None)

    async def subscribe(self) -> AsyncIterator[dict]:
        while True:
            item = await self._q.get()
            if item is None:
                return
            yield item

# Placeholder external calls; real ones wired in Task 13.
async def plan_query(query: str) -> list[str]:
    raise NotImplementedError

async def rag_search(sub_q: str, source_ids: list[str]) -> list[dict]:
    raise NotImplementedError

async def web_fallback_search(sub_q: str) -> list[dict]:
    raise NotImplementedError

async def synthesize_stream(query: str, plan: list[str], sources: list[dict]) -> AsyncIterator[str]:
    if False:
        yield ""

async def run_research(job_id: str, query: str, source_ids: list[str], bus: ResearchEventBus) -> None:
    try:
        plan = await plan_query(query)
        bus.emit({"event": "plan", "sub_questions": plan})

        sources: list[dict] = []
        for sq in plan:
            rag_hits = await rag_search(sq, source_ids)
            web_hits = await web_fallback_search(sq)
            for h in rag_hits + web_hits:
                bus.emit({"event": "source_found", **h})
                sources.append(h)

        chunks: list[str] = []
        async for tok in synthesize_stream(query, plan, sources):
            chunks.append(tok)
            bus.emit({"event": "token", "text": tok})

        result = {
            "summary": "".join(chunks),
            "sections": [{"sub_question": sq, "answer": "", "sources": []} for sq in plan],
            "citations": sources,
        }
        _persist_done(job_id, plan, result)
        bus.emit({"event": "done", "report_id": job_id})
    except Exception as e:
        _persist_failed(job_id, str(e))
        bus.emit({"event": "error", "message": str(e)})

def _persist_done(job_id: str, plan: list[str], result: dict) -> None:
    with SessionLocal() as s:
        j = s.get(ResearchJob, job_id)
        if j is None:
            return
        j.plan_json = plan
        j.result_json = result
        j.status = ResearchJobStatus.completed
        from datetime import datetime
        j.completed_at = datetime.utcnow()
        s.commit()

def _persist_failed(job_id: str, err: str) -> None:
    with SessionLocal() as s:
        j = s.get(ResearchJob, job_id)
        if j is None:
            return
        j.status = ResearchJobStatus.failed
        j.result_json = {"error": err}
        from datetime import datetime
        j.completed_at = datetime.utcnow()
        s.commit()
```

- [ ] **Step 4: Run — pass**

Run: `cd backend && pytest tests/test_deep_research_orchestrator.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/core/chat/deep_research.py backend/tests/test_deep_research_orchestrator.py
git commit -m "feat(research): orchestrator skeleton + event bus"
```

---

### Task 13: Wire real planner, RAG search, web fallback, synthesizer

**Files:**
- Modify: `backend/core/chat/deep_research.py`
- Test: `backend/tests/test_deep_research_integration.py`

- [ ] **Step 1: Replace `plan_query` with LLM call**

Use `LLMManager.get_fast_model()`. Prompt: "Decompose user query into 3-6 research sub-questions, return JSON list of strings." Parse strictly; on parse failure, return `[query]` as single sub-question.

- [ ] **Step 2: Replace `rag_search` with existing RAG engine**

```python
from backend.core.rag_engine import RAGEngine

async def rag_search(sub_q: str, source_ids: list[str]) -> list[dict]:
    engine = RAGEngine()  # or existing singleton
    hits = await engine.search(sub_q, document_ids=source_ids or None, k=5)
    return [{"title": h.title, "url": None, "rag_id": h.id} for h in hits]
```

> Match the real `RAGEngine` signature; adjust field names.

- [ ] **Step 3: Replace `web_fallback_search` with existing module**

Look for `backend/core/web/` or similar; import its search function. If no web search module exists, leave a stub returning `[]` and add a TODO in the spec (not in the plan) for a later project.

- [ ] **Step 4: Replace `synthesize_stream` with real LLM streaming**

```python
async def synthesize_stream(query: str, plan: list[str], sources: list[dict]):
    llm = LLMManager.get_top_model()  # max context, unlimited tokens
    context = _format_sources(sources)
    prompt = f"...synthesize structured report for: {query}\nSub-questions: {plan}\nSources:\n{context}"
    async for chunk in llm.stream(prompt=prompt):
        yield chunk
```

- [ ] **Step 5: Write integration test**

```python
# backend/tests/test_deep_research_integration.py
import os, asyncio, pytest
from backend.core.chat.deep_research import run_research, ResearchEventBus
from backend.db.database import SessionLocal
from backend.db.models import ResearchJob, ResearchJobStatus

@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_LLM_TESTS") != "1", reason="Set RUN_LLM_TESTS=1 to run")
@pytest.mark.asyncio
async def test_deep_research_end_to_end():
    with SessionLocal() as s:
        job = ResearchJob(id="test-int-1", query="UAE VAT refund overview")
        s.add(job); s.commit()

    bus = ResearchEventBus()
    await run_research("test-int-1", "UAE VAT refund overview", source_ids=[], bus=bus)

    with SessionLocal() as s:
        j = s.get(ResearchJob, "test-int-1")
        assert j.status == ResearchJobStatus.completed
        assert "summary" in j.result_json
```

- [ ] **Step 6: Run**

Run: `cd backend && RUN_LLM_TESTS=1 pytest tests/test_deep_research_integration.py -v`

- [ ] **Step 7: Commit**

```bash
git add backend/core/chat/deep_research.py backend/tests/test_deep_research_integration.py
git commit -m "feat(research): real planner/RAG/web/synthesis wiring"
```

---

### Task 14: Research endpoints (create / get / SSE stream)

**Files:**
- Modify: `backend/api/chat.py`
- Test: `backend/tests/test_research_endpoints.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_research_endpoints.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_create_research_job_returns_id():
    r = client.post("/api/chat/research",
                    json={"query": "UAE VAT refund", "source_ids": []})
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body

def test_get_research_job_returns_404_when_missing():
    r = client.get("/api/chat/research/nope")
    assert r.status_code == 404
```

- [ ] **Step 2: Run — fail**

Run: `cd backend && pytest tests/test_research_endpoints.py -v`

- [ ] **Step 3: Implement endpoints**

```python
# backend/api/chat.py additions
import asyncio, json
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from backend.core.chat.deep_research import run_research, ResearchEventBus
from backend.db.database import SessionLocal
from backend.db.models import ResearchJob

_buses: dict[str, ResearchEventBus] = {}

class ResearchCreateReq(BaseModel):
    query: str
    source_ids: list[str] = []
    thread_id: Optional[str] = None

@router.post("/research", status_code=202)
async def create_research(req: ResearchCreateReq, bg: BackgroundTasks):
    with SessionLocal() as s:
        job = ResearchJob(query=req.query, thread_id=req.thread_id)
        s.add(job); s.commit(); s.refresh(job)
        job_id = job.id
    bus = ResearchEventBus()
    _buses[job_id] = bus
    bg.add_task(_run_and_close, job_id, req.query, req.source_ids, bus)
    return {"job_id": job_id}

async def _run_and_close(job_id, query, source_ids, bus):
    try:
        await run_research(job_id, query, source_ids, bus)
    finally:
        bus.close()

@router.get("/research/{job_id}")
def get_research(job_id: str):
    with SessionLocal() as s:
        j = s.get(ResearchJob, job_id)
        if j is None:
            raise HTTPException(404, "not found")
        return {
            "job_id": j.id,
            "status": j.status.value,
            "query": j.query,
            "plan": j.plan_json,
            "result": j.result_json,
            "started_at": j.started_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }

@router.get("/research/{job_id}/stream")
async def stream_research(job_id: str):
    bus = _buses.get(job_id)
    if bus is None:
        raise HTTPException(404, "no live stream; poll /research/{id} instead")

    async def gen():
        async for e in bus.subscribe():
            yield f"data: {json.dumps(e)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 4: Run — pass**

Run: `cd backend && pytest tests/test_research_endpoints.py -v`

- [ ] **Step 5: Uvicorn keep-alive**

Edit the main server launch (`backend/main.py` or how uvicorn is started) to set `timeout_keep_alive=1200`. If uvicorn is launched via CLI, update the command/Dockerfile.

- [ ] **Step 6: Commit**

```bash
git add backend/api/chat.py backend/tests/test_research_endpoints.py backend/main.py
git commit -m "feat(research): create/get/stream endpoints, raise keep-alive"
```

---

### Task 15: Save research result to sources

**Files:**
- Modify: `backend/api/documents.py`
- Test: `backend/tests/test_from_research.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_from_research.py
from fastapi.testclient import TestClient
from backend.main import app
from backend.db.database import SessionLocal
from backend.db.models import ResearchJob, ResearchJobStatus

client = TestClient(app)

def test_from_research_creates_document():
    with SessionLocal() as s:
        job = ResearchJob(
            id="fr-1", query="q", status=ResearchJobStatus.completed,
            result_json={"summary": "hello", "sections": [], "citations": []}
        )
        s.add(job); s.commit()
    r = client.post("/api/documents/from-research/fr-1")
    assert r.status_code == 201
    body = r.json()
    assert "document_id" in body
    assert body["source"] == "research"
```

- [ ] **Step 2: Run — fail**

Run: `cd backend && pytest tests/test_from_research.py -v`

- [ ] **Step 3: Implement endpoint**

```python
# backend/api/documents.py additions
@router.post("/from-research/{job_id}", status_code=201)
def from_research(job_id: str):
    with SessionLocal() as s:
        job = s.get(ResearchJob, job_id)
        if job is None or job.status != ResearchJobStatus.completed:
            raise HTTPException(404, "no completed job")
        md = _render_research_to_markdown(job.result_json)
        doc = _ingest_markdown_as_document(
            content=md,
            title=f"Research: {job.query[:60]}",
            source="research",
        )
        return {"document_id": doc.id, "source": doc.source}
```

`_render_research_to_markdown` produces a readable doc with summary + sections + citations. `_ingest_markdown_as_document` reuses the existing document ingestion pipeline but tags `source='research'`.

- [ ] **Step 4: Run — pass**

Run: `cd backend && pytest tests/test_from_research.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/api/documents.py backend/tests/test_from_research.py
git commit -m "feat(research): save research result as document source=research"
```

---

### Task 16: Frontend ResearchBubble + deep research flow

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/ResearchBubble.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`

- [ ] **Step 1: Implement ResearchBubble**

```tsx
// frontend/src/components/studios/LegalStudio/ResearchBubble.tsx
import { useEffect, useState } from "react";

interface Props {
  jobId: string;
  onSaveToSources?: (jobId: string) => void;
}

interface Event { event: string; [k: string]: any }

export function ResearchBubble({ jobId, onSaveToSources }: Props) {
  const [plan, setPlan] = useState<string[]>([]);
  const [sources, setSources] = useState<Event[]>([]);
  const [text, setText] = useState("");
  const [status, setStatus] = useState<"running" | "done" | "error">("running");

  useEffect(() => {
    const es = new EventSource(`/api/chat/research/${jobId}/stream`);
    es.onmessage = (msg) => {
      const e: Event = JSON.parse(msg.data);
      if (e.event === "plan") setPlan(e.sub_questions);
      if (e.event === "source_found") setSources(prev => [...prev, e]);
      if (e.event === "token") setText(prev => prev + e.text);
      if (e.event === "done") { setStatus("done"); es.close(); }
      if (e.event === "error") { setStatus("error"); es.close(); }
    };
    es.onerror = () => { setStatus("error"); es.close(); };
    return () => es.close();
  }, [jobId]);

  return (
    <div className="rounded-md bg-slate-800 p-3 text-sm text-slate-100 space-y-2">
      <div className="text-xs text-slate-400">
        {status === "running" ? "🔍 Researching…" : status === "done" ? "✅ Done" : "⚠️ Error"}
      </div>
      {plan.length > 0 && (
        <details className="text-xs">
          <summary>Plan ({plan.length} sub-questions)</summary>
          <ol className="list-decimal pl-4">{plan.map((q, i) => <li key={i}>{q}</li>)}</ol>
        </details>
      )}
      {sources.length > 0 && (
        <details className="text-xs">
          <summary>Sources ({sources.length})</summary>
          <ul className="list-disc pl-4">
            {sources.map((s, i) => <li key={i}>{s.title}{s.url ? ` — ${s.url}` : ""}</li>)}
          </ul>
        </details>
      )}
      <div className="whitespace-pre-wrap">{text}</div>
      {status === "done" && onSaveToSources && (
        <button onClick={() => onSaveToSources(jobId)} className="px-3 py-1 rounded bg-violet-600 text-white">
          Save to Sources
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Branch submit handler on mode**

In `LegalStudio.tsx` submit handler, if `mode === "deep_research"`:
1. `POST /api/chat/research` with `{query, source_ids, thread_id}`.
2. Append a pseudo-message with `{type: "research", jobId}` to the messages list.
3. Render via `ResearchBubble` inside `ChatMessages.tsx`.

- [ ] **Step 3: Wire save-to-sources**

```tsx
const saveToSources = async (jobId: string) => {
  await fetch(`/api/documents/from-research/${jobId}`, { method: "POST" });
  refreshSources();
};
```

- [ ] **Step 4: Manual verify**

Send a Deep Research query; stream appears; plan, sources, tokens show. Click "Save to Sources"; refreshed sources list shows the new doc tagged `research`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ResearchBubble.tsx frontend/src/components/studios/LegalStudio/LegalStudio.tsx frontend/src/components/studios/LegalStudio/ChatMessages.tsx
git commit -m "feat(legal-studio): Deep Research UI + save to sources"
```

### Phase 2 Gate

- [ ] All Phase 2 backend tests green.
- [ ] Manual: submit deep-research query; stream arrives; save creates a doc.
- [ ] Tag: `git tag phase-2-bundle-b`.

---

## Phase 3 — Bundle C: Docs + UI Rework

Rebuild Legal Studio into 3-pane layout, add multi-upload, auto-summary, auditor agent, analyst handoff, and full button audit.

### Task 17: DB migration — documents summary/key_terms/source

**Files:**
- Modify: `backend/db/models.py`
- Create: `backend/db/migrations/NNNN_document_summary.py`

- [ ] **Step 1: Extend model**

Add to the existing `Document` model:
```python
summary = Column(String, nullable=True)
key_terms = Column(JSON, nullable=True)
source = Column(String, nullable=False, default="upload")
```

- [ ] **Step 2: Generate + apply migration**

```
cd backend && alembic revision --autogenerate -m "document summary key_terms source"
cd backend && alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add backend/db/models.py backend/db/migrations/
git commit -m "feat(db): add documents.summary, key_terms, source"
```

---

### Task 18: Summarizer module

**Files:**
- Create: `backend/core/documents/summarizer.py`
- Test: `backend/tests/test_document_summarizer.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_document_summarizer.py
import json
from unittest.mock import patch
from backend.core.documents.summarizer import summarize_document_text

def test_summarize_parses_valid_json():
    fake = json.dumps({"summary": "s", "key_terms": ["a", "b", "c", "d", "e"]})
    with patch("backend.core.documents.summarizer._llm_complete", return_value=fake):
        r = summarize_document_text("long text")
    assert r.summary == "s"
    assert r.key_terms == ["a", "b", "c", "d", "e"]
```

- [ ] **Step 2: Run — fail**

Run: `cd backend && pytest tests/test_document_summarizer.py -v`

- [ ] **Step 3: Implement**

```python
# backend/core/documents/summarizer.py
import json, logging
from pydantic import BaseModel
from backend.core.llm_manager import LLMManager

logger = logging.getLogger(__name__)

class DocSummary(BaseModel):
    summary: str
    key_terms: list[str]

def _llm_complete(text: str) -> str:
    system = (
        "Summarize in 3-5 lines (max 60 words). Then list 5 key terms."
        " Respond ONLY with JSON: {\"summary\": ..., \"key_terms\": [..]}"
    )
    llm = LLMManager.get_fast_model()
    return llm.complete(system=system, user=text[:8000], max_tokens=300)

def summarize_document_text(text: str) -> DocSummary:
    raw = _llm_complete(text)
    try:
        data = json.loads(raw)
        return DocSummary(summary=data["summary"], key_terms=list(data["key_terms"])[:5])
    except Exception as e:
        logger.warning("summarize failed: %s", e)
        return DocSummary(summary="Summary unavailable.", key_terms=[])
```

- [ ] **Step 4: Run — pass**

Run: `cd backend && pytest tests/test_document_summarizer.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/core/documents/summarizer.py backend/tests/test_document_summarizer.py
git commit -m "feat(docs): add document summarizer module"
```

---

### Task 19: Hook auto-summary into upload pipeline

**Files:**
- Modify: `backend/api/documents.py`
- Test: `backend/tests/test_upload_triggers_summary.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_upload_triggers_summary.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.db.database import SessionLocal
from backend.db.models import Document

client = TestClient(app)

def test_upload_enqueues_summary(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("This is a short UAE VAT compliance brief.")
    with patch("backend.api.documents.summarize_document_text") as m:
        m.return_value.summary = "A UAE VAT brief."
        m.return_value.key_terms = ["VAT", "UAE", "compliance", "tax", "brief"]
        with open(p, "rb") as f:
            r = client.post("/api/documents/upload", files={"file": ("a.txt", f, "text/plain")})
    assert r.status_code == 200
    doc_id = r.json()["document_id"]
    with SessionLocal() as s:
        d = s.get(Document, doc_id)
        assert d.summary == "A UAE VAT brief."
        assert d.key_terms == ["VAT", "UAE", "compliance", "tax", "brief"]
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Wire summarizer after ingestion**

```python
# backend/api/documents.py (in upload handler, after successful ingestion)
from backend.core.documents.summarizer import summarize_document_text

text = extracted_text  # whatever variable holds post-OCR/parsed text
try:
    summ = summarize_document_text(text)
    doc.summary = summ.summary
    doc.key_terms = summ.key_terms
    s.commit()
except Exception:
    pass  # do not fail upload on summarizer error
```

For large files, move into a background task (FastAPI `BackgroundTasks`) instead of blocking the response.

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Commit**

```bash
git add backend/api/documents.py backend/tests/test_upload_triggers_summary.py
git commit -m "feat(docs): auto-summary on upload"
```

---

### Task 20: Auditor agent module

**Files:**
- Create: `backend/core/chat/auditor_agent.py`
- Test: `backend/tests/test_auditor_agent.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_auditor_agent.py
from unittest.mock import patch
from backend.core.chat.auditor_agent import run_audit

def test_audit_returns_expected_shape():
    with patch("backend.core.chat.auditor_agent._analyze_documents") as m:
        m.return_value = {
            "risk_flags": [{"severity": "high", "document": "d1", "finding": "x"}],
            "anomalies": [],
            "compliance_gaps": [],
            "summary": "...",
        }
        out = run_audit(document_ids=["d1"])
    assert "risk_flags" in out and "summary" in out
    assert isinstance(out["risk_flags"], list)
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```python
# backend/core/chat/auditor_agent.py
from backend.core.audit_studio.risk_classifier import classify_risks  # reuse existing

def _analyze_documents(document_ids: list[str]) -> dict:
    return classify_risks(document_ids)

def run_audit(document_ids: list[str]) -> dict:
    if not document_ids:
        return {
            "risk_flags": [],
            "anomalies": [],
            "compliance_gaps": [],
            "summary": "No documents selected.",
        }
    return _analyze_documents(document_ids)
```

> If `classify_risks` has a different import path in the codebase, fix to match. The point is to reuse the existing audit wizard classifier.

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Commit**

```bash
git add backend/core/chat/auditor_agent.py backend/tests/test_auditor_agent.py
git commit -m "feat(legal-studio): auditor agent reusing audit wizard classifier"
```

---

### Task 21: Auditor endpoint

**Files:**
- Modify: `backend/api/chat.py`
- Test: `backend/tests/test_auditor_endpoint.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_auditor_endpoint.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_auditor_endpoint_returns_structured_result():
    with patch("backend.api.chat.run_audit") as m:
        m.return_value = {
            "risk_flags": [], "anomalies": [], "compliance_gaps": [], "summary": "ok"
        }
        r = client.post("/api/chat/auditor", json={"document_ids": ["d1"]})
    assert r.status_code == 200
    body = r.json()
    for k in ("risk_flags", "anomalies", "compliance_gaps", "summary"):
        assert k in body
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```python
# backend/api/chat.py additions
from backend.core.chat.auditor_agent import run_audit

class AuditorReq(BaseModel):
    document_ids: list[str]

@router.post("/auditor")
def auditor(req: AuditorReq):
    return run_audit(req.document_ids)
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Commit**

```bash
git add backend/api/chat.py backend/tests/test_auditor_endpoint.py
git commit -m "feat(legal-studio): /api/chat/auditor endpoint"
```

---

### Task 22: Finance-from-legal session endpoint

**Files:**
- Modify: `backend/api/sessions.py` (create if absent)
- Test: `backend/tests/test_finance_from_legal.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_finance_from_legal.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_create_finance_from_legal_returns_session_id():
    r = client.post("/api/sessions/finance-from-legal",
                    json={"question": "Compute DSCR", "thread_id": "t1", "document_ids": ["d1"]})
    assert r.status_code == 201
    body = r.json()
    assert "session_id" in body
    assert body["from_legal_thread"] == "t1"
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement endpoint**

```python
# backend/api/sessions.py
from fastapi import APIRouter
from pydantic import BaseModel
import uuid
from backend.db.database import SessionLocal
from backend.db.models import FinanceSession  # create model if not present

router = APIRouter(prefix="/api/sessions")

class FromLegalReq(BaseModel):
    question: str
    thread_id: str | None = None
    document_ids: list[str] = []

@router.post("/finance-from-legal", status_code=201)
def finance_from_legal(req: FromLegalReq):
    session_id = str(uuid.uuid4())
    with SessionLocal() as s:
        fs = FinanceSession(
            id=session_id,
            initial_question=req.question,
            from_legal_thread=req.thread_id,
            document_ids=req.document_ids,
        )
        s.add(fs); s.commit()
    return {"session_id": session_id, "from_legal_thread": req.thread_id}
```

> If `FinanceSession` model does not exist, add minimal fields (id, initial_question, from_legal_thread, document_ids JSON, created_at). Include in migration.

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Wire route into main app**

Add `app.include_router(sessions_router)` in `backend/main.py`.

- [ ] **Step 6: Commit**

```bash
git add backend/api/sessions.py backend/db/models.py backend/db/migrations/ backend/main.py backend/tests/test_finance_from_legal.py
git commit -m "feat(sessions): finance-from-legal handoff endpoint"
```

---

### Task 23: SourcesSidebar component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx`

- [ ] **Step 1: Implement**

```tsx
// frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx
import { useRef } from "react";

export interface SourceDoc {
  id: string;
  filename: string;
  summary?: string;
  key_terms?: string[];
  source: string;           // "upload" | "research"
  status?: "uploading" | "processing" | "summarizing" | "ready" | "error";
}

interface Props {
  docs: SourceDoc[];
  selectedIds: string[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onUpload: (files: FileList) => void;
  onPreview: (id: string) => void;
}

export function SourcesSidebar(p: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  return (
    <aside className="w-[260px] border-r border-slate-800 flex flex-col">
      <div className="p-3 border-b border-slate-800">
        <input
          ref={fileRef}
          type="file"
          multiple
          className="hidden"
          onChange={e => e.target.files && p.onUpload(e.target.files)}
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="w-full px-3 py-2 rounded bg-violet-600 text-white text-sm"
        >
          + Upload (multi-select)
        </button>
      </div>
      <ul className="flex-1 overflow-auto">
        {p.docs.map(d => (
          <li key={d.id} className="p-3 border-b border-slate-800 flex gap-2">
            <input
              type="checkbox"
              checked={p.selectedIds.includes(d.id)}
              onChange={() => p.onSelect(d.id)}
              aria-label={`Select ${d.filename}`}
            />
            <div className="flex-1 min-w-0">
              <button onClick={() => p.onPreview(d.id)} className="text-left w-full">
                <div className="truncate text-sm text-white">{d.filename}</div>
                {d.status && d.status !== "ready" && (
                  <div className="text-xs text-amber-400">{d.status}…</div>
                )}
                {d.summary && (
                  <div className="text-xs text-slate-400 line-clamp-3">{d.summary}</div>
                )}
                {d.key_terms && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {d.key_terms.map(k => (
                      <span key={k} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-200">{k}</span>
                    ))}
                  </div>
                )}
              </button>
            </div>
            <button onClick={() => p.onDelete(d.id)} className="text-slate-500 hover:text-red-400">✕</button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx
git commit -m "feat(legal-studio): add SourcesSidebar component"
```

---

### Task 24: PreviewPane component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/PreviewPane.tsx`

- [ ] **Step 1: Install pdfjs-dist if not present**

Run: `cd frontend && npm ls pdfjs-dist || npm install pdfjs-dist`

- [ ] **Step 2: Implement**

```tsx
// frontend/src/components/studios/LegalStudio/PreviewPane.tsx
import { useEffect, useState } from "react";

interface Props {
  docId: string | null;
  onClose: () => void;
}

export function PreviewPane({ docId, onClose }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!docId) { setUrl(null); return; }
    setUrl(`/api/documents/${docId}/file`);
  }, [docId]);
  if (!docId) return null;
  return (
    <aside className="w-[480px] border-l border-slate-800 flex flex-col">
      <div className="p-2 border-b border-slate-800 flex justify-between">
        <span className="text-sm text-white">Preview</span>
        <button onClick={onClose} className="text-slate-400 hover:text-white">✕</button>
      </div>
      <iframe src={url ?? ""} className="flex-1" title="preview" />
    </aside>
  );
}
```

> If the backend doesn't already serve `/api/documents/{id}/file`, add a FastAPI route returning the stored file. Keep content-type correct for PDFs.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/PreviewPane.tsx
git commit -m "feat(legal-studio): add PreviewPane component"
```

---

### Task 25: AuditorResultBubble component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/AuditorResultBubble.tsx`

- [ ] **Step 1: Implement**

```tsx
// frontend/src/components/studios/LegalStudio/AuditorResultBubble.tsx
interface Finding {
  severity: "low" | "medium" | "high";
  document: string;
  finding: string;
}

interface Props {
  risk_flags: Finding[];
  anomalies: Finding[];
  compliance_gaps: Finding[];
  summary: string;
}

function Section({ title, rows, color }: { title: string; rows: Finding[]; color: string }) {
  if (!rows.length) return null;
  return (
    <details open>
      <summary className={`text-sm font-medium ${color}`}>{title} ({rows.length})</summary>
      <ul className="list-disc pl-5 text-sm text-slate-200">
        {rows.map((r, i) => (
          <li key={i}>
            <span className="uppercase text-xs opacity-70">{r.severity}</span> — {r.document}: {r.finding}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function AuditorResultBubble(p: Props) {
  return (
    <div className="rounded-md bg-slate-800 p-3 space-y-2 text-slate-100">
      <div className="text-xs text-slate-400">🔎 Auditor report</div>
      <div className="text-sm">{p.summary}</div>
      <Section title="Risk Flags" rows={p.risk_flags} color="text-red-400" />
      <Section title="Anomalies" rows={p.anomalies} color="text-amber-400" />
      <Section title="Compliance Gaps" rows={p.compliance_gaps} color="text-violet-300" />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/AuditorResultBubble.tsx
git commit -m "feat(legal-studio): add AuditorResultBubble component"
```

---

### Task 26: Legal Studio 3-pane layout rework

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/ChatInput.tsx`

- [ ] **Step 1: Rewrite layout**

```tsx
// LegalStudio.tsx (top-level layout)
return (
  <div className="flex h-full">
    <SourcesSidebar
      docs={docs}
      selectedIds={selectedIds}
      onSelect={toggleSelect}
      onDelete={deleteDoc}
      onUpload={uploadFiles}
      onPreview={id => setPreviewId(id)}
    />
    <main className="flex-1 flex flex-col min-w-0">
      <ChatMessages messages={messages} />
      <ChatInput
        value={input}
        onChange={setInput}
        onSubmit={send}
        mode={mode}
        onModeChange={setMode}
        domainOverride={override}
        onDomainOverrideChange={setOverride}
        selectedDocCount={selectedIds.length}
      />
    </main>
    <PreviewPane docId={previewId} onClose={() => setPreviewId(null)} />
  </div>
);
```

- [ ] **Step 2: Add context badge in ChatInput**

```tsx
{p.selectedDocCount > 0 && (
  <div className="text-xs text-slate-400 mb-1">📎 {p.selectedDocCount} docs in context</div>
)}
```

- [ ] **Step 3: Multi-upload implementation**

```tsx
const uploadFiles = async (files: FileList) => {
  await Promise.all(Array.from(files).map(async f => {
    const fd = new FormData();
    fd.append("file", f);
    const r = await fetch("/api/documents/upload", { method: "POST", body: fd });
    if (r.ok) refreshSources();
  }));
};
```

- [ ] **Step 4: Include selected doc ids in send**

```tsx
await fetch("/api/chat/send_message", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: input,
    mode,
    domain_override: override,
    selected_document_ids: selectedIds,
  }),
});
```

- [ ] **Step 5: Manual verify**

- 3 panes render; dragging a PDF into sidebar uploads it; summary appears after a moment; checkbox selects; badge "📎 N docs in context" updates; send uses filtered RAG.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx frontend/src/components/studios/LegalStudio/ChatInput.tsx
git commit -m "feat(legal-studio): 3-pane layout, multi-upload, context wiring"
```

---

### Task 27: Auditor button wiring

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

- [ ] **Step 1: Add toolbar button above chat input**

```tsx
<button
  disabled={selectedIds.length === 0}
  onClick={runAuditor}
  className="px-3 py-1.5 rounded bg-amber-600 text-white text-sm disabled:opacity-40"
>
  🔎 Auditor {selectedIds.length > 0 ? `(${selectedIds.length})` : ""}
</button>
```

- [ ] **Step 2: Handler**

```tsx
const runAuditor = async () => {
  const r = await fetch("/api/chat/auditor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: selectedIds }),
  });
  const body = await r.json();
  appendMessage({ type: "auditor", result: body });
};
```

- [ ] **Step 3: Render `<AuditorResultBubble>` when message type is "auditor"**

- [ ] **Step 4: Manual verify**

Select 1+ docs → Auditor enabled → click → structured result bubble appears.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx frontend/src/components/studios/LegalStudio/ChatMessages.tsx
git commit -m "feat(legal-studio): wire Auditor button + result bubble"
```

---

### Task 28: Analyst mode handoff

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- Modify: `frontend/src/components/studios/FinanceStudio/FinanceStudio.tsx`

- [ ] **Step 1: Legal side — when mode=analyst, redirect**

```tsx
if (mode === "analyst") {
  const r = await fetch("/api/sessions/finance-from-legal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: input,
      thread_id: threadId,
      document_ids: selectedIds,
    }),
  });
  const { session_id } = await r.json();
  navigate(`/finance-studio?session=${session_id}`);
  return;
}
```

- [ ] **Step 2: Finance side — accept session param**

In `FinanceStudio.tsx`, on mount:

```tsx
const params = new URLSearchParams(location.search);
const sessionId = params.get("session");
useEffect(() => {
  if (!sessionId) return;
  fetch(`/api/sessions/${sessionId}`)
    .then(r => r.json())
    .then(s => {
      setInitialQuestion(s.initial_question);
      setLegalBreadcrumb(s.from_legal_thread);
      prefillWorkflowWithDocs(s.document_ids);
    });
}, [sessionId]);
```

- [ ] **Step 3: Backend GET /api/sessions/{id}**

```python
@router.get("/{session_id}")
def get_session(session_id: str):
    with SessionLocal() as s:
        fs = s.get(FinanceSession, session_id)
        if fs is None:
            raise HTTPException(404, "not found")
        return {
            "session_id": fs.id,
            "initial_question": fs.initial_question,
            "from_legal_thread": fs.from_legal_thread,
            "document_ids": fs.document_ids,
        }
```

- [ ] **Step 4: Render breadcrumb in Finance Studio**

```tsx
{legalBreadcrumb && (
  <a href={`/legal-studio?thread=${legalBreadcrumb}`} className="text-xs text-violet-300">
    ← Back to Legal chat
  </a>
)}
```

- [ ] **Step 5: Manual verify**

In Legal Studio pick Analyst + send → Finance Studio opens, question pre-filled, breadcrumb visible; clicking breadcrumb returns to the Legal thread.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx frontend/src/components/studios/FinanceStudio/FinanceStudio.tsx backend/api/sessions.py
git commit -m "feat(sessions): analyst mode handoff Legal → Finance"
```

---

### Task 29: Full button audit

**Files:**
- Modify: every file under `frontend/src/components/studios/LegalStudio/` with interactive elements.

- [ ] **Step 1: Enumerate**

Run: `grep -rn "onClick\|onSubmit\|onChange" frontend/src/components/studios/LegalStudio/`

Build a checklist of every element. Include in a scratch note.

- [ ] **Step 2: Verify each**

For each item:
- Confirm handler is defined and imported.
- Call a real API or set real state — no `console.log` / no-op.
- Add a visible feedback path (toast, spinner, disabled-during-request).

- [ ] **Step 3: Manual test every button**

Walk the UI; click each button; verify state changes / network calls fire.

- [ ] **Step 4: Commit per logical group**

```bash
git add <group-files>
git commit -m "fix(legal-studio): wire previously-broken buttons (<summary>)"
```

Repeat until the checklist is clean.

### Phase 3 Gate

- [ ] Backend tests all green.
- [ ] Manual walkthrough: upload → summary visible → select → chat uses context → auditor works → analyst redirects → preview pane opens and closes → all buttons respond.
- [ ] Tag: `git tag phase-3-bundle-c`.

---

## Phase 4 — Bundle D: Template Studio Preview

Add preview modal with Sample Output + Structure tabs; auto-open after upload.

### Task 30: Sample fixture JSON

**Files:**
- Create: `backend/core/templates/sample_fixture.json`

- [ ] **Step 1: Write fixture**

```json
{
  "version": 1,
  "company": {
    "name": "Sample Trading LLC",
    "trn": "100000000000003",
    "license_no": "CN-1234567",
    "address": "Office 12, Sample Tower, Dubai, UAE"
  },
  "period": "2025",
  "trial_balance": [
    {"account": "Cash and Bank", "debit": 150000, "credit": 0},
    {"account": "Accounts Receivable", "debit": 75000, "credit": 0},
    {"account": "Inventory", "debit": 60000, "credit": 0},
    {"account": "Accounts Payable", "debit": 0, "credit": 40000},
    {"account": "Revenue", "debit": 0, "credit": 300000},
    {"account": "Cost of Sales", "debit": 180000, "credit": 0},
    {"account": "Operating Expenses", "debit": 45000, "credit": 0},
    {"account": "Retained Earnings", "debit": 0, "credit": 170000}
  ],
  "balance_sheet": {
    "total_assets": 285000,
    "total_liabilities": 40000,
    "total_equity": 245000
  },
  "profit_loss": {
    "revenue": 300000,
    "cost_of_sales": 180000,
    "gross_profit": 120000,
    "operating_expenses": 45000,
    "net_profit": 75000
  },
  "opinion_text": "In our opinion, the financial statements present fairly, in all material respects, the financial position of Sample Trading LLC as at 31 December 2025 and its financial performance for the year then ended."
}
```

- [ ] **Step 2: Commit**

```bash
git add backend/core/templates/sample_fixture.json
git commit -m "feat(templates): sample fixture for preview rendering"
```

---

### Task 31: Sample render function

**Files:**
- Modify: `backend/core/templates/renderer.py` (create if absent)
- Test: `backend/tests/test_template_sample_render.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_template_sample_render.py
from backend.core.templates.renderer import render_sample

def test_sample_render_returns_pdf_bytes():
    pdf = render_sample(template_id="test-template-1")
    assert pdf[:4] == b"%PDF"
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```python
# backend/core/templates/renderer.py (add or extend)
import json
from pathlib import Path
from functools import lru_cache
from backend.core.templates.engine import apply_template  # existing

_FIXTURE = Path(__file__).parent / "sample_fixture.json"

def _load_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))

@lru_cache(maxsize=128)
def render_sample(template_id: str) -> bytes:
    fixture = _load_fixture()
    return apply_template(template_id, data=fixture, output_format="pdf")
```

> `apply_template` must exist in the codebase (template engine); wire to real signature. If it returns a path, read bytes.

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Commit**

```bash
git add backend/core/templates/renderer.py backend/tests/test_template_sample_render.py
git commit -m "feat(templates): render_sample with fixture-cached output"
```

---

### Task 32: Structure analyzer

**Files:**
- Create: `backend/core/templates/structure_analyzer.py`
- Test: `backend/tests/test_template_structure_analyzer.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_template_structure_analyzer.py
from backend.core.templates.structure_analyzer import extract_placeholders

def test_extract_returns_pages_and_boxes():
    out = extract_placeholders("test-template-1")
    assert "pages" in out and isinstance(out["pages"], list)
    assert all("image_url" in p and "placeholders" in p for p in out["pages"])
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```python
# backend/core/templates/structure_analyzer.py
from backend.core.templates.storage import get_template_pages  # existing helper

def extract_placeholders(template_id: str) -> dict:
    pages = get_template_pages(template_id)  # returns list of {image_url, placeholders:[{type, bbox}]}
    return {"pages": pages}
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Commit**

```bash
git add backend/core/templates/structure_analyzer.py backend/tests/test_template_structure_analyzer.py
git commit -m "feat(templates): structure analyzer returning placeholder map"
```

---

### Task 33: Template preview endpoints

**Files:**
- Modify: `backend/api/templates.py`
- Test: `backend/tests/test_template_endpoints.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_template_endpoints.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_sample_render_returns_pdf():
    with patch("backend.api.templates.render_sample", return_value=b"%PDF-1.4\n..."):
        r = client.get("/api/templates/t1/sample-render")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"

def test_structure_endpoint_returns_pages():
    with patch("backend.api.templates.extract_placeholders",
               return_value={"pages": [{"image_url": "x", "placeholders": []}]}):
        r = client.get("/api/templates/t1/structure")
    assert r.status_code == 200
    body = r.json()
    assert body["pages"][0]["image_url"] == "x"
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Implement**

```python
# backend/api/templates.py
from fastapi.responses import Response
from backend.core.templates.renderer import render_sample
from backend.core.templates.structure_analyzer import extract_placeholders

@router.get("/{template_id}/sample-render")
def sample_render(template_id: str):
    pdf = render_sample(template_id)
    return Response(content=pdf, media_type="application/pdf")

@router.get("/{template_id}/structure")
def structure(template_id: str):
    return extract_placeholders(template_id)
```

- [ ] **Step 4: Run — pass**

- [ ] **Step 5: Commit**

```bash
git add backend/api/templates.py backend/tests/test_template_endpoints.py
git commit -m "feat(templates): sample-render and structure endpoints"
```

---

### Task 34: TemplatePreviewModal component

**Files:**
- Create: `frontend/src/components/studios/TemplateStudio/TemplatePreviewModal.tsx`

- [ ] **Step 1: Implement**

```tsx
// frontend/src/components/studios/TemplateStudio/TemplatePreviewModal.tsx
import { useState } from "react";

interface Placeholder { type: string; bbox: [number, number, number, number] }
interface PageInfo { image_url: string; placeholders: Placeholder[] }

const COLORS: Record<string, string> = {
  company_name: "rgba(59,130,246,0.35)",
  tb_row: "rgba(34,197,94,0.35)",
  opinion_text: "rgba(168,85,247,0.35)",
};

interface Props {
  templateId: string;
  open: boolean;
  onClose: () => void;
  onSend?: () => void;
  onDelete?: () => void;
}

export function TemplatePreviewModal({ templateId, open, onClose, onSend, onDelete }: Props) {
  const [tab, setTab] = useState<"sample" | "structure">("sample");
  const [structure, setStructure] = useState<PageInfo[] | null>(null);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center">
      <div className="w-[80vw] h-[85vh] bg-slate-900 rounded-lg flex flex-col">
        <header className="flex items-center justify-between p-3 border-b border-slate-800">
          <h2 className="text-white text-sm">Template Preview</h2>
          <div className="flex gap-2">
            {onSend && <button onClick={onSend} className="px-2 py-1 rounded bg-violet-600 text-white text-xs">Send</button>}
            {onDelete && <button onClick={onDelete} className="px-2 py-1 rounded bg-red-600 text-white text-xs">Delete</button>}
            <button onClick={onClose} className="px-2 py-1 text-slate-400 hover:text-white">✕</button>
          </div>
        </header>
        <nav className="flex gap-1 px-3 border-b border-slate-800">
          <button
            onClick={() => setTab("sample")}
            className={`px-3 py-2 text-sm ${tab === "sample" ? "text-white border-b-2 border-violet-500" : "text-slate-400"}`}
          >Sample Output</button>
          <button
            onClick={() => { setTab("structure"); if (!structure) loadStructure(); }}
            className={`px-3 py-2 text-sm ${tab === "structure" ? "text-white border-b-2 border-violet-500" : "text-slate-400"}`}
          >Structure</button>
        </nav>
        <section className="flex-1 min-h-0">
          {tab === "sample" ? (
            <iframe src={`/api/templates/${templateId}/sample-render`} className="w-full h-full" title="sample" />
          ) : (
            <StructureView pages={structure} colors={COLORS} />
          )}
        </section>
      </div>
    </div>
  );

  async function loadStructure() {
    const r = await fetch(`/api/templates/${templateId}/structure`);
    const body = await r.json();
    setStructure(body.pages);
  }
}

function StructureView({ pages, colors }: { pages: PageInfo[] | null; colors: Record<string, string> }) {
  if (!pages) return <div className="p-6 text-slate-400">Loading…</div>;
  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-auto">
        {pages.map((p, idx) => (
          <div key={idx} className="relative inline-block m-4">
            <img src={p.image_url} alt={`page ${idx+1}`} />
            {p.placeholders.map((ph, i) => (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: ph.bbox[0], top: ph.bbox[1],
                  width: ph.bbox[2]-ph.bbox[0], height: ph.bbox[3]-ph.bbox[1],
                  background: colors[ph.type] ?? "rgba(255,255,255,0.2)",
                }}
                title={ph.type}
              />
            ))}
          </div>
        ))}
      </div>
      <aside className="w-[200px] p-3 border-l border-slate-800 text-xs text-slate-200 space-y-1">
        <div className="font-medium mb-2">Legend</div>
        {Object.entries(colors).map(([k, v]) => (
          <div key={k} className="flex items-center gap-2">
            <span style={{ background: v, width: 14, height: 14, display: "inline-block", border: "1px solid #444" }} />
            <span>{k}</span>
          </div>
        ))}
      </aside>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/TemplateStudio/TemplatePreviewModal.tsx
git commit -m "feat(template-studio): add TemplatePreviewModal with 2 tabs"
```

---

### Task 35: Wire eye icon + auto-open after upload

**Files:**
- Modify: `frontend/src/components/studios/TemplateStudio/TemplateStudio.tsx`

- [ ] **Step 1: Add state + handlers**

```tsx
const [previewId, setPreviewId] = useState<string | null>(null);
const openPreview = (id: string) => setPreviewId(id);
const closePreview = () => setPreviewId(null);
```

- [ ] **Step 2: Wire eye button**

```tsx
<button onClick={() => openPreview(row.id)} aria-label="Preview template" className="...">👁</button>
```

- [ ] **Step 3: After upload completes, auto-open**

```tsx
const afterUpload = (newTemplate: { id: string }) => {
  refreshTemplates();
  openPreview(newTemplate.id);
};
```

- [ ] **Step 4: Render modal**

```tsx
{previewId && (
  <TemplatePreviewModal
    templateId={previewId}
    open={true}
    onClose={closePreview}
    onDelete={async () => { await deleteTemplate(previewId); closePreview(); }}
    onSend={() => sendTemplate(previewId)}
  />
)}
```

- [ ] **Step 5: Manual verify**

- Upload a template → modal auto-opens with Sample Output tab.
- Click Structure → page images with colored overlays.
- Close + click eye icon in table row → same modal reopens.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/studios/TemplateStudio/TemplateStudio.tsx
git commit -m "feat(template-studio): eye icon + auto-open preview modal"
```

### Phase 4 Gate

- [ ] Backend tests green: `cd backend && pytest tests/test_template_sample_render.py tests/test_template_structure_analyzer.py tests/test_template_endpoints.py -v`
- [ ] Manual: upload a template → modal auto-opens; Sample Output renders; Structure shows.
- [ ] Tag: `git tag phase-4-bundle-d`.

---

## Final Verification

- [ ] `cd backend && pytest -v` — full suite green.
- [ ] `cd frontend && npm run build` — clean build.
- [ ] Walk entire Legal Studio flow (Normal / Deep Research / Analyst + Auditor + Preview + Button audit).
- [ ] Walk entire Template Studio flow (upload → modal → both tabs → eye reopen).
- [ ] Tag: `git tag implementation-complete`.

## Notes for the Implementing Engineer

- The codebase already has an `LLMManager`, `RAGEngine`, audit risk classifier, document ingestion pipeline, and prompt router. Reuse them. If a helper (like `LLMManager.get_fast_model()`) doesn't exist, add the thinnest possible accessor — do not reinvent the provider layer.
- Keep frontend component files focused. If one grows past ~250 lines, consider splitting a sub-component out, following the same naming convention used elsewhere in `studios/`.
- Every task ends with a commit. Small commits > large commits.
- If a test is flaky against a real LLM, gate it behind `RUN_LLM_TESTS=1` like the accuracy fixture does.
- Error handling is defined per-bundle in the spec (§11). Do not add speculative try/except beyond what the spec requires.

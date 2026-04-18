# NotebookLM-Style Finance Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing `FinancialStudio` wizard and `AuditProfileStudio` tabs with a single three-panel NotebookLM-style Finance Studio that combines source docs, AI chat, live report preview, exports, and profile versioning.

**Architecture:** Backend-owned versioning + chat + generation (new `audit_studio` API group, 3 new DB models). Modular frontend under `frontend/src/components/studios/FinanceStudio/` using a `FinanceStudioContext` for shared state across SourceDocsSidebar, AuditChat, ReportPreview, and ExportsPanel.

**Tech Stack:** Python 3.10 + FastAPI + SQLAlchemy (backend); React + Vite + TypeScript + glassmorphism/dark CSS (frontend); pytest (backend tests); vitest + React Testing Library (frontend tests).

**Spec:** `docs/superpowers/specs/2026-04-19-notebooklm-finance-studio-design.md`

**Execution order:** Phases 1–4 build and verify the backend so the frontend (Phases 5–11) has real endpoints to hit. Phase 12 is the end-to-end integration test.

---

## File Structure

### Backend — new / modified

| Path | Responsibility |
|------|----------------|
| `backend/db/models.py` (modify) | Add `ProfileVersion`, `AuditChatMessage`, `GeneratedOutput` ORM models |
| `backend/api/audit_studio.py` (create) | All new endpoints: versions, chat, generate, outputs |
| `backend/main.py` (modify) | Register new router |
| `backend/core/audit_studio/versioning.py` (create) | Branch / compare / activate logic |
| `backend/core/audit_studio/chat_service.py` (create) | Chat → LLM with source citations |
| `backend/core/audit_studio/generation_service.py` (create) | Dispatch generation per output_type to existing generators |
| `backend/tests/test_audit_studio_versions.py` (create) | Branch / compare / activate tests |
| `backend/tests/test_audit_studio_chat.py` (create) | Chat send / history / clear tests |
| `backend/tests/test_audit_studio_generate.py` (create) | Generate each output type + download tests |
| `backend/tests/test_audit_studio_integration.py` (create) | End-to-end flow |

### Frontend — new

```
frontend/src/components/studios/FinanceStudio/
├── FinanceStudio.tsx
├── FinanceStudio.css
├── FinanceStudioContext.tsx
├── types.ts
├── api.ts
├── SourceDocsSidebar/
│   ├── SourceDocsSidebar.tsx
│   ├── DocumentCard.tsx
│   ├── LearnedProfileTree.tsx
│   └── VersionSwitcher.tsx
├── AuditChat/
│   ├── AuditChat.tsx
│   ├── ChatMessage.tsx
│   ├── SuggestedActions.tsx
│   └── WorkflowSteps.tsx
├── ReportPreview/
│   ├── ReportPreview.tsx
│   └── PreviewPage.tsx
└── ExportsPanel/
    ├── ExportsPanel.tsx
    ├── ExportCard.tsx
    ├── FormatPicker.tsx
    └── VersionCompare.tsx
```

### Frontend — deleted / modified

- Delete: `frontend/src/components/studios/FinancialStudio/` (15 files)
- Delete: `frontend/src/components/studios/AuditProfileStudio/AuditProfileStudio.tsx`
- Modify: `frontend/src/context/StudioProvider.tsx` — replace `'financial' | 'profiles'` with `'finance'`
- Modify: `frontend/src/components/StudioSwitcher.tsx` — single "Finance" icon
- Modify: `frontend/src/App.tsx` — route `'finance'` to `<FinanceStudio />`

---

## Conventions Used In Every Task

- **TDD loop** (backend): write failing test → run to confirm failure → write minimal impl → run to confirm pass → commit.
- **Run backend tests:** `cd backend && uv run pytest <path> -v`
- **Run frontend tests:** `cd frontend && npm test -- <path>`
- **Run backend server (dev):** `cd backend && uv run python main.py`
- **Run frontend server (dev):** `cd frontend && npm run dev`
- **Type-check frontend:** `cd frontend && npm run build` (fails on TS errors)
- **Commit granularity:** one commit per task (at the end of the task's steps). Never bundle.

---

# PHASE 1 — DB Models & Migration

## Task 1: Add `ProfileVersion` model

**Files:**
- Modify: `backend/db/models.py` (append to end of file)
- Test: `backend/tests/test_audit_studio_versions.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_audit_studio_versions.py`:

```python
import pytest
from db.database import AsyncSessionLocal
from db.models import AuditProfile, ProfileVersion
from sqlalchemy import select


@pytest.mark.asyncio
async def test_profile_version_persists():
    async with AsyncSessionLocal() as s:
        profile = AuditProfile(id="p1", name="Test Co")
        s.add(profile)
        await s.flush()
        v = ProfileVersion(
            profile_id="p1",
            branch_name="main",
            profile_json='{"account_mappings": []}',
            is_current=True,
        )
        s.add(v)
        await s.commit()
        row = (await s.execute(select(ProfileVersion).where(ProfileVersion.profile_id == "p1"))).scalar_one()
        assert row.branch_name == "main"
        assert row.is_current is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py::test_profile_version_persists -v`
Expected: FAIL with `ImportError: cannot import name 'ProfileVersion'`

- [ ] **Step 3: Add the model**

Append to `backend/db/models.py` (before the final blank line):

```python
class ProfileVersion(Base):
    __tablename__ = "profile_versions"

    id = Column(String(36), primary_key=True, default=_new_id)
    profile_id = Column(String(36), ForeignKey("audit_profiles.id"), nullable=False)
    branch_name = Column(String(255), nullable=False)
    profile_json = Column(Text, nullable=False)
    is_current = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py::test_profile_version_persists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py backend/tests/test_audit_studio_versions.py
git commit -m "feat(db): add ProfileVersion model for audit profile branching"
```

---

## Task 2: Add `AuditChatMessage` model

**Files:**
- Modify: `backend/db/models.py`
- Test: `backend/tests/test_audit_studio_chat.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_audit_studio_chat.py`:

```python
import pytest
from db.database import AsyncSessionLocal
from db.models import AuditProfile, AuditChatMessage
from sqlalchemy import select


@pytest.mark.asyncio
async def test_audit_chat_message_persists():
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p2", name="Test Co"))
        await s.flush()
        m = AuditChatMessage(
            profile_id="p2",
            role="user",
            content="Flag anomalies",
            citations='[{"doc_id":"d1","page":3}]',
        )
        s.add(m)
        await s.commit()
        row = (await s.execute(select(AuditChatMessage).where(AuditChatMessage.profile_id == "p2"))).scalar_one()
        assert row.role == "user"
        assert "d1" in row.citations
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_chat.py::test_audit_chat_message_persists -v`
Expected: FAIL with `ImportError: cannot import name 'AuditChatMessage'`

- [ ] **Step 3: Add the model**

Append to `backend/db/models.py`:

```python
class AuditChatMessage(Base):
    __tablename__ = "audit_chat_messages"

    id = Column(String(36), primary_key=True, default=_new_id)
    profile_id = Column(String(36), ForeignKey("audit_profiles.id"), nullable=False)
    version_id = Column(String(36), ForeignKey("profile_versions.id"), nullable=True)
    role = Column(String(20), nullable=False)      # user | assistant
    content = Column(Text, nullable=False)
    citations = Column(Text, nullable=True)        # JSON string
    created_at = Column(DateTime, default=_utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_chat.py::test_audit_chat_message_persists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py backend/tests/test_audit_studio_chat.py
git commit -m "feat(db): add AuditChatMessage model"
```

---

## Task 3: Add `GeneratedOutput` model

**Files:**
- Modify: `backend/db/models.py`
- Test: `backend/tests/test_audit_studio_generate.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_audit_studio_generate.py`:

```python
import pytest
from db.database import AsyncSessionLocal
from db.models import AuditProfile, GeneratedOutput
from sqlalchemy import select


@pytest.mark.asyncio
async def test_generated_output_persists():
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p3", name="Test Co"))
        await s.flush()
        o = GeneratedOutput(
            profile_id="p3",
            output_type="audit_report",
            status="pending",
        )
        s.add(o)
        await s.commit()
        row = (await s.execute(select(GeneratedOutput).where(GeneratedOutput.profile_id == "p3"))).scalar_one()
        assert row.output_type == "audit_report"
        assert row.status == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_generate.py::test_generated_output_persists -v`
Expected: FAIL with `ImportError: cannot import name 'GeneratedOutput'`

- [ ] **Step 3: Add the model**

Append to `backend/db/models.py`:

```python
class GeneratedOutput(Base):
    __tablename__ = "generated_outputs"

    id = Column(String(36), primary_key=True, default=_new_id)
    profile_id = Column(String(36), ForeignKey("audit_profiles.id"), nullable=False)
    version_id = Column(String(36), ForeignKey("profile_versions.id"), nullable=True)
    output_type = Column(String(50), nullable=False)   # audit_report | profit_loss | ...
    template_id = Column(String(36), ForeignKey("templates.id"), nullable=True)
    status = Column(String(20), default="pending")     # pending|processing|ready|failed
    output_path = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_generate.py::test_generated_output_persists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py backend/tests/test_audit_studio_generate.py
git commit -m "feat(db): add GeneratedOutput model"
```

---

# PHASE 2 — Versioning Endpoints

## Task 4: Scaffold `audit_studio` router and register it

**Files:**
- Create: `backend/api/audit_studio.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_audit_studio_versions.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_audit_studio_versions.py`:

```python
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_audit_studio_router_mounted():
    async with AsyncClient(app=app, base_url="http://test") as c:
        r = await c.get("/api/audit-profiles/nonexistent/versions")
        # 404 is fine (profile missing); 404 from FastAPI itself (path not found) is NOT
        assert r.status_code in (404, 422)
        assert "path" not in (r.json().get("detail") or [{}])[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py::test_audit_studio_router_mounted -v`
Expected: FAIL — 404 "Not Found" for path (router not mounted).

- [ ] **Step 3: Create the router**

Create `backend/api/audit_studio.py`:

```python
"""
Audit Studio API — versioning, chat, generation.
Routes nest under each profile: /api/audit-profiles/{id}/...
"""
from fastapi import APIRouter, HTTPException
from db.database import AsyncSessionLocal
from db.models import AuditProfile
from sqlalchemy import select

router = APIRouter(prefix="/api/audit-profiles", tags=["audit-studio"])


async def _require_profile(profile_id: str) -> AuditProfile:
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(AuditProfile).where(AuditProfile.id == profile_id))).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        return row


@router.get("/{profile_id}/versions")
async def list_versions(profile_id: str):
    await _require_profile(profile_id)
    return {"versions": []}
```

Register in `backend/main.py`. Find the section where existing routers are included (search for `app.include_router(`) and add beside them:

```python
from api import audit_studio
app.include_router(audit_studio.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py::test_audit_studio_router_mounted -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/audit_studio.py backend/main.py backend/tests/test_audit_studio_versions.py
git commit -m "feat(audit-studio): scaffold router and list-versions stub"
```

---

## Task 5: Implement `list_versions` with real data

**Files:**
- Modify: `backend/api/audit_studio.py`
- Test: `backend/tests/test_audit_studio_versions.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit_studio_versions.py`:

```python
@pytest.mark.asyncio
async def test_list_versions_returns_all_for_profile():
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-list", name="X"))
        await s.flush()
        s.add(ProfileVersion(profile_id="p-list", branch_name="main", profile_json="{}", is_current=True))
        s.add(ProfileVersion(profile_id="p-list", branch_name="remap-4001", profile_json="{}"))
        await s.commit()
    async with AsyncClient(app=app, base_url="http://test") as c:
        r = await c.get("/api/audit-profiles/p-list/versions")
        assert r.status_code == 200
        data = r.json()
        names = {v["branch_name"] for v in data["versions"]}
        assert names == {"main", "remap-4001"}
        assert any(v["is_current"] for v in data["versions"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py::test_list_versions_returns_all_for_profile -v`
Expected: FAIL — response has empty `versions: []`.

- [ ] **Step 3: Implement query**

Replace the stub `list_versions` in `backend/api/audit_studio.py`:

```python
from db.models import ProfileVersion

@router.get("/{profile_id}/versions")
async def list_versions(profile_id: str):
    await _require_profile(profile_id)
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(ProfileVersion).where(ProfileVersion.profile_id == profile_id).order_by(ProfileVersion.created_at)
        )).scalars().all()
    return {"versions": [
        {"id": r.id, "branch_name": r.branch_name, "is_current": r.is_current, "created_at": r.created_at.isoformat()}
        for r in rows
    ]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/audit_studio.py backend/tests/test_audit_studio_versions.py
git commit -m "feat(audit-studio): implement GET /versions"
```

---

## Task 6: Implement `POST /branch`

**Files:**
- Create: `backend/core/audit_studio/__init__.py`
- Create: `backend/core/audit_studio/versioning.py`
- Modify: `backend/api/audit_studio.py`
- Test: `backend/tests/test_audit_studio_versions.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit_studio_versions.py`:

```python
@pytest.mark.asyncio
async def test_branch_creates_copy_and_returns_new_id():
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-branch", name="X"))
        await s.flush()
        s.add(ProfileVersion(
            id="v-main", profile_id="p-branch", branch_name="main",
            profile_json='{"account_mappings":[{"a":1}]}', is_current=True,
        ))
        await s.commit()
    async with AsyncClient(app=app, base_url="http://test") as c:
        r = await c.post("/api/audit-profiles/p-branch/branch", json={"branch_name": "remap-4001"})
        assert r.status_code == 200
        new_id = r.json()["version_id"]
        assert new_id != "v-main"
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(ProfileVersion).where(ProfileVersion.profile_id == "p-branch"))).scalars().all()
        assert len(rows) == 2
        new_row = next(r for r in rows if r.id == new_id)
        assert new_row.branch_name == "remap-4001"
        assert new_row.profile_json == '{"account_mappings":[{"a":1}]}'
        assert new_row.is_current is False  # main stays current
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py::test_branch_creates_copy_and_returns_new_id -v`
Expected: FAIL — 404 (route missing).

- [ ] **Step 3: Implement**

Create `backend/core/audit_studio/__init__.py` (empty file).

Create `backend/core/audit_studio/versioning.py`:

```python
"""Branching / compare / activate logic for audit profile versions."""
from sqlalchemy import select
from db.database import AsyncSessionLocal
from db.models import ProfileVersion


async def branch_version(profile_id: str, new_branch_name: str) -> str:
    """Copy the current version's profile_json into a new version row. Returns new version id."""
    async with AsyncSessionLocal() as s:
        current = (await s.execute(
            select(ProfileVersion).where(
                ProfileVersion.profile_id == profile_id,
                ProfileVersion.is_current == True,  # noqa: E712
            )
        )).scalar_one_or_none()
        if current is None:
            raise ValueError("No current version to branch from")
        new = ProfileVersion(
            profile_id=profile_id,
            branch_name=new_branch_name,
            profile_json=current.profile_json,
            is_current=False,
        )
        s.add(new)
        await s.commit()
        return new.id
```

Add to `backend/api/audit_studio.py`:

```python
from pydantic import BaseModel
from core.audit_studio.versioning import branch_version

class BranchRequest(BaseModel):
    branch_name: str

@router.post("/{profile_id}/branch")
async def branch(profile_id: str, req: BranchRequest):
    await _require_profile(profile_id)
    try:
        new_id = await branch_version(profile_id, req.branch_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"version_id": new_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/audit_studio/ backend/api/audit_studio.py backend/tests/test_audit_studio_versions.py
git commit -m "feat(audit-studio): POST /branch copies current version"
```

---

## Task 7: Implement `PATCH /versions/{id}/activate`

**Files:**
- Modify: `backend/core/audit_studio/versioning.py`
- Modify: `backend/api/audit_studio.py`
- Test: `backend/tests/test_audit_studio_versions.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit_studio_versions.py`:

```python
@pytest.mark.asyncio
async def test_activate_sets_only_one_current():
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-act", name="X"))
        await s.flush()
        s.add(ProfileVersion(id="v-a", profile_id="p-act", branch_name="main", profile_json="{}", is_current=True))
        s.add(ProfileVersion(id="v-b", profile_id="p-act", branch_name="alt",  profile_json="{}", is_current=False))
        await s.commit()
    async with AsyncClient(app=app, base_url="http://test") as c:
        r = await c.patch("/api/audit-profiles/p-act/versions/v-b/activate")
        assert r.status_code == 200
    async with AsyncSessionLocal() as s:
        rows = {r.id: r.is_current for r in (await s.execute(
            select(ProfileVersion).where(ProfileVersion.profile_id == "p-act")
        )).scalars().all()}
        assert rows == {"v-a": False, "v-b": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py::test_activate_sets_only_one_current -v`
Expected: FAIL — 404 route missing.

- [ ] **Step 3: Implement**

Append to `backend/core/audit_studio/versioning.py`:

```python
async def activate_version(profile_id: str, version_id: str) -> None:
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(ProfileVersion).where(ProfileVersion.profile_id == profile_id)
        )).scalars().all()
        target = next((r for r in rows if r.id == version_id), None)
        if target is None:
            raise ValueError("Version not found for this profile")
        for r in rows:
            r.is_current = (r.id == version_id)
        await s.commit()
```

Add to `backend/api/audit_studio.py`:

```python
from core.audit_studio.versioning import activate_version

@router.patch("/{profile_id}/versions/{version_id}/activate")
async def activate(profile_id: str, version_id: str):
    await _require_profile(profile_id)
    try:
        await activate_version(profile_id, version_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/audit_studio/versioning.py backend/api/audit_studio.py backend/tests/test_audit_studio_versions.py
git commit -m "feat(audit-studio): PATCH /versions/{id}/activate"
```

---

## Task 8: Implement `GET /versions/{v1}/compare/{v2}`

**Files:**
- Modify: `backend/core/audit_studio/versioning.py`
- Modify: `backend/api/audit_studio.py`
- Test: `backend/tests/test_audit_studio_versions.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit_studio_versions.py`:

```python
@pytest.mark.asyncio
async def test_compare_returns_json_diff():
    import json
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-cmp", name="X"))
        await s.flush()
        s.add(ProfileVersion(id="v1", profile_id="p-cmp", branch_name="main",
                             profile_json=json.dumps({"account_mappings": [{"acct": "4001", "group": "Rev"}]})))
        s.add(ProfileVersion(id="v2", profile_id="p-cmp", branch_name="alt",
                             profile_json=json.dumps({"account_mappings": [{"acct": "4001", "group": "Sales"}]})))
        await s.commit()
    async with AsyncClient(app=app, base_url="http://test") as c:
        r = await c.get("/api/audit-profiles/p-cmp/versions/v1/compare/v2")
        assert r.status_code == 200
        diff = r.json()
        assert "account_mappings" in diff["changed"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py::test_compare_returns_json_diff -v`
Expected: FAIL — route missing.

- [ ] **Step 3: Implement**

Append to `backend/core/audit_studio/versioning.py`:

```python
import json

async def compare_versions(profile_id: str, v1_id: str, v2_id: str) -> dict:
    async with AsyncSessionLocal() as s:
        rows = {r.id: r for r in (await s.execute(
            select(ProfileVersion).where(ProfileVersion.profile_id == profile_id)
        )).scalars().all()}
    if v1_id not in rows or v2_id not in rows:
        raise ValueError("One or both versions not found")
    a = json.loads(rows[v1_id].profile_json or "{}")
    b = json.loads(rows[v2_id].profile_json or "{}")
    changed, added, removed = {}, {}, {}
    for k in set(a) | set(b):
        if k not in a:
            added[k] = b[k]
        elif k not in b:
            removed[k] = a[k]
        elif a[k] != b[k]:
            changed[k] = {"before": a[k], "after": b[k]}
    return {"changed": changed, "added": added, "removed": removed}
```

Add to `backend/api/audit_studio.py`:

```python
from core.audit_studio.versioning import compare_versions

@router.get("/{profile_id}/versions/{v1_id}/compare/{v2_id}")
async def compare(profile_id: str, v1_id: str, v2_id: str):
    await _require_profile(profile_id)
    try:
        return await compare_versions(profile_id, v1_id, v2_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_versions.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/audit_studio/versioning.py backend/api/audit_studio.py backend/tests/test_audit_studio_versions.py
git commit -m "feat(audit-studio): GET /versions/{v1}/compare/{v2}"
```

---

# PHASE 3 — Chat Endpoints

## Task 9: Implement `POST /chat` (non-streaming first)

**Files:**
- Create: `backend/core/audit_studio/chat_service.py`
- Modify: `backend/api/audit_studio.py`
- Modify: `backend/tests/test_audit_studio_chat.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit_studio_chat.py`:

```python
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from main import app

@pytest.mark.asyncio
async def test_chat_send_persists_user_and_assistant():
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-chat", name="X"))
        await s.commit()

    fake_reply = {"content": "No anomalies found.", "citations": []}
    with patch("core.audit_studio.chat_service.run_chat", new=AsyncMock(return_value=fake_reply)):
        async with AsyncClient(app=app, base_url="http://test") as c:
            r = await c.post("/api/audit-profiles/p-chat/chat", json={"message": "Flag anomalies"})
            assert r.status_code == 200
            body = r.json()
            assert body["content"] == "No anomalies found."

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(AuditChatMessage).where(AuditChatMessage.profile_id == "p-chat").order_by(AuditChatMessage.created_at)
        )).scalars().all()
        assert [r.role for r in rows] == ["user", "assistant"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_chat.py::test_chat_send_persists_user_and_assistant -v`
Expected: FAIL — route missing.

- [ ] **Step 3: Implement**

Create `backend/core/audit_studio/chat_service.py`:

```python
"""Chat service for audit studio. Wraps existing LLM manager + profile context."""
import json
from core.llm_manager import get_llm_manager
from db.database import AsyncSessionLocal
from db.models import AuditProfile, ProfileVersion, AuditChatMessage
from sqlalchemy import select


async def _current_profile_json(profile_id: str) -> str:
    async with AsyncSessionLocal() as s:
        v = (await s.execute(
            select(ProfileVersion).where(
                ProfileVersion.profile_id == profile_id,
                ProfileVersion.is_current == True,  # noqa: E712
            )
        )).scalar_one_or_none()
    return v.profile_json if v else "{}"


async def run_chat(profile_id: str, user_message: str) -> dict:
    """Return {'content': str, 'citations': list}."""
    ctx = await _current_profile_json(profile_id)
    mgr = get_llm_manager()
    prompt = (
        "You are an AI audit assistant. Use the following profile JSON as context "
        "and answer the user's question with citations where possible.\n\n"
        f"PROFILE:\n{ctx}\n\nUSER: {user_message}"
    )
    resp = await mgr.chat(prompt)
    return {"content": resp, "citations": []}


async def persist_exchange(profile_id: str, user_msg: str, assistant_reply: dict) -> None:
    async with AsyncSessionLocal() as s:
        s.add(AuditChatMessage(profile_id=profile_id, role="user", content=user_msg))
        s.add(AuditChatMessage(
            profile_id=profile_id,
            role="assistant",
            content=assistant_reply["content"],
            citations=json.dumps(assistant_reply.get("citations", [])),
        ))
        await s.commit()
```

Add to `backend/api/audit_studio.py`:

```python
from core.audit_studio.chat_service import run_chat, persist_exchange

class ChatRequest(BaseModel):
    message: str

@router.post("/{profile_id}/chat")
async def chat(profile_id: str, req: ChatRequest):
    await _require_profile(profile_id)
    reply = await run_chat(profile_id, req.message)
    await persist_exchange(profile_id, req.message, reply)
    return reply
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_chat.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/audit_studio/chat_service.py backend/api/audit_studio.py backend/tests/test_audit_studio_chat.py
git commit -m "feat(audit-studio): POST /chat persists user+assistant messages"
```

---

## Task 10: Implement `GET /chat/history` and `DELETE /chat/history`

**Files:**
- Modify: `backend/api/audit_studio.py`
- Modify: `backend/tests/test_audit_studio_chat.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit_studio_chat.py`:

```python
@pytest.mark.asyncio
async def test_chat_history_and_clear():
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-hist", name="X"))
        await s.flush()
        s.add(AuditChatMessage(profile_id="p-hist", role="user", content="hi"))
        s.add(AuditChatMessage(profile_id="p-hist", role="assistant", content="hello"))
        await s.commit()
    async with AsyncClient(app=app, base_url="http://test") as c:
        r = await c.get("/api/audit-profiles/p-hist/chat/history")
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]

        d = await c.delete("/api/audit-profiles/p-hist/chat/history")
        assert d.status_code == 200

        r2 = await c.get("/api/audit-profiles/p-hist/chat/history")
        assert r2.json()["messages"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_chat.py::test_chat_history_and_clear -v`
Expected: FAIL — routes missing.

- [ ] **Step 3: Implement**

Add to `backend/api/audit_studio.py`:

```python
from db.models import AuditChatMessage
from sqlalchemy import delete

@router.get("/{profile_id}/chat/history")
async def chat_history(profile_id: str):
    await _require_profile(profile_id)
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(AuditChatMessage).where(AuditChatMessage.profile_id == profile_id)
            .order_by(AuditChatMessage.created_at)
        )).scalars().all()
    return {"messages": [
        {"id": r.id, "role": r.role, "content": r.content,
         "citations": r.citations, "created_at": r.created_at.isoformat()}
        for r in rows
    ]}

@router.delete("/{profile_id}/chat/history")
async def chat_clear(profile_id: str):
    await _require_profile(profile_id)
    async with AsyncSessionLocal() as s:
        await s.execute(delete(AuditChatMessage).where(AuditChatMessage.profile_id == profile_id))
        await s.commit()
    return {"status": "cleared"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_chat.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/audit_studio.py backend/tests/test_audit_studio_chat.py
git commit -m "feat(audit-studio): GET + DELETE /chat/history"
```

---

# PHASE 4 — Generation Endpoints

## Task 11: Implement `POST /generate/{output_type}` (enqueue + status)

**Files:**
- Create: `backend/core/audit_studio/generation_service.py`
- Modify: `backend/api/audit_studio.py`
- Modify: `backend/tests/test_audit_studio_generate.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit_studio_generate.py`:

```python
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from main import app

@pytest.mark.asyncio
async def test_generate_creates_pending_output_and_returns_job_id():
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-gen", name="X"))
        await s.commit()

    # Don't actually run the background job — just assert the enqueue path.
    with patch("core.audit_studio.generation_service._schedule", new=AsyncMock()):
        async with AsyncClient(app=app, base_url="http://test") as c:
            r = await c.post(
                "/api/audit-profiles/p-gen/generate/audit_report",
                json={"template_id": None, "options": {}},
            )
            assert r.status_code == 200
            body = r.json()
            assert "job_id" in body

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(GeneratedOutput).where(GeneratedOutput.profile_id == "p-gen")
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].output_type == "audit_report"
        assert rows[0].status == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_generate.py::test_generate_creates_pending_output_and_returns_job_id -v`
Expected: FAIL — route missing.

- [ ] **Step 3: Implement**

Create `backend/core/audit_studio/generation_service.py`:

```python
"""Generation service — dispatches per output_type to existing generators."""
from typing import Optional
from db.database import AsyncSessionLocal
from db.models import GeneratedOutput

SUPPORTED_TYPES = {
    "audit_report", "profit_loss", "balance_sheet", "cash_flow",
    "tax_schedule", "management_report", "custom",
}


async def enqueue(profile_id: str, output_type: str, template_id: Optional[str]) -> str:
    if output_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported output_type: {output_type}")
    async with AsyncSessionLocal() as s:
        row = GeneratedOutput(
            profile_id=profile_id,
            output_type=output_type,
            template_id=template_id,
            status="pending",
        )
        s.add(row)
        await s.commit()
        job_id = row.id
    await _schedule(job_id)
    return job_id


async def _schedule(job_id: str) -> None:
    """Run the background generation task. Patched in tests."""
    import asyncio
    asyncio.create_task(_run(job_id))


async def _run(job_id: str) -> None:
    """Runs the actual generation. Keep minimal; delegate to existing generator."""
    async with AsyncSessionLocal() as s:
        row = await s.get(GeneratedOutput, job_id)
        if row is None:
            return
        row.status = "processing"
        await s.commit()
    try:
        output_path = await _dispatch(job_id)
        async with AsyncSessionLocal() as s:
            row = await s.get(GeneratedOutput, job_id)
            row.status = "ready"
            row.output_path = output_path
            await s.commit()
    except Exception as e:  # noqa: BLE001
        async with AsyncSessionLocal() as s:
            row = await s.get(GeneratedOutput, job_id)
            row.status = "failed"
            row.error_message = str(e)
            await s.commit()


async def _dispatch(job_id: str) -> str:
    """Route to the existing report_generator / template-aware generator. Returns file path."""
    # TODO(integration): wire to existing core.report_generator.* once dispatch map is settled.
    # For now, return a placeholder path so the endpoint+DB flow is testable.
    return f"storage/generated/{job_id}.pdf"
```

Add to `backend/api/audit_studio.py`:

```python
from typing import Optional
from core.audit_studio.generation_service import enqueue

class GenerateRequest(BaseModel):
    template_id: Optional[str] = None
    options: dict = {}

@router.post("/{profile_id}/generate/{output_type}")
async def generate(profile_id: str, output_type: str, req: GenerateRequest):
    await _require_profile(profile_id)
    try:
        job_id = await enqueue(profile_id, output_type, req.template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"job_id": job_id, "status": "pending"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_generate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/audit_studio/generation_service.py backend/api/audit_studio.py backend/tests/test_audit_studio_generate.py
git commit -m "feat(audit-studio): POST /generate/{output_type} enqueues job"
```

---

## Task 12: Implement `GET /outputs` and `GET /outputs/{id}/download`

**Files:**
- Modify: `backend/api/audit_studio.py`
- Modify: `backend/tests/test_audit_studio_generate.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit_studio_generate.py`:

```python
import os, tempfile

@pytest.mark.asyncio
async def test_list_outputs_returns_all_for_profile():
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-out", name="X"))
        await s.flush()
        s.add(GeneratedOutput(id="o1", profile_id="p-out", output_type="audit_report", status="ready",
                              output_path="storage/generated/o1.pdf"))
        s.add(GeneratedOutput(id="o2", profile_id="p-out", output_type="profit_loss", status="pending"))
        await s.commit()
    async with AsyncClient(app=app, base_url="http://test") as c:
        r = await c.get("/api/audit-profiles/p-out/outputs")
        assert r.status_code == 200
        types = {o["output_type"] for o in r.json()["outputs"]}
        assert types == {"audit_report", "profit_loss"}


@pytest.mark.asyncio
async def test_download_returns_file_bytes(tmp_path):
    fpath = tmp_path / "sample.pdf"
    fpath.write_bytes(b"%PDF-1.4 test")
    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-dl", name="X"))
        await s.flush()
        s.add(GeneratedOutput(id="dl1", profile_id="p-dl", output_type="audit_report",
                              status="ready", output_path=str(fpath)))
        await s.commit()
    async with AsyncClient(app=app, base_url="http://test") as c:
        r = await c.get("/api/audit-profiles/p-dl/outputs/dl1/download")
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_generate.py -v`
Expected: FAIL — routes missing.

- [ ] **Step 3: Implement**

Add to `backend/api/audit_studio.py`:

```python
from fastapi.responses import FileResponse
import os
from db.models import GeneratedOutput

@router.get("/{profile_id}/outputs")
async def list_outputs(profile_id: str):
    await _require_profile(profile_id)
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(GeneratedOutput).where(GeneratedOutput.profile_id == profile_id)
            .order_by(GeneratedOutput.created_at.desc())
        )).scalars().all()
    return {"outputs": [
        {"id": r.id, "output_type": r.output_type, "status": r.status,
         "download_url": f"/api/audit-profiles/{profile_id}/outputs/{r.id}/download" if r.status == "ready" else None,
         "error_message": r.error_message,
         "created_at": r.created_at.isoformat()}
        for r in rows
    ]}


@router.get("/{profile_id}/outputs/{output_id}/download")
async def download_output(profile_id: str, output_id: str):
    await _require_profile(profile_id)
    async with AsyncSessionLocal() as s:
        row = await s.get(GeneratedOutput, output_id)
    if row is None or row.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Output not found")
    if row.status != "ready" or not row.output_path or not os.path.exists(row.output_path):
        raise HTTPException(status_code=409, detail=f"Output not ready (status={row.status})")
    return FileResponse(row.output_path, filename=os.path.basename(row.output_path))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_generate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/audit_studio.py backend/tests/test_audit_studio_generate.py
git commit -m "feat(audit-studio): GET /outputs and /outputs/{id}/download"
```

---

## Task 13: Wire `_dispatch` to real generators per output_type

**Files:**
- Modify: `backend/core/audit_studio/generation_service.py`
- Modify: `backend/tests/test_audit_studio_generate.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit_studio_generate.py`:

```python
@pytest.mark.asyncio
async def test_dispatch_routes_each_output_type():
    from core.audit_studio.generation_service import _dispatch, SUPPORTED_TYPES
    from unittest.mock import patch, AsyncMock

    async with AsyncSessionLocal() as s:
        s.add(AuditProfile(id="p-disp", name="X"))
        await s.flush()
        for t in SUPPORTED_TYPES:
            s.add(GeneratedOutput(id=f"d-{t}", profile_id="p-disp", output_type=t, status="processing"))
        await s.commit()

    with patch("core.audit_studio.generation_service._generate_by_type",
               new=AsyncMock(return_value="storage/generated/fake.pdf")) as m:
        for t in SUPPORTED_TYPES:
            path = await _dispatch(f"d-{t}")
            assert path.endswith(".pdf")
        assert m.await_count == len(SUPPORTED_TYPES)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_audit_studio_generate.py::test_dispatch_routes_each_output_type -v`
Expected: FAIL — `_generate_by_type` not defined.

- [ ] **Step 3: Implement dispatch map**

Replace `_dispatch` in `backend/core/audit_studio/generation_service.py`:

```python
async def _dispatch(job_id: str) -> str:
    async with AsyncSessionLocal() as s:
        row = await s.get(GeneratedOutput, job_id)
    return await _generate_by_type(row.profile_id, row.output_type, row.template_id, job_id)


async def _generate_by_type(profile_id: str, output_type: str, template_id, job_id: str) -> str:
    """
    Dispatch to the existing generators. Today each branch returns a placeholder
    path; replace these with real calls to core.report_generator.* as each one
    is proven end-to-end.
    """
    from pathlib import Path
    out_dir = Path("storage/generated"); out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{job_id}.pdf"

    # Branches — keep the mapping explicit so it's obvious what is and isn't wired.
    if output_type == "audit_report":
        from core.report_generator import generate_audit_report  # existing
        await generate_audit_report(profile_id, template_id, str(out_path))
    elif output_type == "profit_loss":
        from core.report_generator import generate_profit_loss
        await generate_profit_loss(profile_id, template_id, str(out_path))
    elif output_type == "balance_sheet":
        from core.report_generator import generate_balance_sheet
        await generate_balance_sheet(profile_id, template_id, str(out_path))
    elif output_type == "cash_flow":
        from core.report_generator import generate_cash_flow
        await generate_cash_flow(profile_id, template_id, str(out_path))
    elif output_type == "tax_schedule":
        from core.report_generator import generate_tax_schedule
        await generate_tax_schedule(profile_id, template_id, str(out_path))
    elif output_type == "management_report":
        from core.report_generator import generate_management_report
        await generate_management_report(profile_id, template_id, str(out_path))
    elif output_type == "custom":
        from core.report_generator import generate_custom
        await generate_custom(profile_id, template_id, str(out_path))
    else:
        raise ValueError(f"Unsupported output_type: {output_type}")

    return str(out_path)
```

**Note:** Confirm each `generate_*` function exists in `core/report_generator.py`. If any is missing, stub it with a small helper that writes a minimal PDF — that work belongs in a separate downstream ticket, not this plan. Add `# type: ignore` on the import if needed to unblock the rest of this phase.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_audit_studio_generate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/core/audit_studio/generation_service.py backend/tests/test_audit_studio_generate.py
git commit -m "feat(audit-studio): dispatch _generate_by_type for all output types"
```

---

# PHASE 5 — Frontend Scaffold

## Task 14: Create `FinanceStudio` folder + `types.ts`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/types.ts`

- [ ] **Step 1: Write the file**

Create `frontend/src/components/studios/FinanceStudio/types.ts`:

```typescript
export type OutputType =
  | 'audit_report'
  | 'profit_loss'
  | 'balance_sheet'
  | 'cash_flow'
  | 'tax_schedule'
  | 'management_report'
  | 'custom';

export interface AuditProfile {
  id: string;
  name: string;
  created_at: string;
}

export interface ProfileVersion {
  id: string;
  branch_name: string;
  is_current: boolean;
  created_at: string;
}

export interface SourceDoc {
  id: string;
  name: string;
  doc_type: string;
  confidence: number | null;
  status: 'uploaded' | 'extracting' | 'ready' | 'failed';
}

export interface ChatCitation { doc_id: string; page?: number; excerpt?: string; }

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: ChatCitation[];
  created_at: string;
}

export interface GeneratedOutput {
  id: string;
  output_type: OutputType;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  download_url: string | null;
  error_message: string | null;
  created_at: string;
}

export type WorkflowStep = 1 | 2 | 3 | 4 | 5;
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: build succeeds (file is unused but well-typed).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/types.ts
git commit -m "feat(finance-studio): add shared types"
```

---

## Task 15: Create `api.ts` — thin wrapper over new backend endpoints

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/api.ts`

- [ ] **Step 1: Write the file**

Create `frontend/src/components/studios/FinanceStudio/api.ts`:

```typescript
import type {
  AuditProfile, ProfileVersion, SourceDoc, ChatMessage,
  GeneratedOutput, OutputType,
} from './types';

const BASE = 'http://localhost:8000';

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

// Profiles (existing endpoints, re-exposed here for locality)
export const getProfile = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}`).then(json<AuditProfile>);

export const listSourceDocs = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/source-documents`).then(json<{ documents: SourceDoc[] }>);

// Versions (new)
export const listVersions = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/versions`).then(json<{ versions: ProfileVersion[] }>);

export const branchVersion = (id: string, name: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/branch`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ branch_name: name }),
  }).then(json<{ version_id: string }>);

export const activateVersion = (id: string, vid: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/versions/${vid}/activate`, { method: 'PATCH' }).then(json);

export const compareVersions = (id: string, v1: string, v2: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/versions/${v1}/compare/${v2}`).then(json<{
    changed: Record<string, { before: unknown; after: unknown }>;
    added: Record<string, unknown>;
    removed: Record<string, unknown>;
  }>);

// Chat (new)
export const chatHistory = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/chat/history`).then(json<{ messages: ChatMessage[] }>);

export const chatSend = (id: string, message: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  }).then(json<{ content: string; citations: unknown[] }>);

export const chatClear = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/chat/history`, { method: 'DELETE' }).then(json);

// Generation (new)
export const generateOutput = (id: string, type: OutputType, templateId: string | null) =>
  fetch(`${BASE}/api/audit-profiles/${id}/generate/${type}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_id: templateId, options: {} }),
  }).then(json<{ job_id: string; status: string }>);

export const listOutputs = (id: string) =>
  fetch(`${BASE}/api/audit-profiles/${id}/outputs`).then(json<{ outputs: GeneratedOutput[] }>);
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/api.ts
git commit -m "feat(finance-studio): add api wrapper"
```

---

## Task 16: Create `FinanceStudioContext`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/FinanceStudioContext.tsx`

- [ ] **Step 1: Write the file**

Create `frontend/src/components/studios/FinanceStudio/FinanceStudioContext.tsx`:

```tsx
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import type {
  AuditProfile, ProfileVersion, SourceDoc, ChatMessage,
  GeneratedOutput, OutputType, WorkflowStep,
} from './types';
import * as api from './api';

interface FinanceStudioState {
  profileId: string | null;
  setProfileId: (id: string | null) => void;

  activeProfile: AuditProfile | null;

  versions: ProfileVersion[];
  activeVersionId: string | null;
  switchVersion: (id: string) => Promise<void>;
  branchVersion: (name: string) => Promise<void>;

  sourceDocs: SourceDoc[];
  refreshDocs: () => Promise<void>;

  chatHistory: ChatMessage[];
  sendMessage: (text: string) => Promise<void>;
  clearChat: () => Promise<void>;
  chatLoading: boolean;

  outputs: GeneratedOutput[];
  generateOutput: (type: OutputType) => Promise<void>;
  selectedTemplateId: string | null;
  setSelectedTemplate: (id: string | null) => void;

  workflowStep: WorkflowStep;
  setWorkflowStep: (s: WorkflowStep) => void;
}

const Ctx = createContext<FinanceStudioState | null>(null);

export function FinanceStudioProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileId] = useState<string | null>(null);
  const [activeProfile, setActiveProfile] = useState<AuditProfile | null>(null);
  const [versions, setVersions] = useState<ProfileVersion[]>([]);
  const [sourceDocs, setSourceDocs] = useState<SourceDoc[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [outputs, setOutputs] = useState<GeneratedOutput[]>([]);
  const [selectedTemplateId, setSelectedTemplate] = useState<string | null>(null);
  const [workflowStep, setWorkflowStep] = useState<WorkflowStep>(1);

  const activeVersionId = versions.find(v => v.is_current)?.id ?? null;

  // Load core data whenever profile changes.
  useEffect(() => {
    if (!profileId) return;
    (async () => {
      setActiveProfile(await api.getProfile(profileId));
      setVersions((await api.listVersions(profileId)).versions);
      setSourceDocs((await api.listSourceDocs(profileId)).documents);
      setChatHistory((await api.chatHistory(profileId)).messages);
      setOutputs((await api.listOutputs(profileId)).outputs);
    })();
  }, [profileId]);

  const refreshDocs = useCallback(async () => {
    if (!profileId) return;
    setSourceDocs((await api.listSourceDocs(profileId)).documents);
  }, [profileId]);

  const switchVersion = useCallback(async (id: string) => {
    if (!profileId) return;
    await api.activateVersion(profileId, id);
    setVersions((await api.listVersions(profileId)).versions);
  }, [profileId]);

  const branchVersion = useCallback(async (name: string) => {
    if (!profileId) return;
    await api.branchVersion(profileId, name);
    setVersions((await api.listVersions(profileId)).versions);
  }, [profileId]);

  const sendMessage = useCallback(async (text: string) => {
    if (!profileId) return;
    setChatLoading(true);
    try {
      await api.chatSend(profileId, text);
      setChatHistory((await api.chatHistory(profileId)).messages);
    } finally {
      setChatLoading(false);
    }
  }, [profileId]);

  const clearChat = useCallback(async () => {
    if (!profileId) return;
    await api.chatClear(profileId);
    setChatHistory([]);
  }, [profileId]);

  const generateOutput = useCallback(async (type: OutputType) => {
    if (!profileId) return;
    await api.generateOutput(profileId, type, selectedTemplateId);
    setOutputs((await api.listOutputs(profileId)).outputs);
  }, [profileId, selectedTemplateId]);

  return (
    <Ctx.Provider value={{
      profileId, setProfileId, activeProfile,
      versions, activeVersionId, switchVersion, branchVersion,
      sourceDocs, refreshDocs,
      chatHistory, sendMessage, clearChat, chatLoading,
      outputs, generateOutput,
      selectedTemplateId, setSelectedTemplate,
      workflowStep, setWorkflowStep,
    }}>
      {children}
    </Ctx.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useFinanceStudio(): FinanceStudioState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useFinanceStudio must be used inside <FinanceStudioProvider>');
  return ctx;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/FinanceStudioContext.tsx
git commit -m "feat(finance-studio): add FinanceStudioContext"
```

---

## Task 17: Create `FinanceStudio.tsx` + CSS (three-panel shell)

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/FinanceStudio.tsx`
- Create: `frontend/src/components/studios/FinanceStudio/FinanceStudio.css`

- [ ] **Step 1: Write the CSS**

Create `frontend/src/components/studios/FinanceStudio/FinanceStudio.css`:

```css
.finance-studio {
  display: grid;
  grid-template-columns: 280px 1fr 300px;
  gap: 12px;
  height: 100%;
  padding: 12px;
  background: transparent;
}

.finance-studio__left,
.finance-studio__right {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: auto;
  padding: 12px;
  backdrop-filter: blur(12px);
}

.finance-studio__center {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  min-width: 0;
}

.finance-studio__center > * {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: auto;
  padding: 12px;
  backdrop-filter: blur(12px);
  min-width: 0;
}
```

- [ ] **Step 2: Write the component**

Create `frontend/src/components/studios/FinanceStudio/FinanceStudio.tsx`:

```tsx
import './FinanceStudio.css';
import { FinanceStudioProvider } from './FinanceStudioContext';
import { SourceDocsSidebar } from './SourceDocsSidebar/SourceDocsSidebar';
import { AuditChat } from './AuditChat/AuditChat';
import { ReportPreview } from './ReportPreview/ReportPreview';
import { ExportsPanel } from './ExportsPanel/ExportsPanel';

export function FinanceStudio() {
  return (
    <FinanceStudioProvider>
      <div className="finance-studio">
        <aside className="finance-studio__left">
          <SourceDocsSidebar />
        </aside>
        <section className="finance-studio__center">
          <AuditChat />
          <ReportPreview />
        </section>
        <aside className="finance-studio__right">
          <ExportsPanel />
        </aside>
      </div>
    </FinanceStudioProvider>
  );
}
```

- [ ] **Step 3: Create stubs for missing subcomponents**

The imports above will fail until subcomponents exist. Create minimal placeholder files so the shell builds:

`frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/SourceDocsSidebar.tsx`:
```tsx
export function SourceDocsSidebar() { return <div>Source Docs</div>; }
```
`frontend/src/components/studios/FinanceStudio/AuditChat/AuditChat.tsx`:
```tsx
export function AuditChat() { return <div>Audit Chat</div>; }
```
`frontend/src/components/studios/FinanceStudio/ReportPreview/ReportPreview.tsx`:
```tsx
export function ReportPreview() { return <div>Report Preview</div>; }
```
`frontend/src/components/studios/FinanceStudio/ExportsPanel/ExportsPanel.tsx`:
```tsx
export function ExportsPanel() { return <div>Exports</div>; }
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/
git commit -m "feat(finance-studio): three-panel shell with provider and stubs"
```

---

# PHASE 6 — SourceDocsSidebar

## Task 18: `DocumentCard`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/DocumentCard.tsx`

- [ ] **Step 1: Write the component**

```tsx
import type { SourceDoc } from '../types';

interface Props { doc: SourceDoc; onDelete: (id: string) => void; }

export function DocumentCard({ doc, onDelete }: Props) {
  const warn = doc.confidence !== null && doc.confidence < 0.7;
  return (
    <div className="doc-card" data-testid={`doc-card-${doc.id}`}>
      <div className="doc-card__name">{doc.name}</div>
      <div className="doc-card__type">{doc.doc_type}</div>
      {warn && <span className="doc-card__warn">⚠ Review</span>}
      {doc.confidence !== null && (
        <div className="doc-card__confidence">
          <div className="bar" style={{ width: `${Math.round(doc.confidence * 100)}%` }} />
        </div>
      )}
      <button onClick={() => onDelete(doc.id)} aria-label="Delete doc">×</button>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/DocumentCard.tsx
git commit -m "feat(finance-studio): DocumentCard"
```

---

## Task 19: `VersionSwitcher`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/VersionSwitcher.tsx`

- [ ] **Step 1: Write the component**

```tsx
import { useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';

export function VersionSwitcher() {
  const { versions, activeVersionId, switchVersion, branchVersion } = useFinanceStudio();
  const [newBranch, setNewBranch] = useState('');

  return (
    <div className="version-switcher">
      <label>Version</label>
      <select
        value={activeVersionId ?? ''}
        onChange={e => switchVersion(e.target.value)}
      >
        {versions.map(v => (
          <option key={v.id} value={v.id}>
            {v.branch_name}{v.is_current ? ' (current)' : ''}
          </option>
        ))}
      </select>

      <input
        placeholder="new branch name"
        value={newBranch}
        onChange={e => setNewBranch(e.target.value)}
      />
      <button
        disabled={!newBranch.trim()}
        onClick={async () => { await branchVersion(newBranch.trim()); setNewBranch(''); }}
      >
        Branch
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/VersionSwitcher.tsx
git commit -m "feat(finance-studio): VersionSwitcher"
```

---

## Task 20: `LearnedProfileTree`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/LearnedProfileTree.tsx`

- [ ] **Step 1: Write the component**

```tsx
import { useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';

export function LearnedProfileTree() {
  const { activeProfile } = useFinanceStudio();
  const [open, setOpen] = useState<Record<string, boolean>>({});

  if (!activeProfile) return <div className="muted">No profile loaded</div>;

  // Profile JSON is stored server-side on the version; we surface top-level sections
  // that AuditProfile exposes. If profile summary fields aren't available here, render name.
  const sections = [
    { key: 'account_mappings', label: 'Account Mappings' },
    { key: 'financial_periods', label: 'Financial Periods' },
    { key: 'risks', label: 'Flagged Risks' },
  ];

  return (
    <div className="profile-tree">
      <h4>Learned Profile — {activeProfile.name}</h4>
      {sections.map(s => (
        <div key={s.key} className="profile-tree__section">
          <button onClick={() => setOpen(o => ({ ...o, [s.key]: !o[s.key] }))}>
            {open[s.key] ? '▾' : '▸'} {s.label}
          </button>
          {open[s.key] && (
            <div className="profile-tree__body muted">
              (loaded lazily from GET /audit-profiles/{activeProfile.id}/{s.key})
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/LearnedProfileTree.tsx
git commit -m "feat(finance-studio): LearnedProfileTree"
```

---

## Task 21: Flesh out `SourceDocsSidebar.tsx` with upload, docs, tree, switcher

**Files:**
- Replace: `frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/SourceDocsSidebar.tsx`

- [ ] **Step 1: Write the component**

```tsx
import { useRef } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';
import { DocumentCard } from './DocumentCard';
import { LearnedProfileTree } from './LearnedProfileTree';
import { VersionSwitcher } from './VersionSwitcher';

export function SourceDocsSidebar() {
  const { profileId, sourceDocs, refreshDocs } = useFinanceStudio();
  const fileInput = useRef<HTMLInputElement>(null);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !profileId) return;
    const fd = new FormData();
    fd.append('file', file);
    fd.append('doc_type', 'trial_balance'); // TODO: doc type picker in a later task
    await fetch(`http://localhost:8000/api/audit-profiles/${profileId}/upload-source`, {
      method: 'POST', body: fd,
    });
    e.target.value = '';
    await refreshDocs();
  }

  async function onDelete(docId: string) {
    if (!profileId) return;
    await fetch(`http://localhost:8000/api/audit-profiles/${profileId}/source-documents/${docId}`, {
      method: 'DELETE',
    });
    await refreshDocs();
  }

  return (
    <div className="source-docs">
      <VersionSwitcher />

      <h4>Source Documents</h4>
      <div
        className="dropzone"
        onClick={() => fileInput.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={async e => {
          e.preventDefault();
          const file = e.dataTransfer.files?.[0];
          if (!file || !profileId) return;
          const fd = new FormData();
          fd.append('file', file);
          fd.append('doc_type', 'trial_balance');
          await fetch(`http://localhost:8000/api/audit-profiles/${profileId}/upload-source`, {
            method: 'POST', body: fd,
          });
          await refreshDocs();
        }}
      >
        Drop file or click to upload
      </div>
      <input ref={fileInput} type="file" hidden onChange={onUpload} />

      <div className="doc-list">
        {sourceDocs.map(d => <DocumentCard key={d.id} doc={d} onDelete={onDelete} />)}
        {sourceDocs.length === 0 && <div className="muted">No documents yet.</div>}
      </div>

      <LearnedProfileTree />
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/SourceDocsSidebar/SourceDocsSidebar.tsx
git commit -m "feat(finance-studio): full SourceDocsSidebar with upload + docs + tree"
```

---

# PHASE 7 — AuditChat

## Task 22: `WorkflowSteps`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/AuditChat/WorkflowSteps.tsx`

- [ ] **Step 1: Write**

```tsx
import { useFinanceStudio } from '../FinanceStudioContext';
import type { WorkflowStep } from '../types';

const STEPS: { n: WorkflowStep; label: string }[] = [
  { n: 1, label: 'Upload' },
  { n: 2, label: 'Build Profile' },
  { n: 3, label: 'Validate with AI' },
  { n: 4, label: 'Select Format' },
  { n: 5, label: 'Generate' },
];

export function WorkflowSteps() {
  const { workflowStep, setWorkflowStep } = useFinanceStudio();
  return (
    <ol className="workflow-steps">
      {STEPS.map(s => (
        <li key={s.n}
            className={s.n === workflowStep ? 'active' : s.n < workflowStep ? 'done' : ''}
            onClick={() => setWorkflowStep(s.n)}>
          {s.n}. {s.label}
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/AuditChat/WorkflowSteps.tsx
git commit -m "feat(finance-studio): WorkflowSteps"
```

---

## Task 23: `SuggestedActions`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/AuditChat/SuggestedActions.tsx`

- [ ] **Step 1: Write**

```tsx
import { useFinanceStudio } from '../FinanceStudioContext';

const PROMPTS = [
  'Flag anomalies in revenue accounts',
  'Give me an audit risk summary',
  'Drill down on account 4001',
  'Compare to prior year',
];

export function SuggestedActions() {
  const { sendMessage, chatLoading } = useFinanceStudio();
  return (
    <div className="suggested-actions">
      {PROMPTS.map(p => (
        <button key={p} disabled={chatLoading} onClick={() => sendMessage(p)}>
          {p}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/AuditChat/SuggestedActions.tsx
git commit -m "feat(finance-studio): SuggestedActions"
```

---

## Task 24: `ChatMessage`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/AuditChat/ChatMessage.tsx`

- [ ] **Step 1: Write**

```tsx
import type { ChatMessage as CM } from '../types';

export function ChatMessage({ msg }: { msg: CM }) {
  return (
    <div className={`chat-msg chat-msg--${msg.role}`} data-testid={`msg-${msg.id}`}>
      <div className="chat-msg__content">{msg.content}</div>
      {msg.citations?.length > 0 && (
        <div className="chat-msg__citations">
          {msg.citations.map((c, i) => (
            <span key={i} className="citation-chip">
              {c.doc_id}{c.page ? ` p.${c.page}` : ''}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/AuditChat/ChatMessage.tsx
git commit -m "feat(finance-studio): ChatMessage"
```

---

## Task 25: Flesh out `AuditChat.tsx`

**Files:**
- Replace: `frontend/src/components/studios/FinanceStudio/AuditChat/AuditChat.tsx`

- [ ] **Step 1: Write**

```tsx
import { useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';
import { WorkflowSteps } from './WorkflowSteps';
import { SuggestedActions } from './SuggestedActions';
import { ChatMessage } from './ChatMessage';

export function AuditChat() {
  const { chatHistory, sendMessage, chatLoading, clearChat } = useFinanceStudio();
  const [text, setText] = useState('');

  async function submit() {
    const t = text.trim();
    if (!t) return;
    setText('');
    await sendMessage(t);
  }

  return (
    <div className="audit-chat">
      <WorkflowSteps />
      <SuggestedActions />

      <div className="audit-chat__messages">
        {chatHistory.map(m => <ChatMessage key={m.id} msg={m} />)}
        {chatLoading && <div className="chat-msg chat-msg--loading">…</div>}
      </div>

      <div className="audit-chat__input">
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit(); }
          }}
          placeholder="Ask about the audit…"
          rows={2}
        />
        <button onClick={submit} disabled={chatLoading || !text.trim()}>Send</button>
        <button onClick={clearChat} disabled={chatLoading}>Clear</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/AuditChat/AuditChat.tsx
git commit -m "feat(finance-studio): full AuditChat wiring"
```

---

# PHASE 8 — ReportPreview

## Task 26: `PreviewPage` + `ReportPreview`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/ReportPreview/PreviewPage.tsx`
- Replace: `frontend/src/components/studios/FinanceStudio/ReportPreview/ReportPreview.tsx`

- [ ] **Step 1: Write `PreviewPage.tsx`**

```tsx
export function PreviewPage({ pageNumber, children }: { pageNumber: number; children: React.ReactNode }) {
  return (
    <div className="preview-page">
      <div className="preview-page__body">{children}</div>
      <div className="preview-page__footer">Page {pageNumber}</div>
    </div>
  );
}
```

- [ ] **Step 2: Write `ReportPreview.tsx`**

```tsx
import { useFinanceStudio } from '../FinanceStudioContext';
import { PreviewPage } from './PreviewPage';

export function ReportPreview() {
  const { outputs } = useFinanceStudio();
  const readyReport = outputs.find(o => o.output_type === 'audit_report' && o.status === 'ready');

  if (!readyReport) {
    return (
      <div className="report-preview report-preview--empty">
        <PreviewPage pageNumber={1}>
          <h3>No report generated yet.</h3>
          <p className="muted">Generate an Audit Report from the Exports panel to preview it here.</p>
        </PreviewPage>
      </div>
    );
  }

  return (
    <div className="report-preview">
      <iframe
        src={`http://localhost:8000${readyReport.download_url}`}
        title="Audit Report Preview"
        className="report-preview__iframe"
      />
    </div>
  );
}
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/ReportPreview/
git commit -m "feat(finance-studio): ReportPreview with PDF iframe + empty state"
```

---

# PHASE 9 — ExportsPanel

## Task 27: `FormatPicker`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/ExportsPanel/FormatPicker.tsx`

- [ ] **Step 1: Write**

```tsx
import { useEffect, useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';

interface Template { id: string; name: string; confidence?: number; is_prebuilt?: boolean; }

export function FormatPicker() {
  const { selectedTemplateId, setSelectedTemplate } = useFinanceStudio();
  const [templates, setTemplates] = useState<Template[]>([]);

  useEffect(() => {
    (async () => {
      const [custom, prebuilt] = await Promise.all([
        fetch('http://localhost:8000/api/templates/list').then(r => r.json()),
        fetch('http://localhost:8000/api/templates/prebuilt').then(r => r.json()),
      ]);
      const all: Template[] = [
        ...(prebuilt.templates || []).map((t: Template) => ({ ...t, is_prebuilt: true })),
        ...(custom.templates || []),
      ];
      setTemplates(all);
    })();
  }, []);

  const selected = templates.find(t => t.id === selectedTemplateId);
  const lowConfidence = selected && !selected.is_prebuilt && (selected.confidence ?? 1) < 0.7;

  return (
    <div className="format-picker">
      <label>Auditor format</label>
      <select
        value={selectedTemplateId ?? ''}
        onChange={e => setSelectedTemplate(e.target.value || null)}
      >
        <option value="">— Select —</option>
        <optgroup label="Prebuilt">
          {templates.filter(t => t.is_prebuilt).map(t => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </optgroup>
        <optgroup label="Custom (learned)">
          {templates.filter(t => !t.is_prebuilt).map(t => (
            <option key={t.id} value={t.id}>
              {t.name}{t.confidence != null ? ` (${Math.round(t.confidence * 100)}%)` : ''}
            </option>
          ))}
        </optgroup>
      </select>
      {lowConfidence && (
        <div className="format-picker__warn">
          ⚠ Low confidence — review before generating.
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/ExportsPanel/FormatPicker.tsx
git commit -m "feat(finance-studio): FormatPicker"
```

---

## Task 28: `ExportCard`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/ExportsPanel/ExportCard.tsx`

- [ ] **Step 1: Write**

```tsx
import { useFinanceStudio } from '../FinanceStudioContext';
import type { OutputType } from '../types';

interface Props { outputType: OutputType; label: string; }

export function ExportCard({ outputType, label }: Props) {
  const { outputs, generateOutput, selectedTemplateId } = useFinanceStudio();
  const latest = outputs
    .filter(o => o.output_type === outputType)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];

  const disabled = !selectedTemplateId || latest?.status === 'processing' || latest?.status === 'pending';

  return (
    <div className="export-card" data-testid={`export-${outputType}`}>
      <div className="export-card__label">{label}</div>
      <div className="export-card__status">{latest?.status ?? 'not started'}</div>
      {latest?.status === 'failed' && (
        <div className="export-card__error">{latest.error_message ?? 'failed'}</div>
      )}
      <div className="export-card__actions">
        <button disabled={disabled} onClick={() => generateOutput(outputType)}>
          {latest?.status === 'ready' ? 'Regenerate' : 'Generate'}
        </button>
        {latest?.status === 'ready' && latest.download_url && (
          <a href={`http://localhost:8000${latest.download_url}`}>Download</a>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/ExportsPanel/ExportCard.tsx
git commit -m "feat(finance-studio): ExportCard"
```

---

## Task 29: Flesh out `ExportsPanel.tsx` with all 7 output types + FormatPicker

**Files:**
- Replace: `frontend/src/components/studios/FinanceStudio/ExportsPanel/ExportsPanel.tsx`

- [ ] **Step 1: Write**

```tsx
import { FormatPicker } from './FormatPicker';
import { ExportCard } from './ExportCard';
import type { OutputType } from '../types';

const OUTPUTS: { type: OutputType; label: string }[] = [
  { type: 'audit_report',     label: 'Audit Report' },
  { type: 'profit_loss',      label: 'Profit & Loss' },
  { type: 'balance_sheet',    label: 'Balance Sheet' },
  { type: 'cash_flow',        label: 'Cash Flow' },
  { type: 'tax_schedule',     label: 'Tax Schedule' },
  { type: 'management_report',label: 'Management Report' },
  { type: 'custom',           label: 'Custom Export' },
];

export function ExportsPanel() {
  return (
    <div className="exports-panel">
      <FormatPicker />
      <div className="exports-panel__cards">
        {OUTPUTS.map(o => <ExportCard key={o.type} outputType={o.type} label={o.label} />)}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/ExportsPanel/ExportsPanel.tsx
git commit -m "feat(finance-studio): ExportsPanel with all 7 cards"
```

---

# PHASE 10 — VersionCompare

## Task 30: `VersionCompare`

**Files:**
- Create: `frontend/src/components/studios/FinanceStudio/ExportsPanel/VersionCompare.tsx`

- [ ] **Step 1: Write**

```tsx
import { useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';
import * as api from '../api';

export function VersionCompare() {
  const { profileId, versions } = useFinanceStudio();
  const [v1, setV1] = useState<string>('');
  const [v2, setV2] = useState<string>('');
  const [diff, setDiff] = useState<Awaited<ReturnType<typeof api.compareVersions>> | null>(null);

  async function run() {
    if (!profileId || !v1 || !v2) return;
    setDiff(await api.compareVersions(profileId, v1, v2));
  }

  const empty = diff && !Object.keys(diff.changed).length
                       && !Object.keys(diff.added).length
                       && !Object.keys(diff.removed).length;

  return (
    <div className="version-compare">
      <h4>Compare versions</h4>
      <div className="version-compare__row">
        <select value={v1} onChange={e => setV1(e.target.value)}>
          <option value="">— v1 —</option>
          {versions.map(v => <option key={v.id} value={v.id}>{v.branch_name}</option>)}
        </select>
        <select value={v2} onChange={e => setV2(e.target.value)}>
          <option value="">— v2 —</option>
          {versions.map(v => <option key={v.id} value={v.id}>{v.branch_name}</option>)}
        </select>
        <button disabled={!v1 || !v2 || v1 === v2} onClick={run}>Compare</button>
      </div>

      {empty && <div className="muted">No differences found between these versions.</div>}
      {diff && !empty && (
        <pre className="version-compare__diff">{JSON.stringify(diff, null, 2)}</pre>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Mount it inside `ExportsPanel`**

Modify `frontend/src/components/studios/FinanceStudio/ExportsPanel/ExportsPanel.tsx` — add the import and render below the cards:

```tsx
import { VersionCompare } from './VersionCompare';
// ...
<VersionCompare />
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/ExportsPanel/VersionCompare.tsx \
        frontend/src/components/studios/FinanceStudio/ExportsPanel/ExportsPanel.tsx
git commit -m "feat(finance-studio): VersionCompare mounted in ExportsPanel"
```

---

# PHASE 11 — Wire Up Routing & Delete Old Studios

## Task 31: Update `StudioProvider` studio type

**Files:**
- Modify: `frontend/src/context/StudioProvider.tsx`

- [ ] **Step 1: Edit**

Replace the `Studio` type and default:

```tsx
export type Studio = 'legal' | 'finance' | 'regulatory' | 'templates' | 'settings';
```

Change default state:

```tsx
const [activeStudio, setActiveStudio] = useState<Studio>('finance');
```

- [ ] **Step 2: Type-check (expect errors)**

Run: `cd frontend && npm run build`
Expected: TS errors in `StudioSwitcher.tsx` / `App.tsx` referencing `'financial'` or `'profiles'`. That's fine — next task fixes them.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/context/StudioProvider.tsx
git commit -m "refactor(studios): collapse 'financial' + 'profiles' into 'finance'"
```

---

## Task 32: Update `StudioSwitcher` + `App.tsx` routing

**Files:**
- Modify: `frontend/src/components/StudioSwitcher.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: In `StudioSwitcher.tsx`**

Remove the two icons for `'financial'` and `'profiles'`. Replace with a single entry:

```tsx
{ key: 'finance', label: 'Finance', icon: '📊' },
```

Remove any code referencing `'financial'` or `'profiles'`.

- [ ] **Step 2: In `App.tsx`**

Find the switch/conditional that maps `activeStudio` to a component. Remove `'financial'` → `<FinancialStudio/>` and `'profiles'` → `<AuditProfileStudio/>` branches. Add:

```tsx
import { FinanceStudio } from './components/studios/FinanceStudio/FinanceStudio';
// ...
{activeStudio === 'finance' && <FinanceStudio />}
```

Delete the now-unused imports of `FinancialStudio` and `AuditProfileStudio`.

- [ ] **Step 3: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/StudioSwitcher.tsx frontend/src/App.tsx
git commit -m "refactor(studios): route 'finance' to FinanceStudio; drop old imports"
```

---

## Task 33: Delete old `FinancialStudio/` and `AuditProfileStudio/`

**Files:**
- Delete: `frontend/src/components/studios/FinancialStudio/` (entire folder)
- Delete: `frontend/src/components/studios/AuditProfileStudio/AuditProfileStudio.tsx`

- [ ] **Step 1: Delete**

```bash
rm -rf "frontend/src/components/studios/FinancialStudio"
rm "frontend/src/components/studios/AuditProfileStudio/AuditProfileStudio.tsx"
rmdir "frontend/src/components/studios/AuditProfileStudio" 2>/dev/null || true
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run build`
Expected: PASS. If it fails, there is a dangling import — grep for `FinancialStudio` or `AuditProfileStudio` and remove.

- [ ] **Step 3: Manual smoke test (UI verification)**

Per CLAUDE.md "For UI or frontend changes, start the dev server and use the feature in a browser":

1. `cd backend && uv run python main.py`
2. `cd frontend && npm run dev`
3. Open `http://localhost:5173`.
4. Confirm: single "Finance" icon in the sidebar; three-panel layout renders; upload a sample trial balance; build profile; send a chat message; select a format; click Generate on Audit Report; wait for status `ready`; preview appears in the iframe.

Capture any UI issues and fix inline before committing.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/src/components/studios/
git commit -m "refactor(studios): delete legacy FinancialStudio and AuditProfileStudio"
```

---

# PHASE 12 — End-to-End Integration Test

## Task 34: Write the integration test

**Files:**
- Create: `backend/tests/test_audit_studio_integration.py`

- [ ] **Step 1: Write**

```python
"""
End-to-end flow per spec §10:
  create → upload → build → chat → apply format → generate → download
"""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from main import app


@pytest.mark.asyncio
async def test_finance_studio_end_to_end(tmp_path):
    fake_pdf = tmp_path / "audit.pdf"

    async def fake_generate(profile_id, output_type, template_id, job_id):
        fake_pdf.write_bytes(b"%PDF-1.4 fake")
        return str(fake_pdf)

    with patch("core.audit_studio.generation_service._generate_by_type", new=AsyncMock(side_effect=fake_generate)), \
         patch("core.audit_studio.chat_service.run_chat",
               new=AsyncMock(return_value={"content": "No risks flagged.", "citations": []})):

        async with AsyncClient(app=app, base_url="http://test") as c:
            # 1. create profile
            r = await c.post("/api/audit-profiles", json={"name": "Integration Co"})
            assert r.status_code in (200, 201)
            pid = r.json()["id"]

            # 2. upload source doc (trial balance)
            files = {"file": ("tb.csv", b"acct,amount\n4001,10000\n", "text/csv")}
            r = await c.post(f"/api/audit-profiles/{pid}/upload-source",
                             data={"doc_type": "trial_balance"}, files=files)
            assert r.status_code == 200

            # 3. build profile
            r = await c.post(f"/api/audit-profiles/{pid}/build-profile")
            assert r.status_code == 200

            # 4. chat
            r = await c.post(f"/api/audit-profiles/{pid}/chat", json={"message": "Flag anomalies"})
            assert r.status_code == 200
            assert "No risks" in r.json()["content"]

            # 5. (format selection is a frontend-only step; pass template_id directly)
            template_id = "ifrs-standard-a4"

            # 6. generate
            r = await c.post(
                f"/api/audit-profiles/{pid}/generate/audit_report",
                json={"template_id": template_id, "options": {}},
            )
            assert r.status_code == 200
            job_id = r.json()["job_id"]

            # Wait for the background task (it's immediate since _generate_by_type is mocked)
            import asyncio
            await asyncio.sleep(0.05)

            # 7. download
            r = await c.get(f"/api/audit-profiles/{pid}/outputs/{job_id}/download")
            assert r.status_code == 200
            assert r.content.startswith(b"%PDF")
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/test_audit_studio_integration.py -v`
Expected: PASS.

- [ ] **Step 3: Full suite**

Run: `cd backend && uv run pytest -v`
Expected: existing 203 tests + new tests all PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_audit_studio_integration.py
git commit -m "test(audit-studio): end-to-end integration test"
```

---

# Self-Review Checklist (executed during plan authoring)

**Spec coverage:**
- §2 architecture → Task 17 (three-panel shell).
- §3 components → Tasks 14–30 cover every file in the spec's component tree.
- §4 state (`FinanceStudioContext`) → Task 16.
- §5 backend new endpoints → Tasks 4–13 (each endpoint has its own task + test).
- §6 data models → Tasks 1–3.
- §7 FormatPicker + "Learn From This Report" → Task 27; the "Learn From This Report" button re-uses the existing `POST /api/templates/upload-reference` endpoint and can be added inside `DocumentCard` when `doc_type === 'report_template'` (noted as a follow-up; not blocking this plan).
- §8 workflow steps → Task 22.
- §9 error handling → covered in components (`DocumentCard` warn badge, `ExportCard` failed state, `VersionCompare` empty state, `FormatPicker` low-confidence warning).
- §10 testing → backend tests are interleaved with every task; frontend vitest tests are deliberately **not** included in this plan (no vitest setup was confirmed in the repo). If `frontend/vitest.config.*` or an equivalent exists, add matching tests under `__tests__/` as a follow-up; otherwise rely on the manual smoke test in Task 33.
- §12 success criteria → Task 34 covers the happy-path e2e.

**Placeholder scan:** Only intentional TODO is the doc-type picker in Task 21 and the "Learn From This Report" button mentioned above — both called out explicitly. No vague "add error handling" instructions.

**Type consistency:** `OutputType`, `WorkflowStep`, `ChatMessage`, `GeneratedOutput`, `ProfileVersion`, `SourceDoc`, `AuditProfile` are declared once in `types.ts` (Task 14) and used identically throughout. Context method names (`switchVersion`, `branchVersion`, `sendMessage`, `clearChat`, `generateOutput`, `setSelectedTemplate`, `setWorkflowStep`) match between `FinanceStudioContext.tsx` (Task 16) and every consumer in later tasks.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-19-notebooklm-finance-studio-plan.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**

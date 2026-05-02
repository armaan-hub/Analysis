import uuid
import json
import pytest
from db.models import AuditProfile, ProfileVersion
from sqlalchemy import select


@pytest.mark.asyncio
async def test_profile_version_persists(db_session):
    profile_id = str(uuid.uuid4())
    profile = AuditProfile(id=profile_id, engagement_name="Test Co")
    db_session.add(profile)
    await db_session.flush()
    v = ProfileVersion(
        profile_id=profile_id,
        branch_name="main",
        profile_json='{"account_mappings": []}',
        is_current=True,
    )
    db_session.add(v)
    await db_session.commit()
    row = (await db_session.execute(select(ProfileVersion).where(ProfileVersion.profile_id == profile_id))).scalar_one()
    assert row.branch_name == "main"
    assert row.is_current is True


# ── Task 4 ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_studio_router_mounted(client):
    r = await client.get(f"/api/audit-profiles/{uuid.uuid4()}/versions")
    assert r.status_code in (404, 422, 200)
    detail = r.json().get("detail", "")
    if isinstance(detail, list):
        assert all("path" not in str(d) for d in detail)


# ── Task 5 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_versions_returns_all_for_profile(db_session, client):
    pid = str(uuid.uuid4())
    db_session.add(AuditProfile(id=pid, engagement_name="X"))
    await db_session.flush()
    db_session.add(ProfileVersion(profile_id=pid, branch_name="main", profile_json="{}", is_current=True))
    db_session.add(ProfileVersion(profile_id=pid, branch_name="remap-4001", profile_json="{}"))
    await db_session.commit()

    r = await client.get(f"/api/audit-profiles/{pid}/versions")
    assert r.status_code == 200
    data = r.json()
    names = {v["branch_name"] for v in data["versions"]}
    assert names == {"main", "remap-4001"}
    assert any(v["is_current"] for v in data["versions"])


# ── Task 6 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_branch_creates_copy_and_returns_new_id(db_session, client):
    pid = str(uuid.uuid4())
    v_main_id = str(uuid.uuid4())
    db_session.add(AuditProfile(id=pid, engagement_name="X"))
    await db_session.flush()
    db_session.add(ProfileVersion(
        id=v_main_id, profile_id=pid, branch_name="main",
        profile_json='{"account_mappings":[{"a":1}]}', is_current=True,
    ))
    await db_session.commit()

    r = await client.post(f"/api/audit-profiles/{pid}/branch", json={"branch_name": "remap-4001"})
    assert r.status_code == 200
    new_id = r.json()["version_id"]
    assert new_id != v_main_id

    rows = (await db_session.execute(select(ProfileVersion).where(ProfileVersion.profile_id == pid))).scalars().all()
    assert len(rows) == 2
    new_row = next(r for r in rows if r.id == new_id)
    assert new_row.branch_name == "remap-4001"
    assert new_row.profile_json == '{"account_mappings":[{"a":1}]}'
    assert new_row.is_current is False


# ── Task 7 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_activate_sets_only_one_current(db_session, client):
    pid = str(uuid.uuid4())
    v_a = str(uuid.uuid4())
    v_b = str(uuid.uuid4())
    db_session.add(AuditProfile(id=pid, engagement_name="X"))
    await db_session.flush()
    db_session.add(ProfileVersion(id=v_a, profile_id=pid, branch_name="main", profile_json="{}", is_current=True))
    db_session.add(ProfileVersion(id=v_b, profile_id=pid, branch_name="alt",  profile_json="{}", is_current=False))
    await db_session.commit()

    r = await client.patch(f"/api/audit-profiles/{pid}/versions/{v_b}/activate")
    assert r.status_code == 200

    rows = {r.id: r.is_current for r in (await db_session.execute(
        select(ProfileVersion).where(ProfileVersion.profile_id == pid)
    )).scalars().all()}
    assert rows == {v_a: False, v_b: True}


# ── Task 8 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compare_returns_json_diff(db_session, client):
    pid = str(uuid.uuid4())
    v1 = str(uuid.uuid4())
    v2 = str(uuid.uuid4())
    db_session.add(AuditProfile(id=pid, engagement_name="X"))
    await db_session.flush()
    db_session.add(ProfileVersion(id=v1, profile_id=pid, branch_name="main",
                             profile_json=json.dumps({"account_mappings": [{"acct": "4001", "group": "Rev"}]})))
    db_session.add(ProfileVersion(id=v2, profile_id=pid, branch_name="alt",
                             profile_json=json.dumps({"account_mappings": [{"acct": "4001", "group": "Sales"}]})))
    await db_session.commit()

    r = await client.get(f"/api/audit-profiles/{pid}/versions/{v1}/compare/{v2}")
    assert r.status_code == 200
    diff = r.json()
    assert "account_mappings" in diff["changed"]

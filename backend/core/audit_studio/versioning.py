"""Branching / compare / activate logic for audit profile versions."""
import json
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

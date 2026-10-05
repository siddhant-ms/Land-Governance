import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_db
from app.core.errors import not_found
from app.core.security import require
from app.models import User, Workspace, WorkspaceItem
from app.models.workspace import ITEM_TYPES

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceIn(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=2000)
    research_question: str = Field(default="", max_length=1000)


class ItemIn(BaseModel):
    item_type: str = Field(pattern="^(" + "|".join(ITEM_TYPES) + ")$")
    ref_id: str | None = Field(default=None, max_length=100)
    title: str = Field(default="", max_length=500)
    payload: dict = Field(default_factory=dict)
    note: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=20)


def item_out(i: WorkspaceItem) -> dict:
    return {"id": str(i.id), "item_type": i.item_type, "ref_id": i.ref_id, "title": i.title, "payload": i.payload,
            "note": i.note, "tags": i.tags, "created_at": i.created_at.isoformat()}


def ws_out(w: Workspace, items: bool = False) -> dict:
    counts: dict[str, int] = {}
    for i in w.items:
        counts[i.item_type] = counts.get(i.item_type, 0) + 1
    d = {"id": str(w.id), "title": w.title, "description": w.description, "research_question": w.research_question,
         "counts": counts, "updated_at": w.updated_at.isoformat(), "created_at": w.created_at.isoformat()}
    if items:
        d["items"] = [item_out(i) for i in w.items]
    return d


def mine(db: Session, wid: uuid.UUID, user: User) -> Workspace:
    w = db.get(Workspace, wid)
    if not w or w.deleted_at or w.owner_id != user.id:
        raise not_found("Workspace")
    return w


@router.post("", status_code=201)
def create(body: WorkspaceIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("workspace.write"))):
    w = Workspace(owner_id=user.id, **body.model_dump())
    db.add(w)
    db.commit()
    audit.record(db, request, user, "WORKSPACE_CREATED", "workspace", w.id)
    return ws_out(w)


@router.get("")
def list_all(db: Session = Depends(get_db), user: User = Depends(require("workspace.write"))):
    return [ws_out(w) for w in db.scalars(select(Workspace).where(Workspace.owner_id == user.id, Workspace.deleted_at.is_(None))
                                          .order_by(Workspace.updated_at.desc()))]


@router.get("/{wid}")
def get(wid: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require("workspace.write"))):
    return ws_out(mine(db, wid, user), items=True)


@router.post("/{wid}/items", status_code=201)
def add_item(wid: uuid.UUID, body: ItemIn, db: Session = Depends(get_db), user: User = Depends(require("workspace.write"))):
    w = mine(db, wid, user)
    if body.ref_id and body.item_type in ("document", "scenario", "map"):
        existing = next((i for i in w.items if i.item_type == body.item_type and i.ref_id == body.ref_id), None)
        if existing:
            return item_out(existing)  # idempotent save
    it = WorkspaceItem(workspace_id=w.id, **body.model_dump())
    db.add(it)
    w.updated_at = datetime.now(UTC)
    db.commit()
    return item_out(it)


@router.delete("/{wid}/items/{iid}", status_code=204)
def delete_item(wid: uuid.UUID, iid: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require("workspace.write"))):
    w = mine(db, wid, user)
    it = db.get(WorkspaceItem, iid)
    if not it or it.workspace_id != w.id:
        raise not_found("Item")
    db.delete(it)
    db.commit()


@router.get("/{wid}/brief")
def brief(wid: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(require("brief.export"))):
    w = mine(db, wid, user)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    L = [f"# Evidence brief: {w.title}", "", f"*Generated:* {now}  *Author:* {user.name}", ""]
    if w.research_question:
        L += ["## Research question", "", w.research_question, ""]
    by = lambda t: [i for i in w.items if i.item_type == t]  # noqa: E731
    answers = by("answer")
    if answers:
        L += ["## Cited findings", ""]
        for a in answers:
            for c in a.payload.get("claims", []):
                L.append(f"- {c['text']} {''.join(f'[{n}]' for n in c.get('numbers', []))}")
        L.append("")
    cites = [i for i in w.items if i.item_type in ("citation", "document")]
    if cites:
        L += ["## Sources", ""]
        for i, c in enumerate(cites, 1):
            p = c.payload
            demo = " **[DEMO]**" if p.get("is_demo") else ""
            L.append(f"{i}. {p.get('title', c.title)}{demo} — {p.get('organization', '')}, {p.get('publication_date', '')}"
                     + (f", p.{p['page']}" if p.get("page") else "") + (f" — <{p['source_url']}>" if p.get("source_url") else ""))
            if p.get("passage"):
                L.append(f"   > {p['passage'][:400]}")
            if c.note:
                L.append(f"   *Note:* {c.note}")
        L.append("")
    sc = by("scenario")
    if sc:
        L += ["## Scenarios", ""]
        for s in sc:
            L.append(f"### {s.title}")
            for o in s.payload.get("outputs", []):
                L.append(f"- {o['label']}: {o['baseline']:g} → {o['scenario']:g} ({o['delta_pct']}%)")
            L.append(f"  Model {s.payload.get('model_name', '')} v{s.payload.get('model_version', '')}; "
                     f"input hash `{s.payload.get('input_hash', '')}`. *Scenario estimate, not a guaranteed outcome.*")
        L.append("")
    notes = by("note")
    if notes:
        L += ["## Notes", ""] + [f"- {n.note}" for n in notes] + [""]
    L += ["---", "Exported briefs include provenance and timestamps. Items marked DEMO come from the prototype's synthetic corpus/data."]
    audit.record(db, request, user, "WORKSPACE_BRIEF_EXPORTED", "workspace", w.id)
    return {"filename": f"brief-{w.id}.md", "content_type": "text/markdown", "content": "\n".join(L)}

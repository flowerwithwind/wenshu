"""用户反馈 API 路由"""
from __future__ import annotations

import os
import json
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

feedback_router: APIRouter = APIRouter(prefix="/api", tags=["feedback"])

FEEDBACK_FILE: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "feedback.json")


class FeedbackRequest(BaseModel):
    message_id: str
    rating: str  # "like" 或 "dislike"
    comment: str | None = None


def _load_feedback() -> list[dict]:
    """加载反馈数据"""
    if not os.path.exists(FEEDBACK_FILE):
        return []
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_feedback(entries: list[dict]) -> None:
    """保存反馈数据"""
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


@feedback_router.post("/feedback")
async def submit_feedback(request: FeedbackRequest) -> dict:
    """记录用户反馈"""
    if request.rating not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="rating 必须为 'like' 或 'dislike'")

    feedback: dict = {
        "message_id": request.message_id,
        "rating": request.rating,
        "comment": request.comment,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    entries: list[dict] = _load_feedback()
    entries.append(feedback)
    _save_feedback(entries)

    return {"status": "ok", "feedback": feedback}


@feedback_router.get("/feedback/stats")
async def feedback_stats() -> dict:
    """反馈统计"""
    entries: list[dict] = _load_feedback()
    total: int = len(entries)
    likes: int = sum(1 for e in entries if e.get("rating") == "like")
    dislikes: int = sum(1 for e in entries if e.get("rating") == "dislike")
    like_rate: float = round(likes / total * 100, 1) if total > 0 else 0

    recent: list[dict] = sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)[:20]

    return {
        "total": total,
        "likes": likes,
        "dislikes": dislikes,
        "like_rate": like_rate,
        "recent": recent,
    }

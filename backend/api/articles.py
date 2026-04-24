"""文章观点 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import get_db

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("")
async def list_articles(category: str = None, limit: int = 20, offset: int = 0):
    db = await get_db()
    try:
        conditions = ["is_published=1"]
        params = []
        if category:
            conditions.append("category=?")
            params.append(category)

        where = " AND ".join(conditions)
        async with db.execute(
            f"SELECT COUNT(*) FROM articles WHERE {where}", params
        ) as cur:
            total = (await cur.fetchone())[0]

        async with db.execute(
            f"""SELECT id, title, summary, category, tag, view_count, created_at, updated_at
                FROM articles WHERE {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            params + [limit, offset]
        ) as cur:
            rows = await cur.fetchall()

        articles = []
        for r in rows:
            articles.append({
                "id": r[0], "title": r[1], "summary": r[2],
                "category": r[3], "tag": r[4].split(",") if r[4] else [],
                "view_count": r[5],
                "created_at": r[6], "updated_at": r[7],
            })
        return {"articles": articles, "total": total}
    finally:
        await db.close()


@router.get("/{article_id}")
async def get_article(article_id: int):
    db = await get_db()
    try:
        await db.execute("UPDATE articles SET view_count=view_count+1 WHERE id=?", (article_id,))
        await db.commit()

        async with db.execute(
            """SELECT id, title, summary, content, category, tag, view_count, created_at, updated_at
               FROM articles WHERE id=?""",
            (article_id,)
        ) as cur:
            r = await cur.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="文章不存在")
        return {
            "id": r[0], "title": r[1], "summary": r[2], "content": r[3],
            "category": r[4], "tag": r[5].split(",") if r[5] else [],
            "view_count": r[6], "created_at": r[7], "updated_at": r[8],
        }
    finally:
        await db.close()


class ArticleCreate(BaseModel):
    title: str
    summary: str = ""
    content: str = ""
    category: str = "market"
    tag: str = ""


@router.post("")
async def create_article(req: ArticleCreate):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO articles (title, summary, content, category, tag) VALUES (?,?,?,?,?)",
            (req.title, req.summary, req.content, req.category, req.tag)
        )
        await db.commit()
        return {"success": True}
    finally:
        await db.close()


@router.delete("/{article_id}")
async def delete_article(article_id: int):
    db = await get_db()
    try:
        await db.execute("DELETE FROM articles WHERE id=?", (article_id,))
        await db.commit()
        return {"success": True}
    finally:
        await db.close()

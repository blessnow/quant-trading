"""聊天 API — 智能投顾对话接口"""
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from database import get_db
from llm.chat_strategies import get_all_strategies, get_strategy_prompts
from llm.chat_agent import ChatAgent

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ─── 请求模型 ───────────────────────────────────────

class CreateSessionRequest(BaseModel):
    strategy_id: str
    title: Optional[str] = None


class SendMessageRequest(BaseModel):
    session_id: int
    content: str


# ─── 认证依赖 ───────────────────────────────────────

async def get_or_create_guest_user() -> int:
    """获取或创建访客用户"""
    db = await get_db()
    try:
        # 查找临时用户
        async with db.execute(
            "SELECT id FROM users WHERE openid = 'temp_guest'"
        ) as cur:
            row = await cur.fetchone()
            if row:
                return row[0]

        # 创建临时用户
        await db.execute(
            """INSERT INTO users (openid, nickname, login_type)
               VALUES ('temp_guest', '访客用户', 'guest')"""
        )
        await db.commit()

        async with db.execute(
            "SELECT id FROM users WHERE openid = 'temp_guest'"
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 1
    finally:
        await db.close()


async def get_current_user(request: Request):
    """从请求中获取当前用户，未登录返回访客用户"""
    # 从 cookie 或 header 获取 token
    token = request.cookies.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        # 未登录用户，返回访客用户
        return await get_or_create_guest_user()

    # 验证 token
    import jwt
    from config import JWT_SECRET

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if not user_id:
            return await get_or_create_guest_user()
        return user_id
    except jwt.ExpiredSignatureError:
        return await get_or_create_guest_user()
    except jwt.InvalidTokenError:
        return await get_or_create_guest_user()


# ─── API 接口 ───────────────────────────────────────

@router.get("/strategies")
async def list_strategies():
    """获取策略列表和提示词"""
    strategies = get_all_strategies()
    return {
        "strategies": [
            {
                "id": s.id,
                "name": s.name,
                "avatar": s.avatar,
                "color": s.color,
                "description": s.description,
                "prompts": [
                    {"title": p.title, "content": p.content, "icon": p.icon}
                    for p in s.prompts
                ]
            }
            for s in strategies
        ]
    }


@router.get("/sessions")
async def list_sessions(user_id: int = Depends(get_current_user)):
    """获取用户的会话列表"""
    db = await get_db()
    try:
        async with db.execute(
            """SELECT id, strategy_id, title, updated_at
               FROM chat_sessions
               WHERE user_id = ?
               ORDER BY updated_at DESC
               LIMIT 50""",
            (user_id,)
        ) as cur:
            rows = await cur.fetchall()
    finally:
        await db.close()

    return {
        "sessions": [
            {
                "id": row[0],
                "strategy_id": row[1],
                "title": row[2],
                "updated_at": row[3],
            }
            for row in rows
        ]
    }


@router.post("/sessions")
async def create_session(
    req: CreateSessionRequest,
    user_id: int = Depends(get_current_user),
):
    """创建新会话"""
    title = req.title or f"新对话 - {datetime.now().strftime('%m-%d %H:%M')}"

    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO chat_sessions (user_id, strategy_id, title)
               VALUES (?, ?, ?)""",
            (user_id, req.strategy_id, title)
        )
        await db.commit()
        session_id = cursor.lastrowid
    finally:
        await db.close()

    return {"session_id": session_id, "title": title}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    user_id: int = Depends(get_current_user),
):
    """删除会话及其消息"""
    db = await get_db()
    try:
        # 验证所有权
        async with db.execute(
            "SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id)
        ) as cur:
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="会话不存在")

        # 删除消息和会话
        await db.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        await db.commit()
    finally:
        await db.close()

    return {"success": True}


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: int,
    user_id: int = Depends(get_current_user),
):
    """获取会话的历史消息"""
    db = await get_db()
    try:
        # 验证所有权
        async with db.execute(
            "SELECT strategy_id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="会话不存在")
            strategy_id = row[0]

        # 获取消息
        async with db.execute(
            """SELECT id, role, content, tool_calls, created_at
               FROM chat_messages
               WHERE session_id = ?
               ORDER BY created_at ASC""",
            (session_id,)
        ) as cur:
            rows = await cur.fetchall()
    finally:
        await db.close()

    return {
        "strategy_id": strategy_id,
        "messages": [
            {
                "id": row[0],
                "role": row[1],
                "content": row[2],
                "tool_calls": json.loads(row[3]) if row[3] else None,
                "created_at": row[4],
            }
            for row in rows
        ]
    }


@router.post("/send")
async def send_message(
    req: SendMessageRequest,
    user_id: int = Depends(get_current_user),
):
    """发送消息，SSE 流式响应"""
    db = await get_db()
    try:
        # 验证会话
        async with db.execute(
            "SELECT strategy_id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (req.session_id, user_id)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="会话不存在")
            strategy_id = row[0]

        # 获取历史消息
        async with db.execute(
            """SELECT role, content, tool_calls FROM chat_messages
               WHERE session_id = ?
               ORDER BY created_at DESC
               LIMIT 20""",
            (req.session_id,)
        ) as cur:
            rows = await cur.fetchall()

        # 保存用户消息
        await db.execute(
            """INSERT INTO chat_messages (session_id, role, content)
               VALUES (?, ?, ?)""",
            (req.session_id, "user", req.content)
        )

        # 更新会话时间
        await db.execute(
            "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
            (req.session_id,)
        )
        await db.commit()
    finally:
        await db.close()

    # 构建历史消息
    from llm.chat_agent import ChatMessage
    messages = []
    for row in reversed(rows):
        messages.append(ChatMessage(
            role=row[0],
            content=row[1],
            tool_calls=json.loads(row[2]) if row[2] else [],
        ))

    # 获取用户持仓（暂时返回空列表）
    positions = []

    # 创建 Agent
    agent = ChatAgent(strategy_id)

    async def event_stream():
        """SSE 事件流"""
        full_content = ""
        tool_calls = []
        last_heartbeat = datetime.now()

        async def send_heartbeat():
            """发送心跳保持连接"""
            yield ": heartbeat\n\n"

        try:
            async for event in agent.chat_stream(messages, req.content, positions):
                # 每5秒发送心跳
                now = datetime.now()
                if (now - last_heartbeat).total_seconds() > 5:
                    yield ": heartbeat\n\n"
                    last_heartbeat = now

                logger.info(f"[SSE] 发送事件: {event['type']}")
                if event["type"] == "tool_call":
                    # 工具调用开始
                    tool_calls.append({
                        "name": event["name"],
                        "args": event["args"],
                    })
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': event['name'], 'args': event['args']}, ensure_ascii=False)}\n\n"

                elif event["type"] == "tool_result":
                    # 工具调用结果
                    if tool_calls:
                        tool_calls[-1]["result"] = event["result"]
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': event['name'], 'result': event['result'][:500]}, ensure_ascii=False)}\n\n"

                elif event["type"] == "content":
                    # 最终内容
                    full_content = event["content"]
                    logger.info(f"[SSE] 发送内容: {full_content[:100]}...")
                    yield f"data: {json.dumps({'type': 'content', 'content': event['content']}, ensure_ascii=False)}\n\n"

                elif event["type"] == "error":
                    yield f"data: {json.dumps({'type': 'error', 'content': event['content']}, ensure_ascii=False)}\n\n"

            # 保存助手消息
            db2 = await get_db()
            try:
                await db2.execute(
                    """INSERT INTO chat_messages (session_id, role, content, tool_calls)
                       VALUES (?, ?, ?, ?)""",
                    (req.session_id, "assistant", full_content, json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None)
                )
                await db2.commit()
            finally:
                await db2.close()

            logger.info("[SSE] 发送 [DONE]")
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[SSE] 错误: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

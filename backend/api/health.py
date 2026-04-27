"""系统健康检查 API"""
from fastapi import APIRouter

from database import get_db
from scheduler import scheduler

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check():
    """系统健康检查"""
    checks = {}

    # 数据库连接
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        await db.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:50]}"

    # 调度器状态
    try:
        jobs = scheduler.get_jobs()
        checks["scheduler"] = {
            "status": "running" if scheduler.running else "stopped",
            "jobs_count": len(jobs),
        }
    except Exception as e:
        checks["scheduler"] = f"error: {str(e)[:50]}"

    # 判断整体状态
    all_ok = all(
        v == "ok" or (isinstance(v, dict) and v.get("status") == "running")
        for v in checks.values()
    )

    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
    }

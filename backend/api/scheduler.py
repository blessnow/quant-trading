"""调度任务监控 API"""
from fastapi import APIRouter

from scheduler import scheduler

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/jobs")
async def get_jobs():
    """获取所有调度任务"""
    jobs = scheduler.get_jobs()
    return {
        "total": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "func": str(job.func),
                "trigger": str(job.trigger),
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "pending": job.pending,
            }
            for job in jobs
        ]
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """获取单个任务详情"""
    job = scheduler.get_job(job_id)
    if not job:
        return {"error": "任务不存在"}
    return {
        "id": job.id,
        "name": job.name,
        "func": str(job.func),
        "trigger": str(job.trigger),
        "next_run": str(job.next_run_time) if job.next_run_time else None,
        "pending": job.pending,
    }


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    """暂停任务"""
    job = scheduler.get_job(job_id)
    if not job:
        return {"error": "任务不存在"}
    scheduler.pause_job(job_id)
    return {"status": "paused", "job_id": job_id}


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """恢复任务"""
    job = scheduler.get_job(job_id)
    if not job:
        return {"error": "任务不存在"}
    scheduler.resume_job(job_id)
    return {"status": "resumed", "job_id": job_id}


@router.get("/status")
async def get_scheduler_status():
    """获取调度器状态"""
    jobs = scheduler.get_jobs()
    running = sum(1 for j in jobs if j.pending)
    return {
        "running": scheduler.running,
        "total_jobs": len(jobs),
        "pending_jobs": running,
    }

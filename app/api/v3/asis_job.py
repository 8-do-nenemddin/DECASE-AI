from fastapi import APIRouter, HTTPException

from sqlalchemy import select
from app.models.job import Job
from app.core.mysql_config import get_mysql_db

router = APIRouter()

@router.get("/as-is/{job_id}/status")
async def get_as_is_status(job_id: str):
    """
    As-Is 분석 상태 조회
    """
    async for db in get_mysql_db():
        job = await db.scalar(select(Job).where(Job.job_id == job_id))
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": job_id,
            "status": job.status,
            "start_time": job.start_time,
            "end_time": job.end_time,
        }

@router.get("/as-is/latest-status")
async def get_latest_as_is_status_by_project_member(
    project_id: int,
    member_id: int,
    job_name: str = "ASIS"
):
    """
    project_id, member_id, job_name으로 가장 최신 ASIS 분석 작업의 상태와 job_id 반환
    """
    async for db in get_mysql_db():
        stmt = (
            select(Job)
            .where(
                Job.project_id == project_id,
                Job.member_id == member_id,
                Job.name == job_name  
            )
            .order_by(Job.start_time.desc())
        )
        job = await db.scalar(stmt)
        if not job:
            raise HTTPException(status_code=404, detail="해당 project_id, member_id, job_name에 대한 작업이 없습니다.")
        return {
            "job_id": job.job_id,
            "status": job.status,
            "start_time": job.start_time,
            "end_time": job.end_time
        }
import asyncio

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from sqlalchemy import select

from app.models.job import JobNameEnum, JobStatusEnum
from app.models.member import Member
from app.models.project import Project
from app.services.asis_services import process_as_is_background
from app.services.job_services import create_job_in_db
from app.core.mysql_config import get_mysql_db

router = APIRouter()

@router.post("/as-is/start")
async def start_as_is_analysis(
        file: UploadFile = File(..., description="분석할 RFP PDF 파일"),
        project_id: int = Form(..., description="프로젝트 ID"),
        member_id: int = Form(..., description="멤버 ID"),
        callback_url: str = Form(..., description="결과를 전송할 콜백 URL"),
):
    """As-Is 분석 작업을 시작하고 Job ID를 반환합니다."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    try:
        pdf_content = await file.read()

        async for db in get_mysql_db():
            project = await db.scalar(select(Project).where(Project.project_id == project_id))
            member = await db.scalar(select(Member).where(Member.member_id == member_id))
            if not project or not member:
                raise HTTPException(status_code=404, detail="프로젝트 또는 멤버를 찾을 수 없습니다.")
            break

        new_job = await create_job_in_db(
            name=JobNameEnum.ASIS,
            project_id=project_id,
            member_id=member_id,
            revision_count=0,
            status=JobStatusEnum.PROCESSING
        )
        job_id = new_job.job_id

        asyncio.create_task(process_as_is_background(pdf_content, job_id, project_id, member_id, callback_url))
        
        return {
            "job_id": job_id,
            "status": JobStatusEnum.PROCESSING.value,
            "message": "As-Is 분석 작업이 시작되었습니다. Job ID로 상태를 확인하세요."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"작업 시작에 실패했습니다: {str(e)}")

import os
import asyncio
import traceback

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from concurrent.futures import ThreadPoolExecutor

from app.models.job import JobNameEnum, JobStatusEnum
from app.core.config import OUTPUT_UPLOADS_DIR, OUTPUT_SRS_DIR
from app.core.mysql_config import get_mysql_db
from app.models import Document, Member, Project
from sqlalchemy import select
from app.services.srs_services import update_job_status_in_db, process_srs_background
from app.services.job_services import create_job_in_db

router = APIRouter()

# 전역 스레드 풀 생성
thread_pool = ThreadPoolExecutor(max_workers=4)

os.makedirs(OUTPUT_UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUT_SRS_DIR, exist_ok=True)

@router.post("/srs-agent/start")
async def start_srs_analysis(
    file: UploadFile = File(..., description="분석할 RFP PDF 파일"),
    project_id: int = Form(None, description="프로젝트 ID"),
    member_id: int = Form(None, description="멤버 ID"),
    document_id: str = Form(None, description="문서 ID"),
    callback_url: str = Form(None, description="콜백 URL")
):
    """
    요구사항 분석 작업 시작 - Job ID 반환
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    try:
        async for db in get_mysql_db():
            # 프로젝트, 멤버 조회 (존재 확인)
            project = await db.scalar(select(Project).where(Project.project_id == project_id))
            member = await db.scalar(select(Member).where(Member.member_id == member_id))
            if not project or not member:
                raise HTTPException(status_code=404, detail="프로젝트 또는 멤버를 찾을 수 없습니다.")
            break

        # Job 생성
        new_job = await create_job_in_db(
            name=JobNameEnum.SRS,
            project_id=project_id,
            member_id=member_id,
            revision_count=0,
            status=JobStatusEnum.PROCESSING
        )
        job_id = new_job.job_id
        
        pdf_content = await file.read()
        
        asyncio.create_task(process_srs_background(pdf_content, job_id, file.filename, project_id, member_id, document_id, callback_url))
        
        return {
            "job_id": job_id,
            "job_name":JobNameEnum.SRS.value,
            "status": JobStatusEnum.PROCESSING.value,
            "message": "요구사항 분석을 시작합니다."
        }
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        error_message = f"요구사항 분석 시작 실패:\n{str(e)}\n\n상세 에러:\n{error_traceback}"
        print(error_message)
        
        if job_id is not None:
            await update_job_status_in_db(job_id, JobStatusEnum.FAILED, error_message)
            
        raise HTTPException(
            status_code=500,
            detail=f"요구사항 분석 시작 실패: {str(e)}"
        )
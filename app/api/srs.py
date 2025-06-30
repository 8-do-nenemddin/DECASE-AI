import os
import json
import asyncio
from typing import List
import httpx

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from concurrent.futures import ThreadPoolExecutor
from pydantic import TypeAdapter, ValidationError

from app.models.job import Job, JobNameEnum, JobStatusEnum
from app.schemas.requirement import SrsRequirementData
from app.core.config import OUTPUT_UPLOADS_DIR, OUTPUT_SRS_DIR
from datetime import datetime
from app.services.requirement_service import RequirementService
from app.core.mysql_config import get_mysql_db
from app.models import Document, Member, Project
from sqlalchemy import select
from app.services.srs_services import update_job_status_in_db, process_srs_background, srs_pipeline

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
        job_id = None

        # DB에 Job 생성
        async for db in get_mysql_db():
            # 프로젝트, 멤버 조회 (존재 확인)
            project = await db.scalar(select(Project).where(Project.project_id == project_id))
            member = await db.scalar(select(Member).where(Member.member_id == member_id))
            if not project or not member:
                raise HTTPException(status_code=404, detail="프로젝트 또는 멤버를 찾을 수 없습니다.")

            new_job = Job(
                name=JobNameEnum.SRS,
                project_id=project_id,
                member_id=member_id,
                revision_count=0,
                start_time=datetime.now(),
                end_time=None,
                status=JobStatusEnum.PROCESSING
            )
            db.add(new_job)
            await db.commit()
            await db.refresh(new_job)
            job_id = new_job.job_id
            break
        
        pdf_content = await file.read()
        
        asyncio.create_task(process_srs_background(pdf_content, job_id, file.filename, project_id, member_id, document_id, callback_url))
        
        return {
            "job_id": job_id,
            "job_name": "SRS",
            "status": "PROCESSING",
            "message": "요구사항 분석을 시작합니다."
        }
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_message = f"요구사항 분석 시작 실패:\n{str(e)}\n\n상세 에러:\n{error_traceback}"
        print(error_message)
        
        if job_id is not None:
            await update_job_status_in_db(job_id, JobStatusEnum.FAILED, error_message)
        raise HTTPException(
            status_code=500,
            detail=f"요구사항 분석 시작 실패: {str(e)}"
        )
import os
import json
import asyncio
from typing import List
import httpx

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from concurrent.futures import ThreadPoolExecutor
from pydantic import TypeAdapter, ValidationError

from app.models.job import Job, JobNameEnum, JobStatusEnum
from app.services.srs_services import srs_pipeline
from app.schemas.requirement import SrsRequirementData
from app.core.config import OUTPUT_UPLOADS_DIR, OUTPUT_SRS_DIR
from datetime import datetime
from app.services.requirement_service import RequirementService
from app.core.mysql_config import get_mysql_db
from app.models import Document, Member, Project
from sqlalchemy import select

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


async def process_srs_background(pdf_content: bytes, job_id: str, original_filename: str, project_id: int, member_id: int, document_id: str, callback_url: str):
    """요구사항 분석 처리"""
    try:
        print(f"\n=== 백그라운드 작업 시작 (Job ID: {job_id}) ===")
        print("\n--- 에이전트 1 & 2: 요구사항 식별, 명명, 분류, 상세설명 작업 중 ---")
        
        final_json_output = await asyncio.to_thread(
            srs_pipeline,
            pdf_content_bytes=pdf_content,
            output_path=os.path.join(OUTPUT_SRS_DIR, f"{job_id}_{original_filename}_requirements.json"),
        )
        
        print("\n=== 요구사항 명세서(SRS) 생성 완료 ===")
        # json 파일 파싱
        requirements_list = json.loads(final_json_output.decode('utf-8') if isinstance(final_json_output, bytes) else final_json_output)

        # 요구사항 명세서(SRS) 생성 완료 후 콜백 전송
        async with httpx.AsyncClient() as client:
            data = {
                "project_id": project_id,
                "member_id": member_id,
                "document_id": document_id,
                "status": "COMPLETED",
                "srs": requirements_list
            }

            try:
                response = await client.post(callback_url, json=data, timeout=60)
                print(f"Job[{job_id}]: 콜백 요청 완료. 응답 코드: {response.status_code}")
                if response.status_code != 200:
                    raise Exception(f"콜백 요청 실패: 응답 코드 {response.status_code}, 응답 내용: {response.text}")
                # 4. Job 완료 상태 업데이트
                await update_job_status_in_db(job_id, JobStatusEnum.COMPLETED, "요구사항 명세서(SRS) 생성 및 콜백 전송이 완료되었습니다.")
            except httpx.RequestError as e:
                print(f"Job[{job_id}]: 콜백 요청 실패: {e}")
                await update_job_status_in_db(job_id, JobStatusEnum.FAILED, f"콜백 전송 실패: {e}")
            except Exception as e:
                print(f"Job[{job_id}]: 콜백 요청 실패: {e}")
                await update_job_status_in_db(job_id, JobStatusEnum.FAILED, f"콜백 전송 실패: {e}")
     
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_message = f"요구사항 처리 중 오류 발생:\n{str(e)}\n\n상세 에러:\n{error_traceback}"
        print(error_message)
        await update_job_status_in_db(job_id, JobStatusEnum.FAILED, error_message)


async def update_job_status_in_db(job_id: int, status: JobStatusEnum, message: str = None):
    """Job 상태 업데이트"""
    async for db in get_mysql_db():
        job = await db.scalar(select(Job).where(Job.job_id == job_id))
        if job:
            job.status = status
            if status in [JobStatusEnum.COMPLETED, JobStatusEnum.FAILED]:
                job.end_time = datetime.now()
            await db.commit()
            await db.refresh(job)
        break


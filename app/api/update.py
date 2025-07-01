import json
import traceback
from typing import List, Any
from pydantic import parse_obj_as
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Form, UploadFile, File, Depends
from sqlalchemy import select

from app.services.update_service import process_update_background, UpdateRequest, RequirementItem
from app.services.job_services import update_job_status_in_db
from app.models import Member, Project
from app.models.job import Job, JobNameEnum, JobStatusEnum
from app.core.mysql_config import get_mysql_db

router = APIRouter()

@router.post("/meeting-analyze")
async def analyze_document_for_updates(
    background_tasks: BackgroundTasks,
    meeting_file: UploadFile = File(..., description="분석할 RFP PDF 파일"),
    requirements_str: str = Form(..., description="기존 요구사항 목록 (JSON 문자열)"),
    project_id: int = Form(..., description="프로젝트 ID"),
    member_id: int = Form(..., description="멤버 ID"),
    document_id: str = Form(None, description="문서 ID"),
    callback_url: str = Form(..., description="콜백 URL")
):
    """
    특정 프로젝트에 대해 문서를 업로드하여, 기존 요구사항 대비 변경 제안을 생성합니다.
    """
    if not meeting_file.filename:
        raise HTTPException(status_code=400, detail="업로드된 파일명이 없습니다.")

    job_id = None
    try:
        # 1. Form으로 받은 JSON 문자열을 Pydantic 모델 리스트로 파싱 및 검증
        try:
            requirements = parse_obj_as(List[RequirementItem], json.loads(requirements_str))
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"요구사항(requirements_str) 형식이 잘못되었습니다: {e}")

        # 2. 데이터베이스 연결 가져오기 및 Job 생성
        async for db in get_mysql_db():
            # 프로젝트, 멤버 조회 (존재 확인)
            project = await db.scalar(select(Project).where(Project.project_id == project_id))
            member = await db.scalar(select(Member).where(Member.member_id == member_id))
            if not project or not member:
                raise HTTPException(status_code=404, detail="프로젝트 또는 멤버를 찾을 수 없습니다.")

            new_job = Job(
                name=JobNameEnum.UPDATE,
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
            print(f"Job {job_id}가 생성되었습니다.")
            break
        

        # 3. 백그라운드 작업 준비
        file_content = await meeting_file.read()
        update_request_data = UpdateRequest(
            callback_url=callback_url,
            job_id=job_id,
            member_id=member_id,
            requirements=requirements,
            project_id=project_id,
            document_id=document_id
        )
        
        # 4. 백그라운드 작업 시작
        background_tasks.add_task(
            process_update_background,
            update_request_data,
            file_content
        )

        return {
            "job_id": job_id,
            "job_name": JobNameEnum.UPDATE.value,
            "status": JobStatusEnum.PROCESSING.value,
            "message": "요구사항 비교, 업데이트 분석을 시작합니다."
        }

    except Exception as e:
        error_traceback = traceback.format_exc()
        error_message = f"요구사항 분석 시작 실패:\n{str(e)}\n\n상세 에러:\n{error_traceback}"
        print(error_message)

        # DB에 Job이 생성된 후 다른 예외가 발생했다면 FAILED 처리
        if job_id:
            await update_job_status_in_db(job_id, JobStatusEnum.FAILED, error_message)

        raise HTTPException(
            status_code=500,
            detail=f"요구사항 분석 시작 실패: {str(e)}"
        )
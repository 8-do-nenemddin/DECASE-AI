import json
import traceback
from typing import List
from pydantic import parse_obj_as

from fastapi import APIRouter, HTTPException, BackgroundTasks, Form, UploadFile, File
from sqlalchemy import select

from app.services.update_service import process_update_background, UpdateRequest, RequirementItem
from app.services.job_services import update_job_status_in_db, create_job_in_db
from app.services.summary_meeting_service import process_meeting_summary_background
from app.models import Member, Project
from app.models.job import JobNameEnum, JobStatusEnum   
from app.core.mysql_config import get_mysql_db

router = APIRouter()

@router.post("/update")
async def analyze_and_summarize_document(
    background_tasks: BackgroundTasks,
    meeting_file: UploadFile = File(..., description="분석 및 요약할 문서 파일"),
    requirements_str: str = Form(..., description="기존 요구사항 목록 (JSON 문자열)"),
    project_id: int = Form(..., description="프로젝트 ID"),
    member_id: int = Form(..., description="멤버 ID"),
    document_id: str = Form(..., description="회의록 요약을 저장할 문서 ID"),
    callback_url: str = Form(..., description="요구사항 분석 콜백 URL")
):
    """
    문서를 업로드하여 [1]기존 요구사항 대비 변경 제안 생성과 [2]회의록 요약을 동시에 수행합니다.
    """
    if not meeting_file.filename:
        raise HTTPException(status_code=400, detail="업로드된 파일명이 없습니다.")

    job_id = None # job_id를 try 블록 시작 부분에서 초기화합니다.
    try:
        # 1. 입력 값 파싱 및 유효성 검사
        try:
            requirements = parse_obj_as(List[RequirementItem], json.loads(requirements_str))
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"요구사항(requirements_str) 형식이 잘못되었습니다: {e}")

        # 2. 데이터베이스 연결 및 Job 생성 (요구사항 분석 작업용)
        async for db in get_mysql_db():
            project = await db.scalar(select(Project).where(Project.project_id == project_id))
            member = await db.scalar(select(Member).where(Member.member_id == member_id))
            if not project or not member:
                raise HTTPException(status_code=404, detail="프로젝트 또는 멤버를 찾을 수 없습니다.")
            break
            
        new_job = await create_job_in_db(
            name=JobNameEnum.UPDATE,
            project_id=project_id,
            member_id=member_id,
            revision_count=0, # 필요시 수정
            status=JobStatusEnum.PROCESSING
        )
        job_id = new_job.job_id

        # 3. 파일 내용을 한 번만 읽기
        file_content = await meeting_file.read()

        # 4. 백그라운드 작업 준비 및 시작
        # 4-1. 요구사항 변경 분석 작업
        update_request_data = UpdateRequest(
            callback_url=callback_url,
            job_id=job_id,
            member_id=member_id,
            requirements=requirements,
            project_id=project_id,
            document_id=document_id
        )
        background_tasks.add_task(
            process_update_background,
            update_request_data,
            file_content # 바이트(bytes) 그대로 전달
        )

        # 4-2. 회의록 요약 작업 (<<< 추가된 부분)
        try:
            meeting_text = file_content.decode('utf-8')
            background_tasks.add_task(
                process_meeting_summary_background,
                document_id=document_id,
                meeting_text=meeting_text # 디코딩된 텍스트(string) 전달
            )
        except UnicodeDecodeError:
            # 텍스트 파일이 아닐 경우 요약 작업은 건너뛰거나, 여기서 에러 처리를 할 수 있습니다.
            # 여기서는 경고만 출력하고 넘어가도록 처리합니다.
            print(f"경고: 파일 '{meeting_file.filename}'은 UTF-8 텍스트가 아니므로 요약 작업을 건너뜁니다.")


        # 5. API 응답 반환
        return {
            "job_id": job_id,
            "job_name": JobNameEnum.UPDATE.value,
            "status": JobStatusEnum.PROCESSING.value,
            "message": "요구사항 분석 및 회의록 요약 작업을 시작합니다." # <<< 수정된 메시지
        }

    except Exception as e:
        error_traceback = traceback.format_exc()
        error_message = f"작업 시작 실패:\n{str(e)}\n\n상세 에러:\n{error_traceback}"
        print(error_message)

        # DB에 Job이 생성된 후 다른 예외가 발생했다면 FAILED 처리
        if job_id:
            await update_job_status_in_db(job_id, JobStatusEnum.FAILED, error_message)

        raise HTTPException(
            status_code=500,
            detail=f"작업 시작 실패: {str(e)}"
        )
import json
import traceback
from typing import List
from pydantic import parse_obj_as

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, UploadFile, File
from sqlalchemy import select

# ✨ 새로 만든 파일 처리 서비스를 임포트합니다.
from app.services.file_processing_service import extract_text_from_file

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
    extra_file: UploadFile = File(..., description="분석 및 요약할 문서 파일(txt, pdf, docx, wav 등)"),
    requirements_str: str = Form(..., description="기존 요구사항 목록 (JSON 문자열)"),
    project_id: int = Form(..., description="프로젝트 ID"),
    member_id: int = Form(..., description="멤버 ID"),
    document_id: str = Form(..., description="회의록 요약을 저장할 문서 ID"),
    callback_url: str = Form(..., description="요구사항 분석 콜백 URL")
):
    """
    다양한 형식의 문서를 업로드하여 [1]요구사항 변경 제안 생성과 [2]회의록 요약을 동시에 수행합니다.
    """
    if not extra_file.filename:
        raise HTTPException(status_code=400, detail="업로드된 파일명이 없습니다.")

    job_id = None
    try:
        # 1. 파일 내용을 한 번만 읽고, 텍스트로 변환
        file_content_bytes = await extra_file.read()
        try:
            # ✨ 파일 처리 서비스를 호출하여 텍스트 추출
            extracted_text = await extract_text_from_file(file_content_bytes, extra_file.filename)
        except ValueError as e:
            # 지원하지 않는 파일 형식인 경우 400 에러 반환
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            # 파일 처리 중 다른 오류 발생 시 500 에러 반환
            raise HTTPException(status_code=500, detail=f"파일 처리 중 오류 발생: {e}")

        # 2. 입력 값 파싱 및 DB Job 생성
        requirements = parse_obj_as(List[RequirementItem], json.loads(requirements_str))
        
        async for db in get_mysql_db(): # DB 연결 확인용
            project = await db.scalar(select(Project).where(Project.project_id == project_id))
            member = await db.scalar(select(Member).where(Member.member_id == member_id))
            if not project or not member:
                raise HTTPException(status_code=404, detail="프로젝트 또는 멤버를 찾을 수 없습니다.")
            break
            
        new_job = await create_job_in_db(...) # 파라미터 생략
        job_id = new_job.job_id

        # 3. 백그라운드 작업 준비 및 시작
        # 3-1. 요구사항 변경 분석 작업
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
            extracted_text # ✨ 추출된 텍스트 전달
        )

        # 3-2. 회의록 요약 작업
        background_tasks.add_task(
            process_meeting_summary_background,
            document_id=document_id,
            meeting_text=extracted_text # ✨ 추출된 텍스트 전달
        )

        # 4. API 즉시 응답 반환
        return { "job_id": job_id, "message": "파일 분석 및 요약 작업을 시작합니다." }

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
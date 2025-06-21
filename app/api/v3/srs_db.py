import os
import json
import uuid
import asyncio
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from concurrent.futures import ThreadPoolExecutor
from pydantic import TypeAdapter, ValidationError

from app.services.srs_services import srs_pipeline
from app.schemas.requirement import SrsRequirementData
from app.core.config import OUTPUT_UPLOADS_DIR, OUTPUT_SRS_DIR
from app.api.v2.jobs import job_store, update_job_status
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
    document_id: str = Form(None, description="문서 ID")
):
    """
    요구사항 분석 작업 시작 - Job ID 반환
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    try:
        # Job ID 생성
        job_id = str(uuid.uuid4())
        
        # 파일 내용 읽기
        pdf_content = await file.read()
        
        # 초기 작업 상태 설정
        job_store[job_id] = {
            "job_name": "SRS",
            "status": "PROCESSING",
            "message": "요구사항 분석을 시작합니다.",
            "result": None,
            "error": None,
            "project_id": project_id,
            "member_id": member_id,
            "document_id": document_id,
            "start_time": datetime.now().isoformat()
        }
        
        # 비동기 작업 시작
        asyncio.create_task(process_srs_background(pdf_content, job_id, file.filename))
        
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
        
        # 에러 발생 시 job_store 업데이트
        if 'job_id' in locals():
            update_job_status(
                job_id=job_id,
                status="FAILED",
                result=None,
                error=error_message
            )
        raise HTTPException(
            status_code=500,
            detail=f"요구사항 분석 시작 실패: {str(e)}"
        )


async def process_srs_background(pdf_content: bytes, job_id: str, original_filename: str):
    """(개선) 백그라운드에서 임시 파일 없이 요구사항 분석 처리"""
    try:
        print(f"\n=== 백그라운드 작업 시작 (Job ID: {job_id}) ===")
        print("\n--- 에이전트 1 & 2: 요구사항 식별, 명명, 분류, 상세설명 작업 중 ---")
        
        # 2. 파일 내용(bytes)을 에이전트 함수에 직접 전달
        final_json_output = await asyncio.to_thread(
            srs_pipeline,
            pdf_content_bytes=pdf_content,
            output_path=os.path.join(OUTPUT_SRS_DIR, f"{job_id}_{original_filename}_requirements.json"),
        )
        
        print("\n=== 요구사항 저장 프로세스 시작 ===")
        
        try:
            # Pydantic TypeAdapter를 사용하여 JSON을 객체 리스트로 파싱
            requirements_list = TypeAdapter(List[SrsRequirementData]).validate_python(json.loads(final_json_output))
        except (json.JSONDecodeError, ValidationError) as e:
            error_message = f"SRS 파이프라인 결과 파싱 오류: {e}"
            print(error_message)
            raise Exception(error_message)

        await save_requirements_to_db(requirements_list, job_store[job_id])

        # 4. 성공 시 Job 상태 업데이트 (추가하면 좋음)
        update_job_status(job_id, status="COMPLETED", message="요구사항 명세서(SRS) 분석 및 저장이 완료되었습니다.")
        
    except Exception as e:
        # (기존 에러 처리 로직과 동일)
        import traceback
        error_traceback = traceback.format_exc()
        error_message = f"요구사항 처리 중 오류 발생:\n{str(e)}\n\n상세 에러:\n{error_traceback}"
        print(error_message)
        update_job_status(job_id=job_id, status="FAILED", error=error_message)

async def save_requirements_to_db(processed_results: List[SrsRequirementData], job_info):
    """
    요구사항 리스트를 DB에 저장하는 함수
    """
    async for db in get_mysql_db():
        print(f"DB 연결 성공")
        project_id = job_info.get("project_id")
        member_id = job_info.get("member_id")
        document_id = job_info.get("document_id")

        print(f"ID 정보 - Project: {project_id}, Member: {member_id}, Document: {document_id}")

        if not all([project_id, member_id, document_id]):
            print("ERROR: 필수 ID 누락")
            raise Exception("프로젝트 ID, 멤버 ID, 문서 ID가 필요합니다.")
        
        # 관련 엔티티 조회
        project_query = select(Project).where(Project.project_id == project_id)
        member_query = select(Member).where(Member.member_id == member_id)
        document_query = select(Document).where(Document.doc_id == document_id)

        print(f"\n문서 ID 조회: {document_id}")
        print(f"문서 쿼리: {document_query}")

        project_result = await db.execute(project_query)
        member_result = await db.execute(member_query)
        document_result = await db.execute(document_query)

        project = project_result.scalar_one_or_none()
        member = member_result.scalar_one_or_none()
        document = document_result.scalar_one_or_none()

        print(f"엔티티 조회 결과 - Project: {project is not None}, Member: {member is not None}, Document: {document is not None}")
        
        if document is None:
            print(f"문서를 찾을 수 없습니다. document_id: {document_id}")
        
        if not all([project, member, document]):
            print("ERROR: 엔티티 조회 실패")
            raise Exception("프로젝트, 멤버, 또는 문서를 찾을 수 없습니다.")
        
        # RequirementService를 사용하여 요구사항 저장
        print("\n=== 요구사항 저장 시작 ===")
        requirement_service = RequirementService(db)
        # 요구사항을 순차적으로 저장
        for idx, requirement in enumerate(processed_results, 1):
            print(f"\n요구사항 {idx}/{len(processed_results)} 저장 시도:")
            # Pydantic 모델을 json으로 변환하여 로그 출력 (가독성 향상)
            print(f"요구사항 데이터: {requirement.model_dump_json(indent=2)}")
            try:
                await requirement_service.create_requirement(requirement, member, project, document)
                print(f"요구사항 {idx} 저장 성공")
            except Exception as e:
                print(f"ERROR: 요구사항 {idx} 저장 실패 - {str(e)}")
                raise
        print("\n=== 모든 요구사항 저장 완료 ===")
        break

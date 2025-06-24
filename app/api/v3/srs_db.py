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
        job_id = str(uuid.uuid4())
        pdf_content = await file.read()
        
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
        
        final_json_output = await asyncio.to_thread(
            srs_pipeline,
            pdf_content_bytes=pdf_content,
            output_path=os.path.join(OUTPUT_SRS_DIR, f"{job_id}_{original_filename}_requirements.json"),
        )
        
        print("\n=== 요구사항 저장 프로세스 시작 ===")
        
        try:
            requirements_list = TypeAdapter(List[SrsRequirementData]).validate_python(json.loads(final_json_output))
        except (json.JSONDecodeError, ValidationError) as e:
            error_message = f"SRS 파이프라인 결과 파싱 오류: {e}"
            print(error_message)
            raise Exception(error_message)

        # *** 변경점: 트랜잭션 관리가 포함된 배치 처리 함수 호출 ***
        await save_requirements_to_db_batched(requirements_list, job_store[job_id])

        update_job_status(job_id, status="COMPLETED", message="요구사항 명세서(SRS) 분석 및 저장이 완료되었습니다.")
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_message = f"요구사항 처리 중 오류 발생:\n{str(e)}\n\n상세 에러:\n{error_traceback}"
        print(error_message)
        update_job_status(job_id=job_id, status="FAILED", error=error_message)

async def save_requirements_to_db_batched(processed_results: List[SrsRequirementData], job_info):
    """
    (개선) 요구사항 리스트를 DB에 '배치'로 저장하고, 트랜잭션을 명시적으로 관리하는 함수
    """
    BATCH_SIZE = 100 

    async for db in get_mysql_db():
        try:
            print(f"DB 연결 성공")
            project_id = job_info.get("project_id")
            member_id = job_info.get("member_id")
            document_id = job_info.get("document_id")

            if not all([project_id, member_id, document_id]):
                raise Exception("프로젝트 ID, 멤버 ID, 문서 ID가 필요합니다.")

            # --- 관련 엔티티 조회 (작업 시작 전 한번만) ---
            project = await db.scalar(select(Project).where(Project.project_id == project_id))
            member = await db.scalar(select(Member).where(Member.member_id == member_id))
            document = await db.scalar(select(Document).where(Document.doc_id == document_id))

            if not all([project, member, document]):
                raise Exception(f"프로젝트, 멤버, 또는 문서를 찾을 수 없습니다. (P:{project_id}, M:{member_id}, D:{document_id})")

            requirement_service = RequirementService(db)
            total_count = len(processed_results)
            print(f"\n=== 총 {total_count}개의 요구사항 저장 시작 (배치 크기: {BATCH_SIZE}) ===")

            # --- 배치 처리를 위한 루프 ---
            for i in range(0, total_count, BATCH_SIZE):
                batch = processed_results[i:i + BATCH_SIZE]
                print(f"\n--- 배치 {i//BATCH_SIZE + 1} 처리 중 ({i+1} ~ {min(i + BATCH_SIZE, total_count)}번 항목) ---")
                
                # 배치 내의 모든 요구사항을 순차적으로 서비스에 전달
                for idx, requirement in enumerate(batch, i + 1):
                    await requirement_service.create_requirement(requirement, member, project, document)
                
                await db.commit()
                print(f"--- 배치 {i//BATCH_SIZE + 1} 커밋 완료 ---")

            print("\n=== 모든 요구사항 저장 완료 ===")

        except Exception as e:
            print(f"!!! 에러 발생: 트랜잭션을 롤백합니다. 원인: {e}")
            await db.rollback()
            raise 
        finally:
            print("DB 세션 리소스 정리 완료")
            break

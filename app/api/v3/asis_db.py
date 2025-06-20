import os
import uuid
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pathlib import Path
from datetime import datetime
from app.core.config import OUTPUT_ASIS_DIR
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.core.mysql_config import get_mysql_db

# 수정된 서비스 함수 import
from app.services.asis_services import asis_pipeline
from app.api.v2.jobs import job_store, update_job_status

router = APIRouter()

# --- 백그라운드 작업 처리 ---
async def process_as_is_background(pdf_content: bytes, job_id: str):
    """백그라운드에서 As-Is 분석 파이프라인을 처리합니다."""
    try:
        job = job_store[job_id]
        project_id = job.get("project_id")
        member_id = job.get("member_id")
        document_id = job.get("document_id")

        if not (project_id and member_id):
            raise ValueError("Job에 project_id 또는 member_id가 설정되지 않았습니다.")
            
        # 1. 최종 저장될 파일 경로를 '미리' 생성
        upload_dir = Path(OUTPUT_ASIS_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ASIS_REPORT_{project_id}_{timestamp}.pdf"
        output_pdf_path = upload_dir / filename

        # 2. 분석 함수를 호출하여 파일 저장 및 바이트 반환을 동시에 수행
        print(f"Job[{job_id}]: 백그라운드 분석/저장 시작...")
        result_pdf_bytes = await asyncio.to_thread(
            asis_pipeline, 
            pdf_content,
            output_pdf_path  # 생성한 파일 경로 전달
        )

        # 3. DB에 메타데이터 기록
        saved_doc_info = None
        async for db in get_mysql_db():
            document_repository = DocumentRepository(db)
            saved_doc = await create_document_record(
                filename=filename,
                file_path=str(output_pdf_path),
                project_id=project_id,
                member_id=member_id,
                document_repository=document_repository
            )
            saved_doc_info = saved_doc.to_dict()
            break
        
        # 4. Job 완료 상태 업데이트
        # result에는 DB 저장 정보만 포함 (바이트는 너무 크므로 제외)
        update_job_status(
            job_id=job_id,
            status="COMPLETED",
            message="As-Is 분석 및 파일 저장이 완료되었습니다.",
            result={"saved_document": saved_doc_info}
        )
        
    except Exception as e:
        print(f"Job[{job_id}]: 처리 중 오류 발생 - {e}")
        update_job_status(job_id=job_id, status="FAILED", message=f"As-Is 분석 실패: {e}", error=str(e))


# --- DB 저장 유틸리티 (수정됨) ---
async def create_document_record(filename: str, file_path: str, project_id: int, member_id: int, document_repository: DocumentRepository) -> Document:
    """
    (수정됨) 파일 저장 로직 없이, 파일 메타데이터를 DB에 기록만 합니다.
    """
    try:
        new_doc_id = await generate_doc_id("ASIS", document_repository)
        doc = Document(
            doc_id=new_doc_id,
            name=filename,
            path=file_path,
            created_date=datetime.now(),
            is_member_upload=False,
            member_id=member_id,
            project_id=project_id
        )
        return await document_repository.save(doc)
    except Exception as e:
        raise Exception(f"DB에 문서 정보 저장 실패: {e}")

# (generate_doc_id, start_as_is_analysis 함수는 이전과 동일하게 사용)
async def generate_doc_id(type_prefix: str, document_repository: DocumentRepository) -> str:
    """Generate an incremental document ID with the given prefix"""
    try:
        # Find the latest document ID with the given prefix
        doc_id = await document_repository.find_latest_doc_id_by_prefix(type_prefix)
        next_number = 1

        if doc_id:
            # Extract the number part from the latest ID (e.g., "ASIS-000123" -> "000123")
            try:
                number_part = doc_id.split("-")[1]
                print(f"Number part: {number_part}")
                next_number = int(number_part) + 1
            except (IndexError, ValueError) as e:
                raise ValueError(f"Invalid docId format: {doc_id}")

        # Format the new ID with leading zeros
        return f"{type_prefix}-{next_number:06d}"
    except Exception as e:
        raise Exception(f"Failed to generate document ID: {str(e)}")
    
@router.post("/as-is/start")
async def start_as_is_analysis(
    file: UploadFile = File(..., description="분석할 RFP PDF 파일"),
    project_id: int = Form(..., description="프로젝트 ID"),
    member_id: int = Form(..., description="멤버 ID"),
    document_id: str = Form(None, description="원본 문서 ID (선택 사항)")
):
    """As-Is 분석 작업을 시작하고 Job ID를 반환합니다."""
    # ... (이전과 동일)
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
        
    job_id = str(uuid.uuid4())
    try:
        pdf_content = await file.read()
        
        job_store[job_id] = {
            "job_name": "ASIS",
            "status": "PROCESSING",
            "message": "As-Is 분석을 시작합니다.",
            "result": None,
            "error": None,
            "project_id": project_id,
            "member_id": member_id,
            "document_id": document_id,
            "start_time": datetime.now().isoformat(),
            "end_time": None
        }
        
        asyncio.create_task(process_as_is_background(pdf_content, job_id))
        
        return {
            "job_id": job_id,
            "status": "PROCESSING",
            "message": "As-Is 분석 작업이 시작되었습니다. Job ID로 상태를 확인하세요."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"작업 시작에 실패했습니다: {str(e)}")
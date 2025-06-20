import os
import json
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from concurrent.futures import ThreadPoolExecutor
from app.schemas.requirement import ProcessResponse
from app.graph.rfp_graph import get_rfp_graph_app
from app.services.srs_services import process_requirements_in_memory
from app.core.config import OPENAI_API_KEY, GPT_MODEL
from app.agents.srs.req_extract_agent import extract_requirement_sentences_agent
from app.agents.srs.req_refine_agent import name_classify_describe_requirements_agent
from app.services.file_processing_service import extract_pages_as_documents, create_chunks_from_documents
from app.core.config import OUTPUT_UPLOADS_DIR, OUTPUT_SRS_DIR, CHUNK_SIZE, CHUNK_OVERLAP
from app.api.v2.jobs import job_store, update_job_status

router = APIRouter()
compiled_app = get_rfp_graph_app()

# 전역 스레드 풀 생성
thread_pool = ThreadPoolExecutor(max_workers=4)

os.makedirs(OUTPUT_UPLOADS_DIR, exist_ok=True)
os.makedirs("app/docs", exist_ok=True)


@router.post("/srs-agent/start")
async def start_srs_analysis(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="분석할 RFP PDF 파일")
):
    """
    요구사항 분석 작업 시작 - Job ID 반환
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    # Job ID 생성
    job_id = str(uuid.uuid4())
    
    # 파일 내용 읽기
    pdf_content = await file.read()
    
    # 초기 작업 상태 설정
    job_store[job_id] = {
        "status": "PROCESSING",
        "message": "요구사항 분석을 시작합니다.",
        "result": None,
        "error": None
    }
    
    # 백그라운드에서 처리 시작
    background_tasks.add_task(process_srs_background, pdf_content, job_id, file.filename)
    
    return {
        "job_id": job_id,
        "message": "요구사항 분석을 시작합니다.",
        "state": "PROCESSING"
    }

@router.get("/srs-agent/{job_id}/status")
async def get_srs_status(job_id: str):
    """
    요구사항 분석 상태 조회
    """
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_store[job_id]
    
    # Create response data
    response_data = {
        "job_id": job_id,
        "state": job["status"],
        "message": job.get("message", ""),
        "requirements": job.get("result", []) if job["status"] == "COMPLETED" else []
    }
    
    # Save to JSON file
    output_filename = f"status_{job_id}.json"
    output_path = os.path.join("app/docs", output_filename)
    
    with open(output_path, "w", encoding="utf-8") as json_file:
        json.dump(response_data, json_file, ensure_ascii=False, indent=4)
    
    return response_data

def process_srs_background(pdf_content: bytes, job_id: str, original_filename: str):
    """백그라운드에서 요구사항 분석 처리"""
    try:
        # 임시 파일 저장
        unique_id = uuid.UUID(job_id)
        temp_pdf_path = os.path.abspath(os.path.join(OUTPUT_UPLOADS_DIR, f"temp_{unique_id}_{original_filename}"))
        
        try:
            with open(temp_pdf_path, "wb") as f:
                f.write(pdf_content)
            
            # PDF 처리 및 요구사항 추출
            pages_as_docs = extract_pages_as_documents(temp_pdf_path)
            chunked_docs = create_chunks_from_documents(pages_as_docs, CHUNK_SIZE, CHUNK_OVERLAP)
            
            all_classified_requirements = []
            print("\n--- 에이전트 1 & 2: 요구사항 식별, 명명, 분류, 상세설명 작업 중 ---")
            
            for i, chunk_doc in enumerate(chunked_docs):
                chunk_text = chunk_doc.page_content
                page_num = chunk_doc.metadata.get("page_number", "N/A")

                print(f"\n[청크 {i+1}/{len(chunked_docs)} 처리중 (페이지: {page_num})]")
                if len(chunk_text.strip()) < 50:
                    print(f"  청크 {i+1}이 너무 짧아 건너뜁니다.")
                    continue
                
                req_sentences = extract_requirement_sentences_agent(chunk_text)
                
                if req_sentences:
                    print(f"  청크 {i+1}에서 식별된 잠재적 요구사항 문장 ({len(req_sentences)}개):")
                    for sent_idx, sentence in enumerate(req_sentences):
                        print(f"    문장 {sent_idx+1}/{len(req_sentences)} 분석 중: '{sentence[:60]}...'")
                        classified_req = name_classify_describe_requirements_agent(
                            requirement_sentence=sentence,
                            source_chunk_text=chunk_text,
                            page_number=page_num
                        )
                        if classified_req:
                            requirement_data = {
                                "description_name": classified_req.get("요구사항명", ""),
                                "type": classified_req.get("type", ""),
                                "description_content": classified_req.get("요구사항 상세설명", ""),
                                "target_task": classified_req.get("대상업무", ""),
                                "rfp_page": classified_req.get("RFP", 0),
                                "processing_detail": classified_req.get("요건처리 상세", ""),
                                "raw_text": classified_req.get("출처 문장", "")
                            }
                            all_classified_requirements.append(requirement_data)
            
            # 요구사항 처리
            processed_results = process_requirements_in_memory(all_classified_requirements, compiled_app)
            
            # 결과 저장
            output_filename = f"processed_{unique_id}_{original_filename}.json"
            output_json_path = os.path.join(OUTPUT_SRS_DIR, output_filename)
            os.makedirs(OUTPUT_SRS_DIR, exist_ok=True)
            
            with open(output_json_path, "w", encoding="utf-8") as json_file:
                json.dump(processed_results, json_file, ensure_ascii=False, indent=4)
            
            # 작업 완료 상태 업데이트
            update_job_status(
                job_id=job_id,
                status="COMPLETED",
                result=processed_results,
                error=None
            )
            
        finally:
            # 임시 파일 정리
            if os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                    print(f"임시 파일 '{temp_pdf_path}' 삭제 완료.")
                except Exception as e_del:
                    print(f"임시 파일 '{temp_pdf_path}' 삭제 실패: {e_del}")
                    
    except Exception as e:
        # 실패 상태로 업데이트
        update_job_status(
            job_id=job_id,
            status="FAILED",
            result=None,
            error=str(e)
        )
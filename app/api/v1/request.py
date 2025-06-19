# app/api/v1/change_request_router.py
import os
import json
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Form, UploadFile, File
from app.schemas.request import ProcessMeetingRequest, ProcessMeetingResponse, ChangeRequestResultItem
from app.services.change_request_service import process_meeting_for_change_requests, summarize_and_save_meeting
from app.core.config import INPUT_DIR, FAISS_INDEX_DIR, METADATA_STORAGE_DIR

from fastapi import Depends
from app.core.mysql_config import get_mysql_db


router = APIRouter()

def process_meeting_background_task(
    task_id: str,
    meeting_content: str, # 파일 내용을 직접 전달
    faiss_index_name: str,
    metadata_name: str,
    top_k: int
):
    print(f"백그라운드 회의록 분석 시작 (Task ID: {task_id})")
    try:
        results = process_meeting_for_change_requests(
            meeting_content,
            faiss_index_name,
            metadata_name,
            top_k
        )
        # TODO: 결과를 DB 또는 파일에 저장 (task_id 사용)
        output_filename = os.path.join(INPUT_DIR, f"cr_results_{task_id}.json") # 예시 저장 경로
        with open(output_filename, "w", encoding="utf-8") as f:
            json_results = [item.model_dump() for item in results] # Pydantic 모델을 dict로 변환
            json.dump(json_results, f, ensure_ascii=False, indent=2)
        print(f"백그라운드 회의록 분석 완료 (Task ID: {task_id}). 결과: {output_filename}")

    except Exception as e:
        print(f"백그라운드 회의록 분석 중 오류 (Task ID: {task_id}): {e}")
        # TODO: 작업 실패 상태 기록

@router.post("/process-meeting-minutes", response_model=ProcessMeetingResponse)
async def endpoint_process_meeting_minutes(
    background_tasks: BackgroundTasks,
    meeting_file_id: str = Form(..., description="RDB에 저장된 회의록 id"),
    meeting_file: UploadFile = File(..., description="분석할 회의록 파일 (txt, md 등 텍스트 파일)"),
    faiss_index_name: str = Form(..., description="사용할 FAISS 인덱스 파일명 (예: existing_requirements.faiss)"),
    metadata_name: str = Form(..., description="사용할 메타데이터 파일명 (예: existing_requirements_metadata.json)"),
    top_k: Optional[int] = Form(1, description="유사도 검색 시 반환할 상위 결과 개수"),
    db = Depends(get_mysql_db)
):
    # FAISS 인덱스 및 메타데이터 파일 존재 여부 확인
    if not os.path.exists(os.path.join(FAISS_INDEX_DIR, faiss_index_name)):
        raise HTTPException(status_code=404, detail=f"FAISS 인덱스 파일 '{faiss_index_name}'을 찾을 수 없습니다.")
    if not os.path.exists(os.path.join(METADATA_STORAGE_DIR, metadata_name)):
        raise HTTPException(status_code=404, detail=f"메타데이터 파일 '{metadata_name}'을 찾을 수 없습니다.")

    try:
        meeting_content_bytes = await meeting_file.read()
        meeting_content_text = meeting_content_bytes.decode('utf-8') # 인코딩 주의
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"회의록 파일 읽기 오류: {e}")
    finally:
        await meeting_file.close()

    if not meeting_content_text.strip():
        raise HTTPException(status_code=400, detail="회의록 내용이 비어있습니다.")

    task_id = str(uuid.uuid4())

    summarize_and_save_meeting(db, meeting_file_id, meeting_file)

    background_tasks.add_task(
        process_meeting_background_task,
        task_id,
        meeting_content_text,
        faiss_index_name,
        metadata_name,
        top_k
    )

    return ProcessMeetingResponse(
        message="회의록 분석 및 변경 요청 추출 작업이 백그라운드에서 시작되었습니다.",
        task_id=task_id
        # 결과는 별도의 API를 통해 task_id로 조회하거나, 완료 알림 후 제공
    )
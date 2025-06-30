# app/api/v1/faiss_router.py
import os
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Form, UploadFile, File
from app.schemas.faiss import CreateFaissIndexRequest, FaissIndexCreationResponse
from app.services.background_faiss_service import create_faiss_index_background_task
from app.core.config import OUTPUT_SRS_DIR, FAISS_INDEX_DIR, METADATA_STORAGE_DIR

router = APIRouter()

@router.post("/create-faiss-index", response_model=FaissIndexCreationResponse)
async def endpoint_create_faiss_index(
    background_tasks: BackgroundTasks,
    # 요청 본문을 Pydantic 모델로 받거나, Form 데이터로 받을 수 있습니다.
    # 여기서는 Form 데이터로 각 필드를 받도록 변경합니다.
    input_file: UploadFile = File(..., description="분석할 요구사항이 담긴 JSON 파일"),
    output_index_name_user: Optional[str] = Form(None, description="생성될 FAISS 인덱스 파일명 (확장자 제외, 예: my_index)"),
    output_metadata_name_user: Optional[str] = Form(None, description="생성될 메타데이터 파일명 (확장자 제외, 예: my_metadata)")
):
    
    if not input_file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="잘못된 파일 형식입니다. JSON 파일을 업로드해주세요.")

    # 입력 파일 저장
    input_file_path = os.path.join(OUTPUT_SRS_DIR, f"input_{input_file.filename}")
    try:
        with open(input_file_path, "wb") as buffer:
            buffer.write(await input_file.read())
        print(f"입력 파일 임시 저장: {input_file_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"입력 파일 저장 실패: {str(e)}")
    
    if not os.path.exists(input_file_path):
        raise HTTPException(
            status_code=404,
            detail=f"입력 JSON 파일 '{input_file_path}'을(를) 서버의 '{OUTPUT_SRS_DIR}' 경로에서 찾을 수 없습니다."
        )

    task_id = str(uuid.uuid4())
    base_name_for_output = os.path.splitext(input_file_path)[0]

    # 최종 출력 파일명 결정 (사용자 지정 없으면 기본값 사용)
    final_index_name = output_index_name_user if output_index_name_user else f"{base_name_for_output}_{task_id[:8]}"
    final_metadata_name = output_metadata_name_user if output_metadata_name_user else f"{base_name_for_output}_{task_id[:8]}"
    
    # 확장자 추가
    final_index_filename_with_ext = f"{final_index_name}.faiss"
    final_metadata_filename_with_ext = f"{final_metadata_name}.json"

    background_tasks.add_task(
        create_faiss_index_background_task,
        task_id,
        input_file_path, # 서버 내 파일명 전달
        final_index_filename_with_ext,
        final_metadata_filename_with_ext
    )
    
    # 응답에는 실제 저장될 예상 경로 제공
    expected_index_path = os.path.join(FAISS_INDEX_DIR, final_index_filename_with_ext)
    expected_metadata_path = os.path.join(METADATA_STORAGE_DIR, final_metadata_filename_with_ext)

    return FaissIndexCreationResponse(
        message="FAISS 인덱스 생성 작업이 백그라운드에서 시작되었습니다.",
        task_id=task_id,
        index_file_path=f"예상 경로: {expected_index_path}", # 실제 파일 생성은 백그라운드에서 이루어짐
        metadata_file_path=f"예상 경로: {expected_metadata_path}"
    )
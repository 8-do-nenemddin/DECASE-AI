# app/services/background_faiss_service.py
import os
from app.core.config import OUTPUT_SRS_DIR
from app.services.file_processing_service import prepare_data_for_faiss
from app.services.faiss_service import build_and_save_faiss_index

def create_faiss_index_background_task(
    task_id: str, # 로깅 및 상태 추적용
    input_json_file_path: str,
    output_index_name: str,
    output_metadata_name: str
):
    print(f"백그라운드 FAISS 인덱싱 시작 (Task ID: {task_id}) - 입력 파일: {input_json_file_path}")

    if not os.path.exists(input_json_file_path):
        print(f"[Task {task_id}] 오류: 입력 JSON 파일 '{input_json_file_path}'을 찾을 수 없습니다.")
        # TODO: 작업 실패 상태 기록 (DB, 로그 파일 등)
        return

    processed_data = prepare_data_for_faiss(input_json_file_path)
    if not processed_data:
        print(f"[Task {task_id}] 오류: 데이터 처리 중 문제 발생 또는 데이터 없음.")
        # TODO: 작업 실패 상태 기록
        return

    index_path, metadata_path = build_and_save_faiss_index(
        processed_data,
        output_index_name,
        output_metadata_name
    )

    if index_path and metadata_path:
        print(f"[Task {task_id}] FAISS 인덱싱 성공. 인덱스: {index_path}, 메타데이터: {metadata_path}")
        # TODO: 작업 성공 상태 기록
    else:
        print(f"[Task {task_id}] FAISS 인덱싱 실패.")
        # TODO: 작업 실패 상태 기록
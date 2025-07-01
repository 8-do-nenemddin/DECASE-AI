import json
import traceback
import httpx
import asyncio
from typing import List, Dict, Any

from pydantic import BaseModel
from google import genai

from app.core.config import GOOGLE_API_KEY
from app.agents.update.update_req_agent import analyze_requirement_changes
from app.services.job_services import update_job_status_in_db # job_services.py에 있다고 가정
from app.models.job import JobStatusEnum

# --- Pydantic 모델 정의 ---

class RequirementItem(BaseModel):
    reqIdCode: str
    type: str
    level1: str
    level2: str
    level3: str
    priority: str
    difficulty: str
    name: str
    description: str

class UpdateRequest(BaseModel):
    callback_url: str
    job_id: int  # job_id를 직접 받도록 추가
    member_id: int
    requirements: List[RequirementItem]
    project_id: int
    document_id: str


# --- 핵심 백그라운드 실행 함수 ---

async def process_update_background(
    request: UpdateRequest,
    file_content: bytes
):
    """
    백그라운드에서 요구사항 분석, DB 상태 업데이트, 콜백 전송까지 모두 처리합니다.
    """
    try:
        # 1. 데이터 준비
        # Pydantic 모델 리스트를 Gemini Agent가 사용할 딕셔너리 리스트로 변환
        existing_reqs_dict_list = [item.model_dump() for item in request.requirements]
        client = genai.Client(api_key=GOOGLE_API_KEY)
        file_content_str = file_content.decode('utf-8', errors='ignore')

        # 2. 요구사항 변경 분석 실행
        print(f"\n--- Job ID {request.job_id}: 요구사항 변경사항 분석 수행 ---")
        changes = await asyncio.to_thread(
            analyze_requirement_changes,
            client=client,
            existing_requirements=existing_reqs_dict_list,
            file_content_str=file_content_str
        )

        print(f"-> Job ID {request.job_id}: 변경사항 분석 완료.")

        # 3. DB 상태 'COMPLETED'로 업데이트
        await update_job_status_in_db(request.job_id, JobStatusEnum.COMPLETED)
        print(f"-> Job ID {request.job_id}: DB 상태를 COMPLETED로 업데이트했습니다.")

        # 4. 성공 콜백 전송
        if request.callback_url:
            print(f"\n--- Job ID {request.job_id}: 성공 콜백 전송 -> {request.callback_url} ---")
            async with httpx.AsyncClient() as http_client:
                success_data = {
                    "job_id": request.job_id,
                    "project_id": request.project_id,
                    "member_id": request.member_id,
                    "document_id": request.document_id,
                    "status": "COMPLETED",
                    "changes": changes,
                }
                response = await http_client.post(request.callback_url, json=success_data, timeout=60)
                print(f"-> Job ID {request.job_id}: 성공 콜백 응답 코드: {response.status_code}")
                response.raise_for_status()

    except Exception as e:
        # --- 전체 프로세스 중 어디서든 오류 발생 시 실행 ---
        error_traceback = traceback.format_exc()
        error_message = f"분석 작업 중 오류 발생 (Job ID: {request.job_id}):\n{str(e)}"
        print(f"\n❌ {error_message}\n{error_traceback}")

        # 5. DB 상태 'FAILED'로 업데이트
        # job_id가 있으므로 항상 DB 업데이트 시도
        await update_job_status_in_db(request.job_id, JobStatusEnum.FAILED)
        print(f"-> Job ID {request.job_id}: DB 상태를 FAILED로 업데이트했습니다.")

        # 6. 실패 콜백 전송
        if request.callback_url:
            print(f"\n--- Job ID {request.job_id}: 실패 콜백 전송 -> {request.callback_url} ---")
            async with httpx.AsyncClient() as http_client:
                failure_data = {
                    "job_id": request.job_id,
                    "project_id": request.project_id,
                    "member_id": request.member_id,
                    "document_id": request.document_id,
                    "status": "FAILED",
                    "error": str(e)
                }
                try:
                    response = await http_client.post(request.callback_url, json=failure_data, timeout=60)
                    print(f"-> Job ID {request.job_id}: 실패 콜백 응답 코드: {response.status_code}")
                except httpx.RequestError as req_err:
                    print(f"-> Job ID {request.job_id}: 실패 콜백 전송 자체를 실패했습니다: {req_err}")
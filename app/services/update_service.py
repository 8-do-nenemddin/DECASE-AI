
import traceback
import httpx
import asyncio
from typing import List

from pydantic import BaseModel
from google import genai

from app.core.config import GOOGLE_API_KEY
from app.agents.update.update_req_agent import analyze_requirement_changes
from app.services.job_services import update_job_status_in_db # job_services.py에 있다고 가정
from app.models.job import JobStatusEnum

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
    filename: str



async def process_update_background(
    request: UpdateRequest,
    file_content: bytes
):
    """
    백그라운드에서 요구사항 분석, DB 상태 업데이트, 콜백 전송까지 모두 처리합니다.
    """
    status = "COMPLETED"
    changes = None
    error_message = None
    
    try:
        # 데이터 준비
        existing_reqs_dict_list = [item.model_dump() for item in request.requirements]
        client = genai.Client(api_key=GOOGLE_API_KEY)
        file_content_str = file_content.decode('utf-8', errors='ignore')

        # 요구사항 변경 분석 실행
        print(f"\n--- Job ID {request.job_id}: 요구사항 변경사항 분석 수행 ---")
        changes = await asyncio.to_thread(
            analyze_requirement_changes,
            client=client,
            existing_requirements=existing_reqs_dict_list,
            file_content_str=file_content_str,
            filename=request.filename
        )

        print(f"-> Job ID {request.job_id}: 변경사항 분석 완료.")

    except Exception as e:
        # 분석 작업 중 오류 발생 시 실행
        error_traceback = traceback.format_exc()
        error_message = f"분석 작업 중 오류 발생 (Job ID: {request.job_id}):\n{str(e)}"
        print(f"\n❌ {error_message}\n{error_traceback}")
        status = "FAILED"

    finally:
        # DB 상태 업데이트 (성공/실패에 따라)
        if status == "COMPLETED":
            await update_job_status_in_db(request.job_id, JobStatusEnum.COMPLETED)
            print(f"-> Job ID {request.job_id}: DB 상태를 COMPLETED로 업데이트했습니다.")
        else:
            await update_job_status_in_db(request.job_id, JobStatusEnum.FAILED)
            print(f"-> Job ID {request.job_id}: DB 상태를 FAILED로 업데이트했습니다.")

        # 콜백 전송 
        if request.callback_url:
            print(f"\n--- Job ID {request.job_id}: 콜백 전송 -> {request.callback_url} ---")
            async with httpx.AsyncClient() as http_client:
                headers = {"Content-Type": "application/json"}
                callback_data = {
                        "projectId": request.project_id,
                        "jobId": request.job_id,
                        "memberId": request.member_id,
                        "documentId": request.document_id,
                        "status": status,
                        "changes": changes
                    }
                
                try:
                    print(f"-> Job ID {request.job_id}: 콜백 데이터 전송 중...")
                    print(f"-> Job ID {request.job_id}: 콜백 URL: {request.callback_url}")
                    print(f"-> Job ID {request.job_id}: 콜백 데이터: {callback_data}")
                    
                    response = await http_client.post(
                        request.callback_url, 
                        json=callback_data, 
                        headers=headers,
                        timeout=60
                    )
                    print(f"-> Job ID {request.job_id}: 콜백 응답 코드: {response.status_code}")
                    print(f"-> Job ID {request.job_id}: 콜백 응답 내용: {response.text}")
                    response.raise_for_status()
                except httpx.RequestError as req_err:
                    print(f"-> Job ID {request.job_id}: 콜백 전송을 실패했습니다: {req_err}")
                except Exception as callback_err:
                    print(f"-> Job ID {request.job_id}: 콜백 전송 중 오류 발생: {callback_err}")
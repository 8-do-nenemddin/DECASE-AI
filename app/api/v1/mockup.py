import asyncio
import os
import io
import zipfile
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.mockup_service import run_mockup_generation_pipeline
from urllib.parse import quote
import json
from typing import Dict, Any
import httpx
from fastapi import BackgroundTasks
from app.api.v3.srs_db import thread_pool

router = APIRouter()

mockup_job_store = {} # 목업 생성 작업 저장소

class RequirementItem(BaseModel):
    # 새로운 functional_requirements.json 형식에 맞는 필드들
    requirement_name: str
    type: str
    sources: List[Dict[str, Any]]
    description: str
    category_large: str
    category_medium: str
    category_small: str
    importance: str
    difficulty: str
    requirement_id: str

class MockupRequest(BaseModel):
    callback_url: str
    requirements: List[RequirementItem]
    output_folder_name: str = None
    project_id: int
    revision_count: int

@router.post("/generate-mockup")
async def generate_mockup_endpoint(
    request: MockupRequest,
    background_tasks: BackgroundTasks
):
    '''
    목업 생성 요청 api
    '''
    try:
        input_data = json.dumps([req.dict() for req in request.requirements], ensure_ascii=False, indent=2)
        project_id = request.project_id
        mockup_job_store[project_id] = {"status": "PROCESSING"}
        await asyncio.get_event_loop().run_in_executor(
            thread_pool, 
            send_callback, 
            input_data, 
            request, 
            project_id
            )
        return {"message": "목업 생성 및 콜백 요청이 시작되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"목업 생성 실패: {str(e)}")
    
def send_callback(input_data: str, request: MockupRequest, project_id: int):
    '''
    생성된 목업을 콜백 url로 전송
    '''
    zip_buffer = io.BytesIO()
    status = "SUCCESS"
    error_message = None
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            mockup_files = run_mockup_generation_pipeline(input_data, request.output_folder_name)
            for file_path, file_content in mockup_files:
                zip_file.writestr(file_path, file_content.encode('utf-8'))
        zip_buffer.seek(0)
        filename = f"mockup_{request.output_folder_name or 'result'}.zip"
    except Exception as e:
        status = "FAILED"
        error_message = str(e)
        print(f"[MOCKUP] 목업 생성 실패: {error_message}")
        zip_buffer = io.BytesIO()
        filename = f"mockup_{request.output_folder_name or 'result'}_failed.zip"
    
    encoded_filename = quote(filename.encode('utf-8'))
    print(f"[MOCKUP] 콜백 URL로 zip 파일 전송 시작: {request.callback_url}")

    with httpx.Client() as client:
        files = {
            "mockUpZip": (encoded_filename, zip_buffer.getvalue(), "application/zip"),
        }
        data = {
            "revisionCount": str(request.revision_count),
            "status": status,
        }
        if error_message:
            data["errorMessage"] = error_message
        params = {"projectId": request.project_id}
        try:
            response = client.post(request.callback_url, params=params, data=data, files=files, timeout=60)
            print(f"[MOCKUP] 콜백 요청 완료. 응답 코드: {response.status_code}")
            mockup_job_store[project_id]["status"] = status
        except Exception as e:
            print(f"[MOCKUP] 콜백 요청 실패: {e}")
            mockup_job_store[project_id]["status"] = "FAILED"
            pass

@router.get("/job/status")
async def get_mockup_job_status(
    project_id: int
    ):
    '''
    목업 생성 작업 상태 조회 api
    '''
    print(f"[DEBUG] get_mockup_job_status called with project_id={project_id}")
    job = mockup_job_store.get(project_id)
    if not job:
        return {"status": "NOT_FOUND"}
    return {"status": job["status"]}
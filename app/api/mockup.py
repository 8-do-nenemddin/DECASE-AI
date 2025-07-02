import asyncio
import io
import zipfile
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from app.models.job import JobNameEnum, JobStatusEnum, Job
from app.models.project import Project
from app.services.mockup_service import run_mockup_generation_pipeline
from urllib.parse import quote
import json
from typing import Dict, Any
import httpx
from fastapi import BackgroundTasks
from app.api.srs import thread_pool
from app.core.mysql_config import get_mysql_db
from app.services.job_services import create_job_in_db, update_job_status_in_db

router = APIRouter()

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
        
        async for db in get_mysql_db():
            project = await db.scalar(select(Project).where(Project.project_id == request.project_id))
            if not project:
                raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
            break
        
        new_job = await create_job_in_db(
            name=JobNameEnum.MOCKUP,
            project_id=request.project_id,
            member_id=None,
            revision_count=request.revision_count,
            status=JobStatusEnum.PROCESSING
        )
        job_id = new_job.job_id
        
        background_tasks.add_task(mockup_and_callback_with_status, input_data, request, job_id)

        return {
            "job_id": job_id, 
            "status": JobStatusEnum.PROCESSING.value, 
            "message": "목업 생성 및 콜백 요청이 시작되었습니다."
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"목업 생성 실패: {str(e)}")

def send_callback(input_data: str, request: MockupRequest, project_id: int, job_id: int):
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
        print(f"[MOCKUP] 목업 생성 실패: {str(e)}")
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
        except Exception as e:
            print(f"[MOCKUP] 콜백 요청 실패: {e}")
            status = "FAILED"
            error_message = str(e)
    return status

# BackgroundTasks에서 실행할 함수
async def mockup_and_callback_with_status(input_data: str, request: MockupRequest, project_id: int, job_id: int):
    loop = asyncio.get_event_loop()
    status = await loop.run_in_executor(
        thread_pool,
        send_callback,
        input_data,
        request,
        project_id,
        job_id
    )
    # 상태 업데이트
    await update_job_status_in_db(job_id, status)


@router.get("/job/status")
async def get_mockup_job_status(
    project_id: int
    ):
    '''
    목업 생성 작업 상태 조회 api
    '''
    async for db in get_mysql_db():
        job = await db.scalar(
            select(Job)
            .where(Job.project_id == project_id, Job.name == JobNameEnum.MOCKUP)
            .order_by(Job.start_time.desc())
        )
        if not job:
            return {"status": "NOT_FOUND"}
        return {"status": job.status, "job_id": job.job_id, "start_time": job.start_time, "end_time": job.end_time}
# app/api/v1/screen_spec_router.py
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import os

from app.services.screen_spec_service import generate_spec_and_flow_documents

router = APIRouter()

class SpecGenerationRequest(BaseModel):
    mockup_dir: str
    output_dir: str

@router.post("/specs/generate", status_code=202)
async def generate_specs_endpoint(
    request: SpecGenerationRequest,
    background_tasks: BackgroundTasks
):
    """
    지정된 목업 폴더의 파일들을 분석하여 화면 설계서 생성을 시작합니다.
    """
    # 입력받은 디렉토리 경로가 실제로 존재하는지 간단히 확인
    if not os.path.isdir(request.mockup_dir):
        raise HTTPException(status_code=404, detail=f"목업 디렉토리를 찾을 수 없습니다: {request.mockup_dir}")

    # 백그라운드에서 서비스 함수 실행
    background_tasks.add_task(
        generate_spec_and_flow_documents,
        request.mockup_dir,
        request.output_dir
    )

    return {"message": "화면 설계서 생성을 백그라운드에서 시작합니다."}
import os
import io
import zipfile
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.mockup_service import run_mockup_generation_pipeline
from urllib.parse import quote
from typing import Dict, Any
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

@router.post("/generate-mockup")
async def generate_mockup_endpoint(
    requirements: List[RequirementItem],
    output_folder_name: str = None,
):
    try:
        # 요구사항 데이터를 JSON 문자열로 변환 (UTF-8 인코딩 사용)
        import json
        input_data = json.dumps([req.dict() for req in requirements], ensure_ascii=False, indent=2)
        
        # 목업 생성 및 zip 파일 생성
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 목업 생성 파이프라인 실행 및 결과를 zip에 추가
            mockup_files = run_mockup_generation_pipeline(input_data, output_folder_name)
            for file_path, file_content in mockup_files:
                # 파일 내용을 UTF-8로 인코딩하여 zip에 추가
                zip_file.writestr(file_path, file_content.encode('utf-8'))
        
        zip_buffer.seek(0)
        
        # 파일명 생성 및 인코딩
        filename = f"mockup_{output_folder_name or 'result'}.zip"
        encoded_filename = quote(filename.encode('utf-8'))
        
        # StreamingResponse로 zip 파일 반환
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"목업 생성 실패: {str(e)}")
import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from sqlalchemy import select
from sqlalchemy.orm import relationship

from app.api.srs import update_job_status_in_db
from app.core.config import OUTPUT_ASIS_DIR

from app.models.job import Job, JobNameEnum, JobStatusEnum
from app.models.member import Member
from app.models.project import Project
from app.services.asis_services import asis_pipeline
from app.core.mysql_config import get_mysql_db

router = APIRouter()


# --- 백그라운드 작업 처리 ---
async def process_as_is_background(pdf_content: bytes, job_id: int, project_id: int, member_id: int, callback_url: str):
    """백그라운드에서 As-Is 분석 파이프라인을 처리하고 콜백으로 결과를 전송합니다."""
    try:
        # 임시 파일 저장 경로 생성
        upload_dir = Path(OUTPUT_ASIS_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ASIS_REPORT_{project_id}_{timestamp}.pdf"
        output_pdf_path = upload_dir / filename

        # 2. 분석 함수를 호출하여 파일 저장 및 바이트 반환을 동시에 수행
        print(f"Job[{job_id}]: 백그라운드 분석/저장 시작...")
        result_pdf_bytes = await asyncio.to_thread(
            asis_pipeline,
            pdf_content,
            output_pdf_path  # 생성한 파일 경로 전달
        )

        # 분석 파이프라인 실패 시 처리
        if result_pdf_bytes is None:
            print(f"Job[{job_id}]: asis_pipeline에서 PDF를 생성하지 못했습니다.")
            await update_job_status_in_db(job_id, JobStatusEnum.FAILED, "As-Is 분석 보고서 생성에 실패했습니다.")
            return

        # 3. 콜백 전송
        encoded_filename = quote(filename.encode('utf-8'))
        print(f"Job[{job_id}]: 콜백 URL로 PDF 파일 전송 시작: {callback_url}")

        async with httpx.AsyncClient() as client:
            files = {
                "file": (encoded_filename, result_pdf_bytes, "application/pdf"),
            }
            data = {
                "project_id": str(project_id),
                "member_id": str(member_id),
                "filename": filename,
                "status": "COMPLETED",
            }

            try:
                response = await client.post(callback_url, data=data, files=files, timeout=60)
                print(f"Job[{job_id}]: 콜백 요청 완료. 응답 코드: {response.status_code}")
                # 4. Job 완료 상태 업데이트
                await update_job_status_in_db(job_id, JobStatusEnum.COMPLETED, "As-Is 분석 및 콜백 전송이 완료되었습니다.")
            except httpx.RequestError as e:
                print(f"Job[{job_id}]: 콜백 요청 실패: {e}")
                await update_job_status_in_db(job_id, JobStatusEnum.FAILED, f"콜백 전송 실패: {e}")

    except Exception as e:
        print(f"Job[{job_id}]: 처리 중 오류 발생 - {e}")
        await update_job_status_in_db(job_id, JobStatusEnum.FAILED, f"As-Is 분석 실패: {e}")


@router.post("/as-is/start")
async def start_as_is_analysis(
        file: UploadFile = File(..., description="분석할 RFP PDF 파일"),
        project_id: int = Form(..., description="프로젝트 ID"),
        member_id: int = Form(..., description="멤버 ID"),
        callback_url: str = Form(..., description="결과를 전송할 콜백 URL"),
):
    """As-Is 분석 작업을 시작하고 Job ID를 반환합니다."""
    # ... (이전과 동일)
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    job_id = None

    try:
        pdf_content = await file.read()

        # DB에 Job 생성
        async for db in get_mysql_db():
            project = await db.scalar(select(Project).where(Project.project_id == project_id))
            member = await db.scalar(select(Member).where(Member.member_id == member_id))
            if not project or not member:
                raise HTTPException(status_code=404, detail="프로젝트 또는 멤버를 찾을 수 없습니다.")

            new_job = Job(
                name=JobNameEnum.ASIS,
                project_id=project_id,
                member_id=member_id,
                revision_count=0,
                start_time=datetime.now(),
                end_time=None,
                status=JobStatusEnum.PROCESSING
            )
            db.add(new_job)
            await db.commit()
            await db.refresh(new_job)
            job_id = new_job.job_id
            break

        asyncio.create_task(process_as_is_background(pdf_content, job_id, project_id, member_id, callback_url))
        
        return {
            "job_id": job_id,
            "status": "PROCESSING",
            "message": "As-Is 분석 작업이 시작되었습니다. Job ID로 상태를 확인하세요."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"작업 시작에 실패했습니다: {str(e)}")

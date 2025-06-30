import json
import os
import asyncio
import httpx

from datetime import datetime
from pathlib import Path
from google import genai
from urllib.parse import quote
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatusEnum, JobNameEnum
from app.core.mysql_config import get_mysql_db
from app.schemas.requirement import SrsRequirementData
from app.models import Document, Member, Project
from app.services.requirement_service import RequirementService
from app.core.config import OUTPUT_SRS_DIR
from app.agents.srs.req_extract_agent import extract_requirements
from app.agents.srs.req_refine_agent import refine_requirements
from app.core.config import GOOGLE_API_KEY
from fastapi import APIRouter, HTTPException, UploadFile, File, Form


async def process_srs_background(pdf_content: bytes, job_id: str, original_filename: str, project_id: int, member_id: int, document_id: str, callback_url: str):
    """요구사항 분석 처리"""
    try:
        print(f"\n=== 백그라운드 작업 시작 (Job ID: {job_id}) ===")
        print("\n--- 에이전트 1 & 2: 요구사항 식별, 명명, 분류, 상세설명 작업 중 ---")
        
        final_json_output = await asyncio.to_thread(
            srs_pipeline,
            pdf_content_bytes=pdf_content,
            output_path=os.path.join(OUTPUT_SRS_DIR, f"{job_id}_{original_filename}_requirements.json"),
        )
        
        print("\n=== 요구사항 명세서(SRS) 생성 완료 ===")
        # json 파일 파싱
        requirements_list = json.loads(final_json_output.decode('utf-8') if isinstance(final_json_output, bytes) else final_json_output)

        # 요구사항 명세서(SRS) 생성 완료 후 콜백 전송
        async with httpx.AsyncClient() as client:
            data = {
                "project_id": project_id,
                "member_id": member_id,
                "document_id": document_id,
                "status": "COMPLETED",
                "srs": requirements_list
            }

            try:
                response = await client.post(callback_url, json=data, timeout=60)
                print(f"Job[{job_id}]: 콜백 요청 완료. 응답 코드: {response.status_code}")
                if response.status_code != 200:
                    raise Exception(f"콜백 요청 실패: 응답 코드 {response.status_code}, 응답 내용: {response.text}")
                # 4. Job 완료 상태 업데이트
                await update_job_status_in_db(job_id, JobStatusEnum.COMPLETED, "요구사항 명세서(SRS) 생성 및 콜백 전송이 완료되었습니다.")
            except httpx.RequestError as e:
                print(f"Job[{job_id}]: 콜백 요청 실패: {e}")
                await update_job_status_in_db(job_id, JobStatusEnum.FAILED, f"콜백 전송 실패: {e}")
            except Exception as e:
                print(f"Job[{job_id}]: 콜백 요청 실패: {e}")
                await update_job_status_in_db(job_id, JobStatusEnum.FAILED, f"콜백 전송 실패: {e}")
     
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_message = f"요구사항 처리 중 오류 발생:\n{str(e)}\n\n상세 에러:\n{error_traceback}"
        print(error_message)
        await update_job_status_in_db(job_id, JobStatusEnum.FAILED, error_message)


async def update_job_status_in_db(job_id: int, status: JobStatusEnum, message: str = None):
    """Job 상태 업데이트"""
    async for db in get_mysql_db():
        job = await db.scalar(select(Job).where(Job.job_id == job_id))
        if job:
            job.status = status
            if status in [JobStatusEnum.COMPLETED, JobStatusEnum.FAILED]:
                job.end_time = datetime.now()
            await db.commit()
            await db.refresh(job)
        break

def srs_pipeline(pdf_content_bytes: bytes, output_path: Path) -> bytes:
    """
    PDF를 분석하여, 요구사항을 추출하고, 최종 요구사항 목록을 'output_path'에 파일로 저장합니다.
    """
    client = genai.Client(api_key=GOOGLE_API_KEY)
    
    # --- ▼▼▼ 수정된 부분 1: 변수 초기화 ▼▼▼ ---
    final_requirements = None  # try 블록 실패에 대비해 None으로 초기화

    try:
        extracted_requirements = extract_requirements(client, pdf_content_bytes)
        final_requirements = refine_requirements(client, extracted_requirements, chunk_size=30)
        
        # --- ▼▼▼ 수정된 부분 2: 성공 로직을 try 블록 안으로 이동 ▼▼▼ ---
        if final_requirements:
            final_json_output = json.dumps(final_requirements, indent=2, ensure_ascii=False)
            
            # 파일로 저장
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_json_output)
            
            print("\n🚀 파이프라인 실행 완료! 최종 요구사항 목록을 확인하세요."
                  f" 파일 경로: {output_path}")
            
            return final_json_output.encode('utf-8')
        else:
            print("⚠️ 파이프라인은 성공했으나, 분석된 최종 요구사항이 없습니다.")
            return b''
        
    except Exception as e:
        print(f"\n❌ 파이프라인 실행 중 오류 발생: {e}")
        raise e
    
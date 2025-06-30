import asyncio
import httpx

from pathlib import Path
from google import genai
from datetime import datetime
from urllib.parse import quote

from app.models.job import JobStatusEnum
from app.api.srs import update_job_status_in_db
from app.core.config import OUTPUT_ASIS_DIR
from app.agents.asis.asis_extract_agent import extract_as_is_facts
from app.agents.asis.report_generate_agent import generate_as_is_report
from app.services.file_processing_service import save_report
from app.core.config import GOOGLE_API_KEY

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


def asis_pipeline(pdf_content_bytes: bytes, output_pdf_path: Path) -> bytes | None:
    """
    PDF를 분석하여, 결과를 'output_pdf_path'에 파일로 저장하고,
    동시에 해당 파일의 내용을 바이트(bytes) 객체로 반환합니다.
    오류 발생 시 None을 반환합니다.
    """
    client = genai.Client(api_key=GOOGLE_API_KEY)

    try:
        facts_result = extract_as_is_facts(client, pdf_content_bytes)
        # facts_result가 비어있는 경우(추출 실패) 파이프라인 중단
        if not facts_result:
            print("\n❌ As-Is 기술 사실 데이터 추출에 실패하여 파이프라인을 중단합니다.")
            return None
            
        report_result = generate_as_is_report(client, facts_result)
        save_report(report_result, output_pdf_path)

        print("\n🚀 파이프라인 실행 완료! 최종 보고서를 확인하세요.")
        # 저장된 파일의 내용을 읽어 바이트로 반환
        return output_pdf_path.read_bytes()

    except Exception as e:
        print(f"\n❌ 파이프라인 실행 중 오류 발생: {e}")
    
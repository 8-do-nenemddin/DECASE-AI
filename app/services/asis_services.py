from pathlib import Path
from google import genai

from app.agents.asis.asis_extract_agent import extract_as_is_facts
from app.agents.asis.report_generate_agent import generate_as_is_report
from app.services.file_processing_service import save_report_to_file

from app.core.config import GOOGLE_API_KEY

def asis_pipeline(pdf_content_bytes: bytes, output_pdf_path: Path) -> bytes:
    """
    PDF를 분석하여, 결과를 'output_pdf_path'에 파일로 저장하고,
    동시에 해당 파일의 내용을 바이트(bytes) 객체로 반환합니다.
    """
    client = genai.Client(api_key=GOOGLE_API_KEY)

    try:
        facts_result = extract_as_is_facts(client, pdf_content_bytes)
        report_result = generate_as_is_report(client, facts_result)
        save_report_to_file(report_result, output_pdf_path)
        print("\n🚀 파이프라인 실행 완료! 최종 보고서를 확인하세요.")
        
    except Exception as e:
        print(f"\n❌ 파이프라인 실행 중 오류 발생: {e}")
    
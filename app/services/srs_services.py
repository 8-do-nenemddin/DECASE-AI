import json

from pathlib import Path
from google import genai

from app.agents.srs.req_extract_agent import extract_requirements
from app.agents.srs.req_refine_agent import refine_requirements

from app.core.config import GOOGLE_API_KEY

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
    
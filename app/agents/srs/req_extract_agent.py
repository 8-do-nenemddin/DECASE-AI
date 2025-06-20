import json
from google import genai
from google.genai import types

from typing import Any, Dict, List

from app.core.config import GEMINI_MODEL

def extract_requirements(client:genai.Client, uploaded_file: Any) -> List[Dict[str, Any]]:
    """
    [1단계] PDF에서 최소 단위 요구사항을 식별, 분해, 통합하고 기본 분류하며 상세 설명을 생성합니다.
    """
    print("\n🚀 1단계: 요구사항 식별, 분해 및 상세 설명 생성을 시작합니다...")
    
    prompt = """
    당신은 RFP 문서를 분석하여, 개발 가능한 **최소 단위의 독립 태스크**로 요구사항을 정의하는 뛰어난 시스템 분석가입니다.
    첨부된 PDF 문서를 종합적으로 분석하여, 아래 [규칙]에 따라 요구사항 목록을 JSON 배열 형식으로 생성하십시오.

    [규칙]
    1.  **최소 단위 분해**:
        - 기능이나 행위가 나열된 경우('A, B, C 기능', '관리 및 등록') 반드시 개별 기능/행위 단위로 분리하여 독립적인 요구사항 항목을 생성해야 합니다.
        - 복합적인 문장은 반드시 단일 개발 태스크가 가능한 수준까지 해체하십시오.

    2.  **의미 기반 통합**:
        - 문서 여러 곳에 흩어져 있더라도, **의미와 개발 범위가 완전히 동일한** 최소 단위 요구사항은 단일 항목으로 통합하십시오.
        - 통합된 경우, `sources` 배열에 모든 출처(페이지, 원문)를 기록해야 합니다.

    3.  **필수 출력 필드**:
        - `requirement_name`: 분해된 최소 단위 요구사항의 명칭 (예: "사용자 비밀번호 찾기 기능")
        - `type`: '기능' 또는 '비기능' 중 하나로 분류
        - `sources`: 출처 목록 배열. `[{ "source_page": <페이지 번호>, "original_text": "<원문 내용>" }]` 형식.
        - `description`: 요구사항에 대한 상세 설명. 요구사항의 목적과 범위를 2문장 내로 명확히 기술
        - `target_page`: 이 요구사항이 주로 사용되거나 구현될 시스템 내의 특정 화면 단위 명칭 (예: "관리자 대시보드", "사용자 정보 조회 화면")

    4.  **출력 형식**: JSON 배열 객체로, 각 요구사항은 위 필드를 모두 포함해야 합니다.
    
    이제 분석을 시작하여, 다른 부가적인 설명 없이 최종 JSON 배열 객체만 반환하십시오.
    """
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Part.from_bytes(
                data=uploaded_file,
                mime_type='application/pdf',
            ), 
            prompt],
            config={
                "response_mime_type": "application/json",
                "temperature": 0.0,
            }
        )
        extracted_requirements = json.loads(response.text)
        print("🚀 분석 완료! 요구사항 목록을 성공적으로 생성했습니다.")
        return extracted_requirements
    except Exception as e:
        print(f"❌ 분석 중 오류 발생: {e}")
        raise ValueError("요구사항 추출에 실패했습니다. PDF 파일이 올바른지 확인하십시오.")
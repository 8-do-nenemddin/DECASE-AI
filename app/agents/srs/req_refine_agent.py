import json

from google import genai
from google.genai import types

from typing import Any, Dict, List, Literal
from pydantic import BaseModel
import concurrent.futures
from app.services.file_processing_service import create_chunks

from app.core.config import GEMINI_MODEL

class RequirementClassification(BaseModel):
    """
    LLM이 반환할 JSON 객체의 구조를 정의하는 Pydantic 모델
    """
    category_large: str
    category_medium: str
    category_small: str
    importance: Literal['상', '중', '하']
    difficulty: Literal['상', '중', '하']
    requirement_id_prefix: str

def refine_requirements(client: genai.Client, extracted_requirements: List[Dict[str, Any]], chunk_size: int = 30) -> List[Dict[str, Any]]:
    """
    [2단계] 각 요구사항에 대해 상세 분류, 중요도, 난이도를 '통합된 하나의 API 호출'로 부여하고 요구사항 ID를 생성합니다.
    """
    print("\n🚀 2단계: 상세 속성 분류 및 요구사항 ID 생성을 시작합니다...")

    def create_classification_prompt(req):
        return f"""
        당신은 시스템 분석 전문가입니다. 주어진 요구사항 정보를 종합적으로 분석하여, 아래 항목들을 모두 포함하는 단일 JSON 객체를 생성하십시오.

        [분석할 요구사항 정보]
        - 요구사항 명: {req.get('requirement_name')}
        - 상세 설명: {req.get('description')}

        [생성할 JSON 필드]
        1.  "category_large": 가장 큰 서비스 범주 (예: "고객 관계 관리").
        2.  "category_medium": 대분류 하위의 기능 영역 (예: "사용자 관리").
        3.  "category_small": 중분류 하위의 최소 기능 단위. (중분류로 충분하면 '해당 없음'으로 지정)
        4.  "importance": [중요도 기준]에 따라 '상', '중', '하' 중 하나로 평가하십시오.
            - 상: 누락 시 시스템 핵심 가치 손상 또는 치명적 리스크 발생. 또는 시스템의 메인 기능으로, 반드시 구현해야 함.
            - 중: 누락 시 업무 효율 저하 또는 고객 불만 증가. 또는, 시스템의 주요 기능이나 서비스로, 구현이 권장됨.
            - 하: 편의성 개선 항목, 없어도 핵심 운영에 영향 적음.
        5.  "difficulty": [난이도 기준]에 따라 '상', '중', '하' 중 하나로 평가하십시오.
            - 상: 핵심 아키텍처 변경, 검증되지 않은 신기술 도입 등 리스크가 매우 큼.
            - 중: 익숙한 기술 기반이나 새로운 기능 개발 등 일부 도전 과제 존재.
            - 하: 단순 수정, 기존 컴포넌트 재활용 등 구현 경로가 명확함.
        6.  "requirement_id_prefix": "category_large"와 "category_medium"을 기반으로 3글자 영문 약어를 조합하여 요구사항 ID 접두사를 생성하십시오. 이때, 약어는 다음 규칙을 따르십시오:
            - **일관성**: 동일한 대분류/중분류가 반복될 경우 항상 동일한 약어를 사용하십시오.
            - **조합**: 대분류 약어와 중분류 약어를 하이픈으로 연결하여 "XYZ-ABC" 형태의 접두사를 만드십시오. (예: "CRM-USR", "LMS-EDU", "FIN-ACC")
            - **예시 약어**:
                - 고객 관계 관리 (Customer Relationship Management) -> CRM
                - 학습 관리 시스템 (Learning Management System) -> LMS
                - 재무 관리 (Financial Management) -> FNM
                - 사용자 관리 (User Management) -> USR
                - 교육 과정 (Education Course) -> EDU
                - 계좌 관리 (Account Management) -> ACC
                - 보고서 (Report) -> RPT
                - 시스템 관리 (System Administration) -> SYS
                - 콘텐츠 관리 (Content Management) -> CON
                - 서비스 (Service) -> SVC

        이제 분석을 시작하여, 다른 설명 없이 최종 JSON 객체만 반환하십시오.
        """
        
    intermediate_results = []
    failed_items = []
    chunks = create_chunks(extracted_requirements, chunk_size)
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks):
        print(f"  - 2단계 청크 {i+1}/{total_chunks} 처리 중 ({len(chunk)}개 항목)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            prompts = [create_classification_prompt(req) for req in chunk]
            future_to_req = {
                executor.submit(
                    client.models.generate_content,
                    model=GEMINI_MODEL,
                    contents=[prompt],
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": RequirementClassification,
                    }
                ): req for req, prompt in zip(chunk, prompts)
            }

            for future in concurrent.futures.as_completed(future_to_req):
                original_req = future_to_req[future]
                try:
                    response = future.result()
                    
                    # SDK가 자동으로 JSON을 파싱하고 Pydantic 모델로 검증/변환해 줌
                    classification_data: RequirementClassification = response.parsed

                    # .model_dump()를 사용하여 Pydantic 객체를 딕셔너리로 변환
                    new_result = original_req | classification_data.model_dump()
                    
                    intermediate_results.append(new_result)
                    print(f"  - 분류 완료: {new_result.get('requirement_name')}")

                except Exception as e:
                    print(f"  - ⚠️ 처리 실패: {original_req.get('requirement_name')}, 오류: {e}")
                    failed_items.append({"failed_requirement": original_req, "error_message": str(e)})

    # --- 최종 ID 부여 로직 (기존과 동일) ---
    print(f"✅ 완료: {len(intermediate_results)}개 요구사항 분류 및 접두사 생성 완료. 이제 최종 ID를 부여합니다.")
    
    final_results_with_ids = []
    id_counters = {}
    
    intermediate_results.sort(key=lambda x: x.get('requirement_id_prefix', ''))

    for req in intermediate_results:
        prefix = req.get('requirement_id_prefix')
        id_counters[prefix] = id_counters.get(prefix, 0) + 1
        req['requirement_id'] = f"{prefix}-{id_counters[prefix]:04d}"
        final_results_with_ids.append(req)

    print(f"✅ 2단계 최종 완료: {len(final_results_with_ids)}개 요구사항 상세 속성 분류 및 고유 ID 생성 완료.")
    return final_results_with_ids
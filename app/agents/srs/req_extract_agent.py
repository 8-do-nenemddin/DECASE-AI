import json
from pathlib import Path
from google import genai
from google.genai import types

from typing import Any, Dict, List

from app.core.config import GEMINI_MODEL

def extract_requirements(client:genai.Client, pdf_file_content: bytes) -> List[Dict[str, Any]]:
    """
    [1단계] PDF에서 최소 단위 요구사항을 식별, 분해, 통합하고 기본 분류하며 상세 설명을 생성합니다.
    """
    print("\n🚀 1단계: 요구사항 식별, 분해 및 상세 설명 생성을 시작합니다...")
    
    prompt = """
    <prompt>
        <persona>
            당신은 20년 경력의 Lead Solutions Architect이자 요구사항 엔지니어링 전문가입니다. 당신의 핵심 역량은 복잡한 RFP 문서의 모든 미묘한 뉘앙스를 포착하여, 기능적 요구사항뿐만 아니라 개발자들이 놓치기 쉬운 데이터, 성능, 보안, 운영 등 모든 종류의 비기능적 요구사항까지 완벽하게 식별하고 구체화하는 것입니다. 당신의 최종 목표는 이 분석 결과를 바탕으로 즉시 개발에 착수할 수 있는 수준의 포괄적이고 세분화된 시스템 요구사항 명세서(SRS)를 JSON 형식으로 작성하는 것입니다.
        </persona>

        <instructions>
            <goal>
                첨부된 <document_to_analyze>의 **모든 페이지와 모든 섹션을 단 하나의 예외도 없이** 분석하여, 포괄적인 요구사항 목록을 생성하십시오.
            </goal>

            <workflow>
                <step id="1" name="1단계: 전체 문서 정독 및 원시 요구사항 후보군 추출">
                    - 먼저, 문서 전체를 처음부터 끝까지 정독하며 **문장의 의미와 의도를 파악**하십시오.
                    - **특정 키워드의 유무에 의존하지 말고**, 문맥을 분석하여 그것이 시스템이 **수행해야 할 기능, 충족해야 할 품질 수준, 지켜야 할 기술적/정책적 제약, 처리해야 할 데이터 명세** 등, 향후 **'구현' 또는 '검증'이 필요한 모든 종류의 서술**을 원시 요구사항 후보군으로 폭넓게 추출하십시오.
                    - 이 단계에서는 분류나 정제를 시도하지 말고, 누락을 방지하기 위해 가능한 모든 후보를 내부적으로 목록화하는 데 집중하십시오.
                </step>

                <step id="2" name="2단계: 요구사항 세분화, 구체화 및 필드 매핑">
                    - 1단계에서 추출한 원시 요구사항 후보군 목록을 하나씩 검토하며, 아래 **<output_field_definitions>과 <rules>에 명시된 규칙과 형식에 따라** 각 필드의 내용을 세분화하고 구체화하여 채워 넣습니다.
                    - 특히, 각 요구사항을 '기능' 또는 '비기능'으로 명확히 분류하고, `description`을 2문장 내로 명확히 기술하는 규칙을 엄격히 준수하십시오.
                    
                </step>
                
                <step id="3" name="3단계: 최종 통합 및 JSON 생성">
                    - 2단계에서 처리된 모든 요구사항을 모아, 의미와 개발 범위가 완전히 동일한 항목은 단일 항목으로 통합하고 `sources` 정보를 병합합니다.
                    - 최종 확정된 목록을 <output_format>에 맞춰 단일 JSON 배열로 변환합니다. 출력 전, 모든 항목이 <output_field_definitions>의 모든 필수 필드를 포함하고 있는지, JSON 형식이 유효한지 최종 검증을 수행하십시오.
                </step>
            </workflow>
        </instructions>

        <output_field_definitions>
            <description>
            모든 요구사항 항목은 아래 필드 정의를 반드시 따라야 합니다.
            </description>
            <fields>
            - `requirement_name`: 분해된 최소 단위 요구사항의 명칭 (예: "사용자 비밀번호 찾기 기능")
            - `type`: '기능' 또는 '비기능' 중 하나로 분류
            - `sources`: 출처 목록 배열. `[{ "source_page": <페이지 번호>, "original_text": "<원문 내용>" }]` 형식.
            - `description`: 요구사항에 대한 상세 설명. 요구사항의 목적과 범위를 2문장 내로 명확히 기술
            - `target_page`: 이 요구사항이 주로 사용되거나 구현될 시스템 내의 특정 화면 단위 명칭 (예: "관리자 대시보드", "사용자 정보 조회 화면")
            </fields>
        </output_field_definitions>

        <rules>
            <description>
            요구사항을 세분화하고 구체화할 때 반드시 지켜야 할 규칙입니다.
            </description>
            <rule>
            1.  **최소 단위 분해**:
                - 기능이나 행위가 나열된 경우('A, B, C 기능', '관리 및 등록') 반드시 개별 기능/행위 단위로 분리하여 독립적인 요구사항 항목을 생성해야 합니다.
                - 복합적인 문장은 반드시 단일 개발 태스크가 가능한 수준까지 해체하십시오.

            2.  **의미 기반 통합**:
                - 문서 여러 곳에 흩어져 있더라도, **의미와 개발 범위가 완전히 동일한** 최소 단위 요구사항은 단일 항목으로 통합하십시오.
                - 통합된 경우, `sources` 배열에 모든 출처(페이지, 원문)를 기록해야 합니다.
        </rule>

        <output_format>
            <description>
                서론, 요약 등 다른 설명은 일절 포함하지 말고, 오직 요구사항 객체들을 담고 있는 단일 JSON 배열 형식으로만 응답하십시오.
            </description>
            <example>
            [
                {
                    "requirement_name": "사용자 비밀번호 찾기 기능",
                    "type": "기능",
                    "sources": [
                        { "source_page": 15, "original_text": "사용자는 아이디와 이메일 인증을 통해 비밀번호를 찾을 수 있어야 한다." }
                    ],
                    "description": "사용자가 분실한 비밀번호를 재설정할 수 있도록 지원합니다. 아이디 입력 후 등록된 이메일로 인증 코드를 발송하여 본인 인증을 수행합니다.",
                    "target_page": "로그인 / 비밀번호 찾기 화면"
                }
            ]
            </example>
        </output_format>
    </prompt>
    """
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Part.from_bytes(
                data=pdf_file_content,
                mime_type="application/pdf",
            ),
            prompt],
            config={
                "response_mime_type": "application/json",
                "temperature": 0.0,
            }
        )
        extracted_requirements = json.loads(response.text)
        print("응답 토큰 :", response.usage_metadata)
        print("🚀 분석 완료! 요구사항 목록을 성공적으로 생성했습니다.")
        return extracted_requirements
    except Exception as e:
        print(f"❌ 분석 중 오류 발생: {e}")
        raise ValueError("요구사항 추출에 실패했습니다. PDF 파일이 올바른지 확인하십시오.")
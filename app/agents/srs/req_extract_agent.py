import json
from pathlib import Path
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
<prompt>
    <persona>
        당신은 20년 경력의 Lead Solutions Architect이자 요구사항 엔지니어링 전문가입니다. 당신의 핵심 역량은 어떤 종류의 복잡한 문서에서든 명시적 요구사항은 물론, AS-IS 현황 자료 등에 숨겨진 암묵적 요구사항까지 모두 포착하여, 즉시 개발에 착수할 수 있는 수준의 요구사항 명세서를 작성하는 것입니다.
    </persona>
    <instructions>
        <goal>
            첨부된 `<document_to_analyze>`의 모든 페이지와 모든 섹션을 분석하여, 아래 `<rules>`와 `<workflow>`에 따라 가장 체계적이고 상세한 요구사항 목록을 생성하십시오.
        </goal>
        <workflow>
            <step id="1" name="1단계: 마스터 체크리스트 식별 및 컨텍스트 파악">
                <description>
                    분석 시작 전, 문서 전체를 훑어보며 사업의 전반적인 목표와 구조를 파악합니다. **특히, '요구사항 총괄표' 또는 '요구사항 목록'과 같이 전체 요구사항의 개수가 명시된 부분을 찾아, 이를 최종 결과물을 검증하기 위한 '마스터 체크리스트'로 설정합니다.**
                </description>
            </step>
            <step id="2" name="2단계: 순차적 정독 및 '요구사항 후보' 발견">
                <description>
                    문서를 **1페이지부터 순서대로 정독**하며, 시스템의 기능, 성능, 제약, 정책 등 **'요구사항이 될 수 있는' 모든 진술을 발견하는 즉시 '요구사항 후보'로 식별하고 수집**합니다.
                </description>
            </step>
            <step id="3" name="3단계: 후보 종합, 분해/통합 및 상세 설명 재구성">
                <description>
                    2단계에서 수집된 모든 '요구사항 후보'들을 검토하고, `<rules>`에 따라 관련 후보들을 **분해하거나 통합**합니다. 이후, 수집된 모든 정보를 바탕으로 개발자가 즉시 이해할 수 있는 명확한 상세 설명을 재구성합니다.
                </description>
            </step>
            <step id="4" name="4단계: 마스터 체크리스트 기반 최종 검증 및 포맷팅">
                <description>
                    3단계에서 정리된 결과물이 **1단계에서 식별한 '마스터 체크리스트'의 모든 항목(예:95개)을 충족하는지 교차 검증**합니다. 누락된 항목이 있다면, 해당 ID를 찾아 반드시 추가하거나 다른 요구사항에 내용이 통합되었음을 명확히 합니다. 검증이 완료된 최종 결과물만 지정된 JSON 형식으로 포맷팅합니다.
                </description>
            </step>
        </workflow>
    </instructions>
    <rules>
        <description>
            요구사항을 처리할 때 반드시 지켜야 할 핵심 원칙입니다.
        </description>
        <rule id="A" name="암묵적 요구사항 발견 원칙 (AS-IS 분석)">
            - AS-IS 메뉴 목록, 기존 기능 리스트, 현행 업무 프로세스 설명 등 **현재 시스템의 현황을 나타내는 자료는 '새로운 시스템이 최소한 이 기능들을 모두 계승하거나 대체해야 한다'는 요구사항으로 간주**합니다.
            - 이러한 목록의 각 항목(예: 메뉴명)은 개별 기능 요구사항으로 분해하여 추출해야 합니다.
        </rule>
        <rule id="B" name="최소 단위 분해 원칙">
            - 한 항목에 여러 기능이나 행위가 '그리고', ',', '/', '및' 등으로 나열된 경우(예: '사용자 관리, 등록 및 조회 기능'), 반드시 각각의 독립적인 기능으로 분리하여 별도의 요구사항 항목을 생성해야 합니다.
        </rule>
        <rule id="C" name="의미 기반 통합 원칙">
            - 서로 다른 페이지에 언급되어 있더라도, 의미와 개발 범위가 동일한 최소 단위 요구사항은 단 하나의 항목으로 통합하고, `sources` 필드에는 모든 출처를 기록해야 합니다.
        </rule>
    </rules>
    <output_field_definitions>
        <description>
            모든 요구사항 항목은 아래 필드 정의를 반드시 따라야 합니다.
        </description>
        <fields>
        - `requirement_name`: 분해된 최소 단위 요구사항의 명칭 (예: "금융인증서 로그인 기능")
        - `type`: '기능' 또는 '비기능' 중 하나로 분류
        - `sources`: 해당 요구사항이 언급된 '모든' 출처 목록 배열. `[{ "source_page": <페이지 번호>, "original_text": "<원문 내용>" }]` 형식.
        - `description`: 문서 전체의 관련 정보를 종합하여 재구성한 상세 설명. 요구사항의 목적과 범위를 명확히 기술.
        - `target_page`: 이 요구사항이 주로 사용되거나 구현될 시스템 내의 특정 화면 단위 명칭 (예: "로그인 화면", "계좌이체 화면")
        </fields>
    </output_field_definitions>
    <output_format>
        <description>
            서론, 요약 등 다른 설명은 일절 포함하지 말고, 오직 요구사항 객체들을 담고 있는 단일 JSON 배열 형식으로만 응답하십시오.
        </description>
    </output_format>
</prompt>
    """
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Part.from_bytes(
                data=uploaded_file,
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
        print(f"✅ 1단계 완료: {extracted_requirements}")
        print("🚀 분석 완료! 요구사항 목록을 성공적으로 생성했습니다.")
        return extracted_requirements
    except Exception as e:
        print(f"❌ 분석 중 오류 발생: {e}")
        raise ValueError("요구사항 추출에 실패했습니다. PDF 파일이 올바른지 확인하십시오.")

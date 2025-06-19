import json
from google import genai

from typing import Any, Dict

from app.core.config import GEMINI_MODEL

def generate_as_is_report(client: genai.Client, as_is_facts: Dict[str, Any]) -> str:
    """
    [1단계-B] 추출된 기술 사실 데이터를 기반으로 개발자용 기술 분석 보고서를 Markdown으로 생성합니다.
    """
    print("🚀 As-Is 기술 현황 분석 보고서 생성을 시작합니다...")
    
    facts_str = json.dumps(as_is_facts, indent=2, ensure_ascii=False)

    prompt = f"""
    당신은 새로운 팀원이나 시스템 유지보수 담당자를 위해 기술 인수인계 문서를 작성하는 경험 많은 시니어 개발자(Tech Lead)입니다.
    주어진 [As-Is 시스템 분석 데이터]를 바탕으로, 개발자가 시스템의 구조와 현황을 명확하고 빠르게 파악할 수 있는 실용적인 '기술 현황 분석 보고서'를 Markdown 형식으로 작성하십시오.
    추가적인 응답 없이 다음 형식만을 출력하십시오.
    
    [As-Is 시스템 분석 데이터]
    ```json
    {facts_str}
    ```

    [보고서 작성 가이드라인]
    1.  **제목**: `# As-Is 기술 현황 분석 보고서` 로 시작하십시오.
    2.  **목차 준수**: 아래 4개의 목차를 반드시 사용하고, 각 목차 아래에 관련 데이터를 상세하게 서술하십시오.
        - `## 1. 시스템 개요`
        - `## 2. 주요 기능 및 구현 현황`
        - `## 3. 비기능 현황 분석 (NFR)`
        - `## 4. 아키텍처 분석`
    3.  **개발자 관점 서술**: 데이터를 단순히 나열하지 말고, 개발자의 관점에서 기술적 의미를 해석하여 문장 형태로 풀어주십시오.
        - **(중요)** '주요 기능' 섹션에서는 비즈니스 설명보다 **기술적 구현 방식, 로직의 특징, 알려진 문제점**을 위주로 설명합니다.
        - **(중요)** '아키텍처' 섹션에서는 각 구성요소의 **정확한 버전, 설정, 그리고 이로 인한 잠재적 이슈(예: 'CentOS 6 사용으로 인한 보안 취약점 노출 가능성')**를 명시적으로 언급합니다.
    4.  **객관적이고 명료한 표현**: 명확하고 간결한 기술 용어를 사용하십시오. 불필요한 미사여구나 비즈니스 중심의 표현('고객 가치 증대', '혁신적인')은 지양하고, 기술적 사실과 잠재적 리스크를 객관적으로 전달하는 데 집중합니다.
    5.  **가독성**: 적절한 줄 바꿈, 글머리 기호(bullet points), 강조(bold) 등을 사용하여 복잡한 기술 내용을 쉽게 파악할 수 있도록 작성합니다.
    6.  **내용 추가 금지**: 제공된 [As-Is 시스템 분석 데이터]에 없는 내용은 절대 추측하여 추가하지 마십시오.

    이제, 위 가이드라인에 따라 최종 Markdown 보고서를 작성하십시오.
    """
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "temperature":0.1
            }               
        )
        report = response.text
        print("✅ As-Is 기술 현황 분석 보고서 생성 완료.")
        return report
    except Exception as e:
        print(f"🚨 보고서 생성 실패: {e}")
        return "## 보고서 생성 실패\n오류가 발생했습니다."
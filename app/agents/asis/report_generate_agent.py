import json
from google import genai
from typing import Any, Dict

from app.core.config import GEMINI_MODEL

def generate_as_is_report(client: genai.Client, as_is_facts: Dict[str, Any]) -> str:
    """
    [1단계-B] 추출된 기술 사실 데이터를 기반으로 개발자용 기술 분석 보고서를 'HTML'로 생성합니다.
    """
    print("🚀 As-Is 기술 현황 분석 HTML 보고서 생성을 시작합니다...")
    
    # 딕셔너리 데이터를 JSON 문자열로 변환하여 프롬프트에 삽입
    facts_str = json.dumps(as_is_facts, indent=2, ensure_ascii=False)

    # HTML 생성을 위한 프롬프트 (CSS 스타일링 지침 포함)
    prompt = f"""
    당신은 새로운 팀원이나 시스템 유지보수 담당자를 위해 기술 인수인계 문서를 작성하는 경험 많은 시니어 개발자(Tech Lead)입니다.
    주어진 [As-Is 시스템 분석 데이터]를 바탕으로, 개발자가 시스템의 구조와 현황을 명확하고 빠르게 파악할 수 있는 실용적인 '기술 현황 분석 보고서'를 **완벽한 단일 HTML 파일**로 작성하십시오.
    
    [As-Is 시스템 분석 데이터]
    ```json
    {facts_str}
    ```

    [HTML 보고서 작성 가이드라인]
    1.  **완전한 HTML 구조**: 반드시 `<!DOCTYPE html>` 로 시작하여 `</html>` 로 끝나는 완전한 HTML 문서여야 합니다.
    2.  **내장 CSS 스타일**: `<head>` 안에 `<style>` 태그를 사용하여 보고서를 보기 좋게 꾸며주십시오. 아래 CSS 가이드를 참고하되, 더 나은 디자인 제안이 있다면 자유롭게 개선하십시오.
        -   `font-family`: 'Pretendard', 'Noto Sans KR', sans-serif 와 같은 가독성 좋은 한글 폰트 사용
        -   `body`: 적절한 `max-width` 와 `margin` 으로 중앙 정렬된 레이아웃 구성
        -   `h1, h2, h3`: 제목에 맞는 폰트 크기, 색상, 여백 적용
        -   `section`: 각 목차 섹션을 구분하고, 보기 좋은 여백(padding)과 경계선(border) 추가
        -   `table`: 테이블에 `width: 100%`, `border-collapse`, 그리고 행(tr)과 셀(th, td)에 명확한 스타일 적용
        -   `code`: 코드나 기술 용어를 표시하기 위한 `<code>` 태그에 배경색과 폰트 스타일 적용
    3.  **시맨틱 HTML 태그 사용**: `header`, `main`, `section`, `h1`, `h2`, `ul`, `li`, `table`, `strong`, `code` 등 의미에 맞는 태그를 적극적으로 사용하십시오.
    4.  **목차 준수**: 아래 4개의 목차를 반드시 `<h2>` 태그로 사용하고, 각 목차 아래에 관련 데이터를 상세하게 서술하십시오.
        - `1. 시스템 개요 (System Overview)`
        - `2. 주요 기능 및 구현 현황 (Key Features & Implementation Status)`
        - `3. 비기능 현황 분석 (Non-functional Requirements Analysis)`
        - `4. 아키텍처 분석 (Architecture Analysis)`
    5.  **개발자 관점 서술**: 데이터를 단순히 나열하지 말고, 개발자의 관점에서 기술적 의미를 해석하여 문장 형태로 풀어주십시오. '아키텍처' 섹션에서는 각 구성요소의 **정확한 버전, 설정, 그리고 이로 인한 잠재적 이슈(예: 'CentOS 6 사용으로 인한 보안 취약점 노출 가능성')**를 명시적으로 언급합니다.
    6.  **내용 추가 금지**: 제공된 [As-Is 시스템 분석 데이터]에 없는 내용은 절대 추측하여 추가하지 마십시오.
    7.  **스타일은 a4**: HTML 문서의 스타일은 A4 용지 크기에 맞춰 인쇄할 때도 잘 보이도록 구성합니다. @page size: A4; margin: 0; 를 사용합니다.
    이제, 위 가이드라인에 따라 최종 HTML 문서를 작성하십시오. 추가적인 설명이나 Markdown 코드 블록 마커 없이, 순수한 HTML 코드만 반환해야 합니다.
    """
    try:
        # 모델에 텍스트(HTML 소스 코드) 생성을 요청
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "temperature": 0.1,
                "response_mime_type": "text/plain" 
            }               
        )
        report_html = response.text
        print("✅ As-Is 기술 현황 분석 HTML 보고서 생성 완료.")
        return report_html
    except Exception as e:
        print(f"🚨 HTML 보고서 생성 실패: {e}")
        # 오류 발생 시에도 유효한 HTML을 반환하여 렌더링 오류 방지
        return f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head><meta charset="UTF-8"><title>오류</title></head>
        <body><h1>보고서 생성 실패</h1><p>오류가 발생했습니다: {e}</p></body>
        </html>
        """

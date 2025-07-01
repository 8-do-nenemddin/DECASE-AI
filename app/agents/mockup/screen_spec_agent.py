# app/agents/mockup/screen_spec_agent.py
import json
import re
import asyncio
from typing import List, Dict, Any
from datetime import datetime

from google import genai

class ScreenSpecAgent:
    """
    주어진 데이터를 바탕으로 화면 설계 및 기능 흐름 분석을 수행하는 핵심 에이전트.
    파일 I/O나 외부 통신 없이 오직 분석 로직에만 집중합니다.
    """
    def __init__(self, google_api_key: str):
        # API 클라이언트를 초기화합니다.
        self.client = genai.Client(api_key=google_api_key)

    async def generate_document_for_screen(
        self, filename: str, html_content: str, associated_requirements: List[Dict]
    ) -> str:
        """단일 화면에 대한 '설명 부분'만 HTML 형식으로 생성합니다."""
        print(f"  -> Agent: '{filename}' 화면 텍스트 설명 생성 중...")
        
        prompt = f"""
        당신은 UI/UX 화면을 분석하여 매우 상세하고 정형화된 '화면 정의서'를 작성하는 시스템 분석가입니다. 
        주어진 HTML 코드와 연관 요구사항을 분석하여, 아래 [출력 형식]에 맞춰 결과물을 HTML 형식으로 생성해야 합니다.

        [분석 대상 화면 파일명]: {filename}
        [화면 HTML 코드]: ```html\n{html_content}\n```
        [연관 요구사항 목록]: ```json\n{json.dumps(associated_requirements, ensure_ascii=False, indent=2)}\n```

        [작업 지침]
        1. HTML과 요구사항을 분석하여, 화면의 구성 요소와 인터랙션을 파악합니다.
        2. [출력 형식]에 따라, **HTML 본문(body 태그 내부)에 들어갈 내용만** 작성합니다. (상단 헤더 테이블과 이미지는 제외)

        [출력 형식 - HTML]
        <h2>1. 화면 구성 요소 (Screen Components)</h2>
        <table border="1">
          </table>

        <h2>2. 주요 인터랙션 (Key Interactions)</h2>
        <ul>
            </ul>
        """
        
        # 동기 함수인 generate_content를 별도 스레드에서 실행하여 비동기 환경에서 블로킹 방지
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-1.5-pro-latest",
            contents=prompt,
            config={"temperature": 0.0}
        )
        
        cleaned_html = response.text.strip()
        if cleaned_html.startswith("```html"):
            cleaned_html = cleaned_html[7:]
        if cleaned_html.endswith("```"):
            cleaned_html = cleaned_html[:-3]
        
        return cleaned_html.strip()

    async def generate_function_flows(self, screen_overviews: Dict[str, List]) -> Dict[str, str]:
        """전체 화면 관계를 분석하여 기능 흐름도를 Mermaid 문법으로 생성합니다."""
        print("  -> Agent: 전체 기능 흐름도 생성 중...")
        
        prompt = f"""
        당신은 화면 목록 정보를 받아서, 기능 흐름도를 Mermaid 문법으로 생성하는 시스템입니다. 다른 설명이나 대화 없이, 오직 요청된 JSON 객체만을 출력해야 합니다.
        
        ---
        [요청 및 출력 예시]
        ... (이전과 동일하여 생략)
        ---

        [실제 입력 데이터]
        ```json
        {json.dumps(screen_overviews, indent=2)}
        ```
        """
        
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-1.5-pro-latest",
            contents=prompt,
            config={"temperature": 0.0}
        )
        
        try:
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response.text)
            if json_match:
                return json.loads(json_match.group(1))
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            print("❌ LLM 응답에서 JSON을 파싱하는데 실패했습니다: ", e)
            print("--- 받은 원본 텍스트 ---\n", response.text)
            raise e
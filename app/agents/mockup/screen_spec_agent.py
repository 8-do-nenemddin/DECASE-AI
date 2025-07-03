# app/agents/mockup/screen_spec_agent.py
import json
import re
import os
import asyncio
from typing import List, Dict, Any
from datetime import datetime

from google import genai
from app.core.config import GEMINI_MODEL

class ScreenSpecAgent:
    """
    주어진 데이터를 바탕으로 화면 설계 및 기능 흐름 분석을 수행하는 핵심 에이전트.
    파일 I/O나 외부 통신 없이 오직 분석 로직에만 집중합니다.
    """
    def __init__(self, google_api_key: str):
        # API 클라이언트를 초기화합니다.
        self.client = genai.Client(api_key=google_api_key)
    
    def html_template(self) -> str:
        # [수정] .format()에서 오류가 나지 않도록 style 태그 안의 { }를 {{ }}로 이스케이프
        return """
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>화면 정의서</title>
    <style>
      body {
         {
          font-family: Arial, sans-serif;
          margin: 20px;
          background-color: #f5f5f5;
        }
      }
      .container {
         {
          background-color: white;
          padding: 20px;
          border-radius: 5px;
          box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
      }
    </style>
  </head>
  <body>
    <div class="container">
      <table
        border="1"
        style="width: 100%; border-collapse: collapse; font-size: 12px"
      >
        <tr>
          <td
            colspan="1"
            style="
              padding: 8px;
              background-color: #5b9bd5;
              color: white;
              font-weight: bold;
              text-align: center;
            "
          >
            화면ID
          </td>
          <td
            colspan="1"
            style="padding: 8px; background-color: white; text-align: center"
          >
            {screenId}
          </td>
          <td
            colspan="1"
            style="
              padding: 8px;
              background-color: #5b9bd5;
              color: white;
              font-weight: bold;
              text-align: center;
            "
          >
            화면명
          </td>
          <td
            colspan="2"
            style="padding: 8px; background-color: white; text-align: center"
          >
            {screenName}
          </td>
          <td
            colspan="1"
            style="
              padding: 8px;
              background-color: #5b9bd5;
              color: white;
              font-weight: bold;
              text-align: center;
            "
          >
            최종변경일자
          </td>
          <td colspan="1" style="padding: 8px; background-color: white">
            {lastModifiedDate}
          </td>
        </tr>
        <tr>
          <td
            colspan="1"
            style="
              padding: 8px;
              background-color: #5b9bd5;
              color: white;
              font-weight: bold;
              text-align: center;
            "
          >
            설명
          </td>
          <td colspan="4" style="padding: 8px; background-color: white">
            {description}
          </td>
          <td
            colspan="1"
            style="
              padding: 8px;
              background-color: #5b9bd5;
              color: white;
              font-weight: bold;
              text-align: center;
            "
          >
            작성자
          </td>
          <td colspan="1" style="padding: 8px; background-color: white">
            {author}
          </td>
        </tr>
        <tr>
          <td
            colspan="7"
            style="
              padding: 8px;
              background-color: #5b9bd5;
              color: white;
              font-weight: bold;
              text-align: center;
            "
          >
            화면 레이아웃
          </td>
        </tr>
        <tr>
          <td
            rowspan="3"
            colspan="4"
            style="padding: 15px; vertical-align: top; width: 65%"
          >
            <div
              style="
                border: 1px solid #ddd;
                padding: 10px;
                text-align: center;
                background-color: #f9f9f9;
                min-height: 350px;
              "
            >
              <img
                src="{imagePath}"
                style="width: 100%; height: 100%; object-fit: contain"
                alt="화면 이미지"
              />
            </div>
          </td>
          <td
            style="
              padding: 8px;
              background-color: #5b9bd5;
              color: white;
              font-weight: bold;
              text-align: center;
            "
          >
            구성
          </td>
          <td
            colspan="2"
            style="padding: 8px; background-color: white; vertical-align: top"
          >
            {configuration}
          </td>
        </tr>
        <tr>
          <td
            style="
              padding: 8px;
              background-color: #5b9bd5;
              color: white;
              font-weight: bold;
              text-align: center;
            "
          >
            처리절차
          </td>
          <td
            colspan="2"
            style="padding: 8px; background-color: white; vertical-align: top"
          >
            {processFlow}
          </td>
        </tr>
        <tr>
          <td
            style="
              padding: 8px;
              background-color: #5b9bd5;
              color: white;
              font-weight: bold;
              text-align: center;
            "
          >
            제약사항
          </td>
          <td
            colspan="2"
            style="padding: 8px; background-color: white; vertical-align: top"
          >
            {constraints}
          </td>
        </tr>
      </table>
    </div>
  </body>
</html>
        """
    

    async def generate_spec_json(
        self, filename: str, html_content: str
    ) -> Dict[str, Any]:
        print(f"-> Agent: '{filename}' 화면 분석 및 JSON 데이터 생성 시작...")

        prompt = f"""
        당신은 UI/UX 화면을 분석하여 화면 정의서의 각 항목을 채울 텍스트를 생성하는 전문 시스템 분석가입니다.
        주어진 HTML 코드를 분석하여, 아래 [출력 형식]에 명시된 키를 가진 JSON 객체를 생성해야 합니다.

        [분석 대상 화면 파일명]: {filename}
        [화면 HTML 코드]:
        ```html
        {html_content}
        ```

        [작업 지침]
        1.  **screenId**: 화면의 고유 ID를 `DEC-PM-XXX-M0` 형식에 맞춰 생성합니다.
        2.  **description**: HTML 코드 내용을 기반으로 화면의 목적과 핵심 기능을 요약하는 '설명'을 작성합니다.
        3.  **configuration**: 화면의 주요 UI 요소(예: 헤더, 테이블, 버튼 등)가 어떻게 '구성'되어 있는지 설명합니다.
        4.  **processFlow**: 사용자가 이 화면에서 수행할 일반적인 작업 '처리 절차'를 순서대로 설명합니다.
        5.  **constraints**: 이 화면을 구현하거나 사용할 때 고려해야 할 '제약 사항'이나 규칙을 2~3가지 항목으로 작성합니다.
        6.  반드시 유효한 JSON 형식으로만 응답해야 하며, 응답의 시작과 끝에 ```json 이나 ``` 와 같은 마크다운 코드 블록을 포함하지 마십시오.

        [출력 형식 - JSON 예시]
        {{
            "screenId": "DEC-PM-009-M0",
            "description": "특정 항목의 변경 전/후 데이터를 비교하며 상세 내역을 확인하고, 이를 승인/반려 처리하는 화면입니다.",
            "configuration": "화면은 상단에 요청 기본정보, 중앙에 비교 영역, 하단에 이력 정보로 구성됩니다.",
            "processFlow": "1. 관리자는 변경 전/후 데이터를 비교 검토합니다.\\n2. '승인' 또는 '반려' 버튼을 클릭하여 요청을 처리합니다.\\n3. 처리 결과는 이력에 자동으로 기록됩니다.",
            "constraints": "• '수정' 유형의 요청일 경우에만 변경 전/후 비교 영역이 표시되어야 합니다.\\n• 승인/반려 처리는 해당 권한을 가진 관리자만 가능해야 합니다."
        }}
        """

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.1,
                "response_mime_type": "application/json" # [수정] JSON 응답 형식 지정
            }
        )
        try:
            # [수정] llm 응답 앞뒤의 마크다운 블록을 안전하게 제거
            clean_response_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            generated_data = json.loads(clean_response_text)
        except json.JSONDecodeError as e:
            print(f"Error: LLM 응답을 JSON으로 파싱하는 데 실패했습니다. 원본: {response.text}")
            raise e # 오류 발생 시 중단

        final_spec = {
            "screenId": generated_data.get("screenId", "ID-생성-오류"),
            "description": generated_data.get("description", ""),
            "configuration": generated_data.get("configuration", ""),
            "processFlow": generated_data.get("processFlow", ""),
            "constraints": generated_data.get("constraints", ""),
            "screenName": os.path.splitext(os.path.basename(filename))[0],
            "lastModifiedDate": datetime.now().strftime('%Y.%m.%d'),
            "author": "" # 필요시 작성자 정보 추가
        }
        print(f"-> Agent: '{filename}' 화면 분석 및 JSON 생성 완료.")
        return final_spec
    
    @staticmethod
    def fill_html_with_json(spec_json: Dict[str, Any], template_html: str) -> str:
        """
        주어진 JSON 데이터로 HTML 템플릿의 플레이스홀더를 채워 최종 HTML 텍스트를 반환합니다.
        .format() 대신 .replace()를 사용하여 템플릿 내의 중괄호와 충돌을 피합니다.
        """
        print("-> HTML 템플릿에 데이터 채우는 중...")
        
        # .format() 대신 체이닝(chaining) 방식으로 .replace()를 사용
        filled_html = template_html.replace("{screenId}", spec_json.get("screenId", ""))
        filled_html = filled_html.replace("{screenName}", spec_json.get("screenName", ""))
        filled_html = filled_html.replace("{lastModifiedDate}", spec_json.get("lastModifiedDate", ""))
        filled_html = filled_html.replace("{description}", spec_json.get("description", ""))
        filled_html = filled_html.replace("{author}", spec_json.get("author", ""))
        filled_html = filled_html.replace("{configuration}", spec_json.get("configuration", "").replace("\n", "<br />"))
        filled_html = filled_html.replace("{processFlow}", spec_json.get("processFlow", "").replace("\n", "<br />"))
        filled_html = filled_html.replace("{constraints}", spec_json.get("constraints", "").replace("\n", "<br />"))
        filled_html = filled_html.replace("{imagePath}", spec_json.get("imagePath", ""))
        
        print("-> HTML 생성 완료.")
        return filled_html
    
    def generate_screen_spec(self, input_data: str) -> str:
        """
        주어진 입력 데이터를 바탕으로 화면 정의서를 생성합니다.
        """
        print("-> 화면 정의서 생성 시작...")
        
        # 입력 데이터를 JSON으로 파싱
        try:
            spec_json = json.loads(input_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"입력 데이터가 올바른 JSON 형식이 아닙니다: {e}")
        
        # HTML 템플릿을 가져옵니다.
        template_html = self.html_template()
        
        # JSON 데이터를 HTML 템플릿에 채웁니다.
        filled_html = self.fill_html_with_json(spec_json, template_html)
        
        print("-> 화면 정의서 생성 완료.")
        return filled_html
    

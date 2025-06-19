# app/agents/mockup_generator_agent.py
import re

import json
import anthropic # 추가
from typing import Dict, Any

class HtmlGenerator:
    def __init__(self, claude_client: anthropic.Anthropic):
        self.client = claude_client
        self.model = "claude-4-sonnet-20250514"

    def _call_claude(self, prompt: str) -> str:
        try:
            print(f"Claude HTML 생성 요청 중...")
            response = self.client.messages.create(model=self.model, system="You are a world-class UI/UX Design Lead. Respond ONLY with the full, raw HTML code.", messages=[{"role": "user", "content": prompt}], max_tokens=20000, temperature=0.1)
            text = response.content[0].text
            match = re.search(r'```(html)?\s*([\s\S]*?)\s*```', text, re.I)
            return match.group(2).strip() if match else text
        except Exception as e:
            return f"<h1>Claude Error</h1><p>{e}</p>"

    def generate_html_page(self, page_plan: Dict[str, Any], navigation_html: str, project_name: str) -> str:
        page_title = page_plan.get('page_title_ko', '페이지')
        print(f"📄 '{page_title}' 페이지 HTML 생성 요청...")
        
        source_reqs = page_plan.get('source_requirements', [])
        main_title_html = f"<h1>{page_title}</h1>"
        
        # ▼▼▼ '사족'이 될 수 있는 지시문을 content_prompt에서 제거합니다 ▼▼▼
        if page_plan.get('is_main_page'):
            content_prompt_data = f"{main_title_html}\n{json.dumps(page_plan.get('widgets', []), ensure_ascii=False, indent=2)}"
            final_instruction = f"환영 메시지('{page_plan.get('welcome_message', '')}')와 위 위젯 아이디어를 바탕으로 대시보드 형태의 콘텐츠를 구성해주십시오."
            traceability_html = ""
        else:
            feature_details_text = "\n".join([f"- **{req.get('description')} (ID: {req.get('id')})**\n  - 상세 내용: {req.get('description_detailed')}\n" for req in source_reqs])
            content_prompt_data = f"{main_title_html}\n<hr>\n<strong>[필수 구현 기능 목록]</strong>\n{feature_details_text}"
            final_instruction = "위 '필수 구현 기능 목록'의 상세 내용을 충실히 반영하여, 사용자가 실제로 기능을 사용할 수 있는 구체적인 UI 목업을 구성해주십시오."

            # 하단의 추적성 정보는 그대로 유지합니다.
            traceability_html = "<details style='margin-top: 50px; padding: 15px; border: 1px solid #eee; border-radius: 5px; background-color: #f9f9f9;'><summary style='cursor: pointer; font-weight: bold;'>이 페이지에 반영된 전체 요구사항 ({len(source_reqs)}개)</summary><ul style='margin-top: 10px;'>"
            for req in source_reqs:
                traceability_html += f"<li><strong>{req.get('id')}: {req.get('description')}</strong><p>{req.get('description_detailed')}</p></li>"
            traceability_html += "</ul></details>"

        # ▼▼▼ 지시와 데이터를 명확히 분리한 최종 프롬프트 ▼▼▼
        prompt = f"""
        **지시:**
        1. 아래 '메인 콘텐츠 데이터'를 바탕으로 완전한 단일 HTML 페이지를 생성해줘.
        2. 공통 요구사항: <!DOCTYPE html> 부터 </html> 까지, 반응형 2단 레이아웃(좌:사이드바, 우:메인), `<title>`은 '{page_title} | {project_name}'
        3. 사이드바 콘텐츠: 프로젝트 이름 '{project_name}'과 아래의 HTML 링크 목록을 그대로 포함.
        ```html
        {navigation_html}
        ```
        4. **[핵심 임무]** {final_instruction}

        ---
        **메인 콘텐츠 데이터:**
        {content_prompt_data}
        ---
        
        **추적성 정보 (메인 콘텐츠 하단에 포함):**
        {traceability_html}

        ---
        **최종 결과물:** 다른 설명 없이, 완성된 HTML 코드만 응답.
        """
        return self._call_claude(prompt)

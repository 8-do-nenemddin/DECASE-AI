# app/agents/meeting_analyzer_agent.py
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.core.config import OPENAI_API_KEY, GPT_MODEL
from app.schemas.request import MeetingActionItem

# client = OpenAI(api_key=OPENAI_API_KEY) # 모듈 레벨 또는 함수 내에서 생성

def summarize_meeting_text(full_text: str) -> str :
    client_instance = OpenAI(api_key=OPENAI_API_KEY)
    """
    LLM을 이용하여 회의록을 요약해서 보여주는 agent
    """
    prompt = f"""
# 역할 (Role)
당신은 IT 프로젝트의 요구사항 변경 관리 전문가이자 시니어 비즈니스 분석가(Senior Business Analyst)입니다. 당신의 임무는 회의록을 분석하여 요구사항의 변경 내역을 정확하게 식별하고 구조화하여 문서화하는 것입니다.

# 맥락 (Context)
이 텍스트는 '소프트웨어 요구사항 정의서(SRS)'의 변경점을 논의하고 확정하기 위한 회의의 녹취록입니다. 따라서 회의의 모든 논의는 요구사항의 추가, 수정, 삭제에 초점이 맞춰져 있습니다.

# 임무 (Task)
아래 회의록 텍스트를 분석하여, '주요 요구사항 변경사항'을 아래 형식에 맞춰 요약해 주세요.

# 출력 형식: HTML (Output Format: HTML)
* 최종 요약 결과는 다른 설명 없이, 아래에 정의된 HTML 구조에 맞춰 코드만 반환해야 합니다.
* 각 항목의 내용은 간결한 명사형(개조식)으로 작성하여 채워주세요.
* 회의록에서 근거(요청자, 사유)를 찾을 수 없는 경우, '관련 근거' 셀은 비워두거나 '특이사항 없음'으로 표시합니다.

# HTML 출력 템플릿
<!DOCTYPE html>
<html lang="ko">
<body>
    <table class="summary-table">
        <caption>[회의 제목]</caption>
        <thead>
            <tr>
                <th class="category">구분</th>
                <th>핵심 내용</th>
                <th>관련 근거 (요청자/사유)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td class="category">회의 핵심 결의사항</td>
                <td colspan="2"></td>
            </tr>
            <tr>
                <td class="category">추가된 요구사항 (Added)</td>
                <td><ul></ul></td>
                <td><ul></ul></td>
            </tr>
            <tr>
                <td class="category">수정된 요구사항 (Modified)</td>
                <td><ul></ul></td>
                <td><ul></ul></td>
            </tr>
            <tr>
                <td class="category">삭제된 요구사항 (Deleted)</td>
                <td><ul></ul></td>
                <td><ul></ul></td>
            </tr>
        </tbody>
    </table>
</body>
</html>

회의록:
\"\"\"
{full_text}
\"\"\"
"""
    try:
        response = client_instance.chat.completions.create(
            model = GPT_MODEL,
            messages = [
                {"role": "system", "content": "당신은 전문 회의록 요약가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        summary = response.choices[0].message.content.strip()

        if "```html" in summary:
            summary = summary.split("```html")[1].split("```")[0].strip()
        elif "<!DOCTYPE html>" in summary:
            summary = summary[summary.find("<!DOCTYPE html>"):]
            
        return summary
    
    except Exception as e:
        print(f"[회의록 요약 실패]: {e}")
        return "요약 생성에 실패했습니다."
import json
from pathlib import Path
from google import genai
from google.genai import types

from typing import Any, Dict, List

from app.core.config import GEMINI_MODEL

def refine_single_requirement(client: genai.Client, requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
    """단일 요구사항 객체를 받아, 내부에 여러 기능이 있으면 개별 요구사항으로 분해합니다."""
    print(f"  - 세분화 처리 중: '{requirement['requirement_name']}'")

    prompt = f"""
<prompt>
    <persona>
        당신은 요구사항을 가장 작은 실행 단위(atomic unit)로 분해하는 전문 시스템 분석가입니다. 당신의 임무는 하나의 요구사항 설명에 포함된 여러 개의 개별 기능을 각각 독립적인 요구사항으로 만드는 것입니다.
    </persona>
    <goal>
        아래 `<original_requirement>` JSON 객체를 분석하여, 포함된 각 개별 기능들을 별개의 요구사항 JSON 객체로 분리하십시오.
    </goal>
    <instructions>
        1. `description` 필드와 `requirement_name` 필드를 주의 깊게 읽고, 독립적으로 개발 및 테스트할 수 있는 모든 개별 기능/작업/산출물을 식별합니다.
        2. 식별된 각 개별 기능에 대해 **새로운 JSON 객체**를 생성합니다.
        3. **새로운 `requirement_name`**: 원본 이름에 특정 기능명을 조합하여 "원본 요구사항 명 - 세부 기능명" 형식으로 새로 만드세요. (예: "학습운영시스템 고도화 기획 - 시스템 벤치마킹")
        4. **새로운 `description`**: 오직 해당 단일 기능에 대한 설명만 포함하도록 간결하게 재작성합니다.
        5. **필수 유지 필드**: 원본의 `type`, `sources`, `target_page` 필드는 **내용 변경 없이 그대로 복사**하여 새로 생성된 모든 객체에 포함시켜야 합니다.
        6. 만약 원본 요구사항이 더 이상 분해할 수 없는 단일 기능이라면, 추가 작업 없이 원본 객체 하나만 배열에 담아 반환합니다.
    </instructions>
    <original_requirement>
    {json.dumps(requirement, indent=2, ensure_ascii=False)}
    </original_requirement>
    최종 결과는 다른 설명 없이 오직 JSON 배열 형식으로만 반환하십시오.
</prompt>
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1
            }
        )
        split_requirements = json.loads(response.text)
        if len(split_requirements) > 1:
            print(f"    splits into -> {len(split_requirements)} sub-requirements.")
        return split_requirements
    except Exception as e:
        print(f"    ❌ 세분화 중 오류 발생: {e}. 원본 요구사항을 그대로 유지합니다.")
        return [requirement]
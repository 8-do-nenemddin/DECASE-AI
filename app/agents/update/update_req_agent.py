import json
from typing import List, Dict, Any

from google import genai as genai
from app.core.config import GEMINI_MODEL

def analyze_requirement_changes(
    client: genai.Client,
    existing_requirements: List[Dict[str, Any]],
    file_content_str: str,
    filename: str 
) -> Dict[str, List[Dict[str, Any]]]:
    """
    기존 요구사항과 새로 업로드된 문서를 비교하여, 새로운 스키마에 맞는
    '추가/수정/삭제' 변경 제안 딕셔너리를 생성합니다.
    """
    print("🤖 Agent를 호출하여 요구사항 변경사항 분석을 시작합니다...")

    req_list_str = json.dumps(existing_requirements, indent=2, ensure_ascii=False)

    # ✨ [수정] '회의록' -> '추가 자료' 또는 '문서'로 용어 변경
    # ✨ [수정] 'modified_reason' 지침 및 예시 변경
    prompt = f"""
    당신은 IT 프로젝트의 요구사항 변경을 관리하는 매우 꼼꼼한 시스템 분석가입니다.
    당신의 임무는 [기존 요구사항 목록]과 새로 들어온 [추가 자료]를 비교 분석하여, 요구사항의 '추가', '수정', '삭제'가 필요한 항목을 식별하고 그 근거를 명확히 하여 JSON 형식으로 제안하는 것입니다.

    [기존 요구사항 목록]
    ```json
    {req_list_str}
    ```

    [추가 자료]
    파일명: {filename}
    ---
    {file_content_str}
    ---

    [작업 지침 및 최종 출력 JSON 구조]
    1.  **정확한 식별**: 문서를 기반으로 변경이 필요한 기존 요구사항을 `requirement_id`를 통해 정확히 식별합니다.
    2.  **변경 유형 분류**: 각 변경 사항을 `to_add`(추가), `to_update`(수정), `to_delete`(삭제) 세 가지 유형으로 분류합니다.
    3.  **엄격한 스키마 준수**: 반드시 아래에 명시된 스키마와 필드명을 가진 단일 JSON 객체로만 응답해야 합니다. 모든 필드명은 **스네이크 케이스(snake_case)**를 사용해야 합니다.
    4.  **`to_add` 지침**: 새로운 요구사항을 생성합니다. 모든 필드를 채워야 합니다.
        - `target_page`: 요구사항 설명에 기반하여 관련된 UI 페이지나 기능을 명시합니다. (예: "로그인 페이지")
        - `type`: 유형은 "기능", "비기능" 중 하나로 설정합니다.
        - `importance`: 중요도는 "HIGH", "MIDDLE", "LOW" 중 하나로 설정합니다.
        - `difficulty`: 난이도는 "HIGH", "MIDDLE", "LOW" 중 하나로 설정합니다.
    5.  **`to_update` 지침**: **매우 중요합니다.** 수정이 필요한 요구사항의 **전체 필드를 모두 포함**해야 합니다.
        - 먼저 `requirement_id`로 기존 요구사항을 찾습니다.
        - 문서 내용에 따라 변경이 필요한 필드의 값만 수정합니다.
        - **수정되지 않은 필드들은 반드시 기존 요구사항의 값을 그대로 채워 넣습니다.**
        - `modified_reason` 필드에 수정 사유를 반드시 작성합니다.
        - 사유는 '`{filename}`에 따라' 라는 형식으로 시작합니다.
    6.  **`to_delete` 지침**: 삭제할 요구사항의 `requirement_id`와 삭제 사유(`modified_reason`)만 포함합니다.

    ```json
    {{
      "to_add": [
        {{
          "requirement_id": "SYS-FR-0001",
          "requirement_name": "소셜 로그인 기능",
          "type": "기능",
          "description": "사용자가 카카오, 구글 등 소셜 계정을 이용하여 간편하게 로그인하거나 회원가입하는 기능을 제공합니다.",
          "target_page": "로그인, 회원가입 페이지",
          "level1": "사용자 관리",
          "level2": "로그인",
          "level3": "소셜 로그인",
          "importance": "HIGH",
          "difficulty": "MIDDLE",
          "modified_reason": "{filename}에 따라 사용자 편의성 증대를 위해 추가"
        }}
      ],
      "to_update": [
        {{
          "requirement_id": "CMS-FR-0002",
          "requirement_name": "게시물 목록 조회 기능",
          "type": "기능",
          "description": "작성된 게시물 목록을 페이지네이션과 함께 조회하는 기능을 구현합니다. 정렬 옵션으로 최신순과 인기순(조회수 기준)을 제공합니다.",
          "target_page": "게시판",
          "level1": "콘텐츠 관리",
          "level2": "게시판",
          "level3": "게시물 목록 조회",
          "importance": "HIGH",
          "difficulty": "LOW",
          "modified_reason": "{filename}에 따라 인기순 정렬 옵션을 추가하기 위함"
        }}
      ],
      "to_delete": [
        {{
          "requirement_id": "USR-FR-0005",
          "modified_reason": "{filename}의 '내 정보 조회/수정 기능 통합' 결정에 따라 해당 기능이 '내 정보 관리' 요구사항에 통합되었으므로 삭제 처리함."
        }}
      ]
    }}
    ```

    이제 분석을 시작하여 최종 제안 JSON을 생성하십시오.
    """
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "temperature": 0.0,
                "response_mime_type": "application/json"
            }
        )
        extracted_updates = json.loads(response.text)
        print("✅ 요구사항 변경사항 분석 완료.")
        print("변경사항:", json.dumps(extracted_updates, indent=2, ensure_ascii=False))

        return extracted_updates
    except Exception as e:
        print(f"❌ 분석 중 오류 발생: {e}")
        raise RuntimeError(f"요구사항 변경사항 분석 중 오류 발생: {e}")
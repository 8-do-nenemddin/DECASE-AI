# app/services/mockup_service.py
import os
import json
from typing import List, Tuple, Dict, Any

# 새롭게 리팩토링된 UiMockupAgent를 임포트합니다.
from app.agents.mockup.mockup_agent import UiMockupAgent

def run_mockup_generation_pipeline(
    input_data: str,
    output_folder_name: str | None = None
) -> List[Tuple[str, str]]:
    """
    요청 데이터를 받아 UiMockupAgent를 실행하고,
    생성된 모든 파일(HTML + JSON Map)의 (이름, 내용) 리스트를 반환하는 파이프라인입니다.
    """
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    if not GOOGLE_API_KEY or not ANTHROPIC_API_KEY:
        raise ValueError("Google 또는 Anthropic API 키가 .env 파일에 설정되지 않았습니다.")

    try:
        requirements_data: List[Dict[str, Any]] = json.loads(input_data)
    except json.JSONDecodeError as e:
        raise ValueError(f"입력 데이터 JSON 파싱 실패: {str(e)}")

    agent = UiMockupAgent(
        requirements_data=requirements_data,
        google_api_key=GOOGLE_API_KEY,
        anthropic_api_key=ANTHROPIC_API_KEY
    )
    project_name = output_folder_name or "생성된 목업 프로젝트"
    html_files, map_data = agent.run(project_name=project_name)
    
    map_file_content = json.dumps(map_data, ensure_ascii=False, indent=2)
    all_files = html_files + [("_page_to_requirements_map.json", map_file_content)]

    return all_files
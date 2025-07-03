# app/services/screen_spec_service.py
import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import httpx
from playwright.async_api import async_playwright

from app.agents.mockup.screen_spec_agent import ScreenSpecAgent
from app.core.config import GOOGLE_API_KEY
from app.models.job import JobStatusEnum
from app.services.job_services import update_job_status_in_db # config 파일에서 API 키를 가져온다고 가정

# --- 서비스의 핵심 실행 함수 ---

async def generate_spec_and_flow_documents(mockup_dir_str: str, output_dir_str: str, job_id: int, project_id: int, revision_count: int, callback_url: str):
    """
    전체 프로세스를 관장하는 서비스 함수.
    파일 로드, 스크린샷, Agent 호출, 파일 저장을 모두 수행합니다.
    """
    mockup_dir = Path(mockup_dir_str)
    output_dir = Path(output_dir_str)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🚀 산출물 생성 파이프라인 시작! (입력: {mockup_dir}, 출력: {output_dir})")
    
    # 1. 파일 시스템에서 데이터 로드
    page_map, html_contents, req_data = _load_input_files(mockup_dir)
    
    # 2. Agent 초기화
    agent = ScreenSpecAgent(google_api_key=GOOGLE_API_KEY)
    
    # 3. 각 화면별 설계서 생성 (비동기 동시 처리)
    tasks = []
    for filename, html_content in html_contents.items():
        associated_reqs = [req_data.get(req_id) for req_id in page_map.get(filename, []) if req_data.get(req_id)]
        tasks.append(
            # [수정] associated_reqs 인자 제거 (현재 로직에서 사용되지 않음)
            _process_single_screen(agent, filename, html_content, mockup_dir, output_dir)
        )
    if tasks:
        await asyncio.gather(*tasks)

    # 4. (옵션) 기능 흐름도 생성 로직을 여기에 추가할 수 있습니다.
    # 화면정의서 생성 완료 콜백
    async with httpx.AsyncClient() as client:
            print(project_id)
            params = {
                "projectId": project_id,
                "revisionCount": revision_count,
                "status": "COMPLETED",
            }

            try:
                response = await client.post(callback_url, params=params, timeout=60)
                print(f"Job[{job_id}]: 콜백 요청 완료. 응답 코드: {response.status_code}")
                if response.status_code != 200:
                    raise Exception(f"콜백 요청 실패: 응답 코드 {response.status_code}, 응답 내용: {response.text}")
                # 4. Job 완료 상태 업데이트
                await update_job_status_in_db(job_id, JobStatusEnum.COMPLETED)
            except httpx.RequestError as e:
                print(f"Job[{job_id}]: 콜백 요청 실패: {e}")
                await update_job_status_in_db(job_id, JobStatusEnum.FAILED)
            except Exception as e:
                print(f"Job[{job_id}]: 콜백 요청 실패: {e}")
                await update_job_status_in_db(job_id, JobStatusEnum.FAILED)
     
    print("🎉 모든 작업이 완료되었습니다.")


# [수정] 함수의 로직을 에이전트의 흐름에 맞게 완전히 변경
async def _process_single_screen(agent: ScreenSpecAgent, filename: str, html_content: str, mockup_dir: Path, output_dir: Path):
    """한 화면에 대한 스크린샷, 분석, HTML 조립 및 저장을 처리합니다."""
    print(f"📄 '{filename}' 화면에 대한 전체 문서 작업 시작...")
    
    html_path = mockup_dir / filename
    # 최종 결과물에서 상대 경로로 이미지를 참조하기 위해 경로 설정
    screenshot_filename = html_path.stem + ".png"
    screenshot_path = output_dir / screenshot_filename
    
    # 1. 스크린샷 캡처 (결과물 폴더에 바로 저장)
    try:
        await _capture_screenshot(html_path, screenshot_path)
        print(f"  📸 -> '{filename}' 스크린샷 캡처 완료: {screenshot_path}")
    except Exception as e:
        print(f"  -> ⚠️ '{filename}' 스크린샷 생성 중 오류 발생: {e}")
        return

    # 2. Agent를 통해 분석 데이터(JSON) 생성
    spec_data = await agent.generate_spec_json(filename, html_content)
    if not spec_data:
        print(f"  -> ⚠️ '{filename}' 분석 데이터 생성 실패.")
        return
        
    # 3. 분석 데이터에 스크린샷 경로 추가
    # HTML 파일에서 이미지를 참조해야 하므로, 파일명만 넘겨 상대 경로로 사용
    spec_data["imagePath"] = screenshot_filename

    # 4. Agent의 템플릿과 데이터를 사용해 최종 HTML 조립
    template_html = agent.html_template()
    full_html = ScreenSpecAgent.fill_html_with_json(spec_data, template_html)

    # 5. 최종 화면정의서 파일 저장
    spec_filename = Path(filename).stem + "_spec.html"
    final_path = output_dir / spec_filename
    with open(final_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
    print(f"  💾 -> '{final_path}' 화면 정의서 파일로 저장 완료.\n")


# --- 유틸리티 및 헬퍼 함수 ---

def _load_input_files(mockup_dir: Path):
    map_file_path = mockup_dir / "_page_to_requirements_map.json"
    if not map_file_path.exists(): raise FileNotFoundError(f"매핑 파일을 찾을 수 없습니다: {map_file_path}")
    with open(map_file_path, 'r', encoding='utf-8') as f: raw_data = json.load(f)
    
    page_map, html_contents, req_data = {}, {}, {}
    for page_info in raw_data.get("page_mapping", []):
        html_filename = page_info.get("generated_file")
        if not html_filename: continue
        source_reqs = page_info.get("source_requirements", [])
        page_map[html_filename] = [req.get("id") for req in source_reqs if req.get("id")]
        for req in source_reqs:
            if req_id := req.get("id"):
                req_data[req_id] = {"requirement_id": req_id, "description": req.get("description", ""), "name": f"{req_id} 이름"}
        html_file_path = mockup_dir / html_filename
        if html_file_path.exists():
            with open(html_file_path, 'r', encoding='utf-8') as f: html_contents[html_filename] = f.read()
    return page_map, html_contents, req_data

async def _capture_screenshot(html_path: Path, output_path: Path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(html_path.resolve().as_uri())
        await page.screenshot(path=output_path)
        await browser.close()
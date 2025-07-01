# app/services/screen_spec_service.py
import os
import json
import base64
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from playwright.async_api import async_playwright

from app.agents.mockup.screen_spec_agent import ScreenSpecAgent
from app.core.config import GOOGLE_API_KEY # config 파일에서 API 키를 가져온다고 가정

# --- 서비스의 핵심 실행 함수 ---

async def generate_spec_and_flow_documents(mockup_dir_str: str, output_dir_str: str):
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
            _process_single_screen(agent, filename, html_content, associated_reqs, mockup_dir, output_dir)
        )
    if tasks:
        await asyncio.gather(*tasks)

    # 4. (옵션) 기능 흐름도 생성 로직을 여기에 추가할 수 있습니다.
    
    print("🎉 모든 작업이 완료되었습니다.")


async def _process_single_screen(agent: ScreenSpecAgent, filename: str, html_content: str, associated_reqs: List, mockup_dir: Path, output_dir: Path):
    """한 화면에 대한 스크린샷, 분석, HTML 조립 및 저장을 처리합니다."""
    print(f"📄 '{filename}' 화면에 대한 전체 문서 작업 시작...")
    
    html_path = mockup_dir / filename
    screenshot_path = mockup_dir / (html_path.stem + ".png")
    
    # 스크린샷 캡처
    try:
        await _capture_screenshot(html_path, screenshot_path)
    except Exception as e:
        print(f"  -> ⚠️ '{filename}' 스크린샷 생성 중 오류 발생: {e}")
        return

    # Agent를 통해 설명 생성
    description_html = await agent.generate_document_for_screen(filename, html_content, associated_reqs)
    if not description_html:
        return
        
    # 최종 HTML 조립
    relative_image_path = f"../{mockup_dir.name}/{screenshot_path.name}"
    header_html = f"""<table border="1" style="width:100%; border-collapse: collapse;"><tr style="background-color:#f2f2f2;"><th style="padding:8px; text-align:left;">Page Title</th><td style="padding:8px;">{Path(filename).stem}</td><th style="padding:8px; text-align:left;">Screen ID</th><td style="padding:8px;">{filename}</td><th style="padding:8px; text-align:left;">Date</th><td style="padding:8px;">{datetime.now().strftime('%Y.%m.%d')}</td></tr></table>"""
    image_html = f"""<h2>1. 화면 이미지</h2><div style="text-align:center; margin: 20px 0; border: 1px solid #ddd; padding: 10px;"><img src="{relative_image_path}" alt="{filename} Screen Capture" style="max-width: 100%; height: auto;"></div>"""
    final_body = header_html + image_html + description_html
    full_html = _wrap_in_html(f"화면설계서: {filename}", final_body)

    # 파일 저장
    spec_filename = Path(filename).stem + "_spec.html"
    with open(output_dir / spec_filename, 'w', encoding='utf-8') as f:
        f.write(full_html)
    print(f"  💾 -> '{output_dir / spec_filename}' 파일로 저장 완료.\n")

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

def _wrap_in_html(title: str, body_content: str) -> str:
    style = """<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;line-height:1.6;padding:1em 2em;color:#333}h1,h2{border-bottom:1px solid #eaecef;padding-bottom:.3em}table{border-collapse:collapse;width:100%;margin:1em 0}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background-color:#f6f8fa}code{background-color:#f0f0f0;padding:2px 5px;border-radius:4px}</style>"""
    return f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>{title}</title>{style}</head><body>{body_content}</body></html>'
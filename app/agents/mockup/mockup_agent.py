# app/agents/mockup_agent.py

import re
from typing import List, Dict, Any, Tuple
import google.generativeai as genai
import anthropic

from app.agents.mockup.mockup_analyzer_agent import RequirementsAnalyzer
from app.agents.mockup.mockup_planner_agent import MockupPlanner
from app.agents.mockup.mockup_generator_agent import HtmlGenerator

def sanitize_filename(name: str) -> str:
    if not isinstance(name, str): name = str(name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name[:100]

class UiMockupAgent:
    def __init__(self, requirements_data: List[Dict[str, Any]], google_api_key: str, anthropic_api_key: str):
        if not requirements_data: raise ValueError("요구사항 데이터가 없습니다.")
        if not google_api_key or not anthropic_api_key: raise ValueError("API 키가 설정되지 않았습니다.")

        self.requirements_data = requirements_data
        genai.configure(api_key=google_api_key)
        self.anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)
        
        self.system_overview: str = "N/A"
        self.feature_specs: List[Dict[str, Any]] = []
        self.main_page_plan: Dict[str, Any] = {}
        self.page_plans: List[Dict[str, Any]] = []
        
        self._initialize_components_and_plan()

    def _initialize_components_and_plan(self):
        print("--- 에이전트 초기화: 요구사항 분석 및 페이지 기획 시작 ---")
        analyzer = RequirementsAnalyzer(self.requirements_data)
        self.feature_specs = analyzer.get_feature_specifications()
        if not self.feature_specs: raise ValueError("기능 명세를 추출할 수 없어 프로세스를 중단합니다.")
        self.system_overview = analyzer.get_system_overview()
        
        planner = MockupPlanner(self.feature_specs, self.system_overview)
        self.main_page_plan = planner.plan_user_main_page()
        self.page_plans = planner.define_pages_and_features()
        if not self.main_page_plan or not self.page_plans: raise ValueError("페이지 계획을 수립할 수 없어 프로세스를 중단합니다.")
        print("✅ 에이전트 초기화 및 사전 기획 완료.")

    def _create_navigation_html(self) -> str:
        main_page_title = self.main_page_plan.get("page_title_ko", "홈")
        nav_html = '<ul>\n'
        nav_html += f'    <li><a href="index.html">{main_page_title} (홈)</a></li>\n'
        for page in self.page_plans:
            page_name = page.get("page_name")
            if not page_name: continue
            file_name = f"{sanitize_filename(page_name)}.html"
            title = page.get('page_title_ko', page_name)
            nav_html += f'    <li><a href="{file_name}">{title}</a></li>\n'
        nav_html += '</ul>'
        return nav_html

    def run(self, project_name: str) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
        print(f"\n🚀 '{project_name}' 프로젝트 목업 생성 실행 시작...")
        generator = HtmlGenerator(self.anthropic_client)
        navigation_html = self._create_navigation_html()
        generated_files = []
        feature_specs_map = {spec['id']: spec for spec in self.feature_specs}
        
        all_page_plans = [self.main_page_plan] + self.page_plans
        print(f"--- 총 {len(all_page_plans)}개 페이지 순차 생성 시작 ---")

        for page_plan in all_page_plans:
            if not page_plan.get('is_main_page', False):
                 page_plan['source_requirements'] = [feature_specs_map[fid] for fid in page_plan.get('included_feature_ids', []) if fid in feature_specs_map]
            page_html = generator.generate_html_page(page_plan, navigation_html, project_name)
            if page_html and "Error" not in page_html:
                filename = "index.html" if page_plan.get('is_main_page') else f"{sanitize_filename(page_plan.get('page_name', 'untitled'))}.html"
                generated_files.append((filename, page_html))
                print(f"👍 '{filename}' 콘텐츠 생성 성공")
            else:
                print(f"⚠️ '{page_plan.get('page_title_ko', 'N/A')}' 페이지 생성 실패.")

        page_map_data = self._create_page_map(project_name)
        print(f"\n🎉 에이전트 작업 완료! 총 {len(generated_files)}개 파일 콘텐츠 생성.")
        return generated_files, page_map_data

    def _create_page_map(self, project_name: str) -> Dict[str, Any]:
        page_map_data = {"project_name": project_name, "total_pages": len(self.page_plans) + 1, "page_mapping": []}
        page_map_data["page_mapping"].append({
            "page_title": self.main_page_plan.get('page_title_ko', '메인 페이지'), "generated_file": "index.html",
            "source_requirement_count": 0, "source_requirements": []
        })
        for page in self.page_plans:
            reqs = page.get('source_requirements', [])
            page_map_data["page_mapping"].append({
                "page_title": page.get('page_title_ko'), "generated_file": f"{sanitize_filename(page.get('page_name'))}.html",
                "source_requirement_count": len(reqs),
                "source_requirements": [{"id": r.get('id'), "description": r.get('description')} for r in reqs]
            })
        return page_map_data
# app/agents/mockup_planner_agent.py
import json
import re
from typing import List, Dict, Any
import google.generativeai as genai
class MockupPlanner:
    def __init__(self, feature_specs: List[Dict[str, Any]], system_overview: str):
        self.feature_specs = feature_specs
        self.system_overview = system_overview
        self.model_name = "gemini-2.5-pro"
        self.analysis_cache = {}

    def _call_gemini(self, prompt_text: str, cache_key: str, system_message: str, is_json: bool = True) -> str | None:
        if cache_key in self.analysis_cache: return self.analysis_cache[cache_key]
        try:
            print(f"Gemini 계획 요청 중 (키: {cache_key})...")
            generation_config = {"temperature": 0.1}
            if is_json: generation_config["response_mime_type"] = "application/json"
            model = genai.GenerativeModel(self.model_name, system_instruction=system_message, generation_config=generation_config)
            response = model.generate_content(prompt_text)
            result = response.text.strip()
            self.analysis_cache[cache_key] = result
            return result
        except Exception as e:
            print(f"❌ Gemini 호출 실패 (키: {cache_key}) → {e}")
            return None

    def define_pages_and_features(self) -> List[Dict[str, Any]]:
        print("--- 페이지 구조 및 기능 할당 기획 시작 (Gemini) ---")
        features_for_grouping = "\n".join([f"- ID: {spec['id']}, 설명: {spec['description']}, 모듈: {spec['module']}" for spec in self.feature_specs])
        prompt = f"""
        **시스템 개요:** {self.system_overview}
        **전체 기능 목록 ({len(self.feature_specs)}개):**
        {features_for_grouping}
        ---
        **지시:**
        위 전체 기능 목록을 '모듈'을 중심으로 논리적인 페이지들로 그룹화해주십시오. 하나의 페이지가 너무 많은 기능을 갖지 않도록 적절히 분할해야 합니다.
        
        **JSON 출력 형식:**
        - 최상위 키는 "pages"이고, 값은 페이지 객체 리스트여야 합니다.
        - 각 페이지 객체는 다음을 포함해야 합니다: `page_name` (영문), `page_title_ko` (한글), `page_description` (설명), `included_feature_ids` (해당 페이지에 할당된 기능 ID 리스트)
        - 모든 기능 ID가 단 한 번씩만 할당되어야 합니다.
        """
        system_message = "You are an expert information architect. Your task is to group features into logical pages. Respond ONLY in a valid JSON object with a 'pages' key."
        structure_str = self._call_gemini(prompt, "page_structure_and_features_v_simple", system_message, is_json=True)
        if not structure_str:
            print("🔴 페이지 계획 생성 실패. Fallback 로직을 사용합니다.")
            return [{"page_name": "Fallback_Page", "page_title_ko": "전체 기능 목록", "page_description": "모든 기능을 포함하는 페이지", "included_feature_ids": [spec['id'] for spec in self.feature_specs]}]
        try:
            pages = json.loads(structure_str).get("pages", [])
            print(f"✅ {len(pages)}개의 페이지 계획 생성 완료.")
            return pages
        except (json.JSONDecodeError, ValueError) as e:
            print(f"🚨 페이지 계획 파싱 오류: {e}")
            return [{"page_name": "Fallback_Page", "page_title_ko": "전체 기능 목록", "page_description": "모든 기능을 포함하는 페이지", "included_feature_ids": [spec['id'] for spec in self.feature_specs]}]

    def plan_user_main_page(self) -> Dict[str, Any]:
        print("메인 페이지 콘텐츠 기획 중 (Gemini)...")
        # (기존 로직과 동일)
        features_list_str = "\n".join([f"- {spec['description']}" for spec in self.feature_specs[:15]])
        prompt = f'시스템 개요: {self.system_overview}\n핵심 기능 샘플:\n{features_list_str}\n---\n지시: 메인 페이지(홈 대시보드) 콘텐츠를 기획해주세요.\nJSON 형식: {{ "page_title_ko": "...", "welcome_message": "...", "widgets": [...] }}'
        system_message = "You are a UX planner designing a user-centric main page. Respond ONLY in a valid JSON object."
        plan_str = self._call_gemini(prompt, "plan_user_main_page_gemini_v1", system_message, is_json=True)
        if not plan_str: return {"page_title_ko": "메인 페이지", "welcome_message": "환영합니다!", "widgets": [], "is_main_page": True}
        try:
            plan = json.loads(plan_str)
            plan['is_main_page'] = True
            return plan
        except json.JSONDecodeError:
            return {"page_title_ko": "메인 페이지", "welcome_message": "환영합니다!", "widgets": [], "is_main_page": True}
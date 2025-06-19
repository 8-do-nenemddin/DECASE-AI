import collections
from typing import List, Dict, Any
import google.generativeai as genai
class RequirementsAnalyzer:
    def __init__(self, requirements_data: List[Dict[str, Any]]):
        self.requirements = requirements_data
        self.model_name = "gemini-2.5-pro"
        self.analysis_cache = {}

    def _call_gemini(self, prompt_text: str, cache_key: str, system_message: str, is_json: bool = False) -> str | None:
        if cache_key in self.analysis_cache: return self.analysis_cache[cache_key]
        try:
            print(f"Gemini 분석 요청 중 (키: {cache_key})...")
            generation_config = {"temperature": 0.1}
            if is_json:
                generation_config["response_mime_type"] = "application/json"
            model = genai.GenerativeModel(self.model_name, system_instruction=system_message, generation_config=generation_config)
            response = model.generate_content(prompt_text)
            result = response.text.strip()
            self.analysis_cache[cache_key] = result
            return result
        except Exception as e:
            print(f"❌ Gemini 호출 실패 (키: {cache_key}) → {e}")
            return None

    def get_feature_specifications(self) -> List[Dict[str, Any]]:
        feature_specs = []
        if not self.requirements: return []
        target_reqs = [req for req in self.requirements if req.get("type") == "기능"]
        print(f"분석 대상 기능적 요구사항 수: {len(target_reqs)}")
        for i, req in enumerate(target_reqs):
            feature_specs.append({
                "id": req.get("requirement_id", f"FUNC-{i+1:03}"),
                "description": req.get("requirement_name", "제목 없음").strip(),
                "description_detailed": req.get("description", "").strip(),
                "module": req.get("category_medium", "미분류"),
                "priority": req.get("importance", "중"),
            })
        print(f"{len(feature_specs)}개의 주요 기능 명세 추출 완료.")
        return feature_specs

    def get_system_overview(self) -> str:
        if not self.requirements: return "요구사항 데이터 없음"
        print("--- 시스템 개요 분석 시작 (Gemini) ---")
        all_specs = self.get_feature_specifications()
        module_groups = collections.defaultdict(list)
        for spec in all_specs:
            module_groups[spec['module']].append(spec)
        print(f"✅ 총 {len(all_specs)}개의 요구사항을 {len(module_groups)}개의 모듈 그룹으로 분류했습니다.")
        sub_summaries = []
        for module_name, features_in_module in module_groups.items():
            feature_names = [spec['description'] for spec in features_in_module]
            prompt = f"'{module_name}' 모듈에 속한 기능 목록입니다:\n{chr(10).join(f'- {name}' for name in feature_names)}\n\n이 모듈의 핵심적인 역할과 목적을 한두 문장으로 요약해 주십시오."
            sub_summary = self._call_gemini(prompt, f"overview_module_{module_name}", "You are a helpful assistant.")
            if sub_summary: sub_summaries.append(f"'{module_name}' 모듈: {sub_summary}")
        final_summary_input = "\n".join(f"- {s}" for s in sub_summaries)
        prompt = f"다음은 시스템을 구성하는 각 모듈의 역할 요약입니다.\n{final_summary_input}\n\n위 내용을 종합하여 전체 시스템의 핵심 목적, 주요 사용자, 추천 프로젝트 이름을 요약해주십시오."
        overview = self._call_gemini(prompt, "overview_final_smart_grouping", "You are a system architect.")
        if not overview: overview = f"총 {len(all_specs)}개의 요구사항을 가진 시스템."
        print("✅ 시스템 개요 생성 완료.")
        return overview
# app/services/id_management_service.py

import os
import json
import time
from typing import Dict, Any
from openai import OpenAI
from app.core.config import OPENAI_API_KEY, GPT_MODEL

# LLM을 사용하므로 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

class RequirementIdManager:
    """
    '대상업무'와 '대분류'를 기반으로 3글자 약어를 생성하여
    고유 ID를 부여하는 클래스.
    """
    def __init__(self, counter_file='req_task_cat_counters.json'):
        # 새로운 ID 규칙을 위한 새 카운터 파일
        self.counter_file = counter_file
        self.counters = self._load_counters()

    def _load_counters(self) -> Dict[str, int]:
        try:
            with open(self.counter_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _save_counters(self):
        with open(self.counter_file, 'w', encoding='utf-8') as f:
            json.dump(self.counters, f, indent=2, ensure_ascii=False)

    def _get_3_letter_code(self, text: str) -> str:
        """LLM을 통해 주어진 텍스트의 핵심 의미를 나타내는 3글자 영문 코드를 생성합니다."""
        if not text:
            return "XXX"

        prompt = f"""
        당신은 주어진 한글 텍스트의 핵심 의미를 분석하여, 업계에서 통용될 만한 3글자 영문 대문자 약어(Abbreviation)를 생성하는 전문가입니다.

        [생성 규칙]
        1. 텍스트의 핵심 주제(Core Subject)를 파악합니다.
        2. 널리 알려진 약어(LMS, ERP, CRM, API 등)가 있다면 최우선으로 사용합니다.
        3. 널리 알려진 약어가 없다면, 핵심 단어들에서 대표 철자를 조합하여 가장 논리적인 3글자 코드를 만듭니다.
        4. 최종 결과는 반드시 3글자 영문 대문자여야 합니다.

        [처리 예시]
        - 입력: '학습관리시스템 구축' -> 결과: LMS
        - 입력: '시스템 운영' -> 결과: SYS

        이제 다음 텍스트에 대한 3글자 영문 대문자 약어를 생성해주십시오. 추가 설명 없이 약어만 반환하십시오.

        [텍스트]
        "{text}"
        """
        try:
            response = client.chat.completions.create(
                model=GPT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            code = response.choices[0].message.content.strip().upper()
            return ''.join(filter(str.isalpha, code))[:3]
        except Exception as e:
            print(f"3글자 코드 생성 오류 ({text}): {e}")
            return "ERR"

    def generate_id(self, data_to_process: Dict[str, Any]) -> str:
        """
        주어진 데이터를 기반으로 ID 문자열만 생성하여 반환하고,
        내부적으로 상태(카운터)는 업데이트합니다.
        """
        target_task = data_to_process.get('target_task', 'UnknownTask')
        category_large = data_to_process.get('category_large', 'UnknownCategory')

        # 각 정보에 대한 3글자 코드 생성
        task_code = self._get_3_letter_code(target_task)
        time.sleep(0.5) # API Rate Limit 방지
        large_cat_code = self._get_3_letter_code(category_large)

        # 코드를 조합하여 ID 접두사 생성
        id_prefix_base = f"{task_code}-{large_cat_code}"
        
        current_number = self.counters.get(id_prefix_base, 0)
        next_number = current_number + 1
        
        # 'REQ-' 접두사를 포함한 최종 ID 생성
        final_id = f"REQ-{id_prefix_base}-{next_number:04d}"

        # 상태 업데이트 및 저장
        self.counters[id_prefix_base] = next_number
        self._save_counters()
        
        return final_id
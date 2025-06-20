# app/services/llm_call_service.py
import json
import google.generativeai as genai
from openai import OpenAI
from typing import Any, Optional, List, Dict

from app.core.config import GPT_MODEL, OPENAI_API_KEY, GOOGLE_API_KEY, GEMINI_MODEL

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

# Google Gemini 초기화
genai.configure(api_key=GOOGLE_API_KEY)

# === 3. LLM 호출 헬퍼 함수 (기존과 동일) ===
def call_gpt(
    system_prompt: str,
    user_prompt: str,
    is_json_output: bool = False
) -> Optional[Any]:
    global client, GPT_MODEL
    llm_response_content = ""
    try:
        request_params = {
            "model": GPT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 4000
        }
        if is_json_output:
            request_params["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**request_params)
        llm_response_content = response.choices[0].message.content

        if llm_response_content is None:
            print("경고: LLM으로부터 응답 내용이 없습니다.")
            return None

        if is_json_output:
            return json.loads(llm_response_content)
        return llm_response_content

    except json.JSONDecodeError as e:
        print(f"LLM 응답 JSON 파싱 오류: {e}. 응답: {llm_response_content[:500]}...")
        return None
    except Exception as e:
        print(f"LLM API 호출 또는 처리 중 오류 발생: {type(e).__name__} - {e}")
        if llm_response_content:
            print(f"오류 발생 시 LLM 응답 일부: {llm_response_content[:500]}...")
        return None
    

def call_gemini(prompt: str, is_json_output: bool = False) -> Optional[Any]:
    """Google Gemini API를 호출하는 함수"""
    try:
        model_instance = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config={"temperature": 0.2, "response_mime_type": "application/json" if is_json_output else "text/plain"},
        )

        response = model_instance.generate_content(prompt)
        response_text = response.text

        if is_json_output:
            return json.loads(response_text)
        return response_text

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from Gemini response: {e}. Response: {response_text[:500]}...")
        return None
    except Exception as e:
        print(f"An error occurred during Gemini API call: {type(e).__name__} - {e}")
        return None

"""QueryEnhancer 테스트"""

from unittest.mock import MagicMock

import pytest

from src.rag.query_enhancer import LLMQueryEnhancer, NoopQueryEnhancer


class TestNoopQueryEnhancer:
    """NoopQueryEnhancer 테스트 - 항상 원본 반환"""

    def test_returns_original_query(self):
        enhancer = NoopQueryEnhancer()
        query = "연차 휴가는 며칠이야?"

        result = enhancer.enhance(query)

        assert result == query

    def test_ignores_history(self):
        enhancer = NoopQueryEnhancer()
        query = "그건 어떻게 작동해?"
        history = [
            {"role": "user", "content": "Gemini API 사용법 알려줘"},
            {"role": "assistant", "content": "Gemini API는..."},
        ]

        result = enhancer.enhance(query, history=history)

        assert result == query  # 히스토리 무시하고 원본 반환


class TestLLMQueryEnhancer:
    """LLMQueryEnhancer 테스트"""

    def test_skip_when_no_history(self):
        """히스토리 없으면 원본 반환"""
        mock_llm = MagicMock()
        enhancer = LLMQueryEnhancer(llm_client=mock_llm)
        query = "연차 휴가는 며칠이야?"

        result = enhancer.enhance(query, history=None)

        assert result == query
        mock_llm.call.assert_not_called()

    def test_skip_when_empty_history(self):
        """빈 히스토리면 원본 반환"""
        mock_llm = MagicMock()
        enhancer = LLMQueryEnhancer(llm_client=mock_llm)
        query = "연차 휴가는 며칠이야?"

        result = enhancer.enhance(query, history=[])

        assert result == query
        mock_llm.call.assert_not_called()

    def test_skip_when_single_message_history(self):
        """히스토리가 1개면 원본 반환 (첫 질문)"""
        mock_llm = MagicMock()
        enhancer = LLMQueryEnhancer(llm_client=mock_llm)
        query = "Gemini API 사용법 알려줘"
        history = [{"role": "user", "content": query}]

        result = enhancer.enhance(query, history=history)

        assert result == query
        mock_llm.call.assert_not_called()

    def test_calls_llm_with_history(self):
        """히스토리 있으면 LLM 호출"""
        mock_response = MagicMock()
        mock_response.content = "Gemini API 작동 방식"
        mock_llm = MagicMock()
        mock_llm.call.return_value = mock_response

        enhancer = LLMQueryEnhancer(llm_client=mock_llm)
        query = "그건 어떻게 작동해?"
        history = [
            {"role": "user", "content": "Gemini API 사용법 알려줘"},
            {"role": "assistant", "content": "Gemini API는 Google의 생성형 AI API입니다."},
        ]

        result = enhancer.enhance(query, history=history)

        assert result == "Gemini API 작동 방식"
        mock_llm.call.assert_called_once()

    def test_truncates_long_content(self):
        """긴 메시지는 300자로 제한"""
        mock_response = MagicMock()
        mock_response.content = "개선된 쿼리"
        mock_llm = MagicMock()
        mock_llm.call.return_value = mock_response

        enhancer = LLMQueryEnhancer(llm_client=mock_llm, max_content_length=50)
        query = "더 알려줘"
        long_content = "A" * 100  # 100자 메시지
        history = [
            {"role": "user", "content": "질문"},
            {"role": "assistant", "content": long_content},
        ]

        enhancer.enhance(query, history=history)

        # LLM 호출 시 전달된 프롬프트 확인
        call_args = mock_llm.call.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]
        # 100자가 50자로 잘리고 "..." 추가됨
        assert "A" * 50 + "..." in prompt
        assert "A" * 100 not in prompt

    def test_uses_recent_messages_only(self):
        """최근 N개 메시지만 사용"""
        mock_response = MagicMock()
        mock_response.content = "개선된 쿼리"
        mock_llm = MagicMock()
        mock_llm.call.return_value = mock_response

        enhancer = LLMQueryEnhancer(llm_client=mock_llm, max_history=2)
        query = "더 알려줘"
        history = [
            {"role": "user", "content": "첫번째 질문"},
            {"role": "assistant", "content": "첫번째 답변"},
            {"role": "user", "content": "두번째 질문"},
            {"role": "assistant", "content": "두번째 답변"},
        ]

        enhancer.enhance(query, history=history)

        # LLM 호출 시 최근 2개만 포함되어야 함
        call_args = mock_llm.call.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]
        assert "첫번째 질문" not in prompt
        assert "첫번째 답변" not in prompt
        assert "두번째 질문" in prompt
        assert "두번째 답변" in prompt

    def test_returns_original_on_llm_error(self):
        """LLM 에러 시 원본 반환"""
        mock_llm = MagicMock()
        mock_llm.call.side_effect = Exception("LLM 에러")

        enhancer = LLMQueryEnhancer(llm_client=mock_llm)
        query = "그건 어떻게 작동해?"
        history = [
            {"role": "user", "content": "Gemini API 사용법"},
            {"role": "assistant", "content": "Gemini API는..."},
        ]

        result = enhancer.enhance(query, history=history)

        assert result == query  # 원본 반환

    def test_returns_original_on_empty_response(self):
        """빈 응답이면 원본 반환"""
        mock_response = MagicMock()
        mock_response.content = "   "  # 공백만 있는 응답
        mock_llm = MagicMock()
        mock_llm.call.return_value = mock_response

        enhancer = LLMQueryEnhancer(llm_client=mock_llm)
        query = "그건 어떻게 작동해?"
        history = [
            {"role": "user", "content": "Gemini API 사용법"},
            {"role": "assistant", "content": "Gemini API는..."},
        ]

        result = enhancer.enhance(query, history=history)

        assert result == query  # 원본 반환

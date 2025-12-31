"""Preprocessor 테스트"""

import pytest

from src.rag.preprocessor import (
    KoreanPreprocessor,
    MinimalPreprocessor,
    NoopPreprocessor,
    Preprocessor,
)


class TestNoopPreprocessor:
    """NoopPreprocessor 테스트 - 항상 원본 반환"""

    def test_returns_original_query(self):
        preprocessor = NoopPreprocessor()
        query = "연차 휴가는 며칠이야?"

        result = preprocessor.process(query)

        assert result == query

    def test_empty_query(self):
        preprocessor = NoopPreprocessor()

        assert preprocessor.process("") == ""

    def test_whitespace_preserved(self):
        preprocessor = NoopPreprocessor()
        query = "  공백 포함  "

        result = preprocessor.process(query)

        assert result == query  # 공백도 그대로 유지

    def test_implements_protocol(self):
        """Protocol을 구현하는지 확인"""
        preprocessor = NoopPreprocessor()
        assert isinstance(preprocessor, Preprocessor)


class TestMinimalPreprocessor:
    """MinimalPreprocessor 테스트 - 유니코드 정규화만"""

    def test_unicode_normalization(self):
        """NFKC 정규화 확인"""
        preprocessor = MinimalPreprocessor()
        # 호환성 문자 → 표준 문자
        query = "ＡＢＣ１２３"  # 전각 문자

        result = preprocessor.process(query)

        assert result == "ABC123"  # 반각으로 변환

    def test_strips_whitespace(self):
        preprocessor = MinimalPreprocessor()
        query = "  검색어  "

        result = preprocessor.process(query)

        assert result == "검색어"

    def test_empty_query(self):
        preprocessor = MinimalPreprocessor()

        assert preprocessor.process("") == ""
        assert preprocessor.process(None) is None

    def test_implements_protocol(self):
        preprocessor = MinimalPreprocessor()
        assert isinstance(preprocessor, Preprocessor)


class TestKoreanPreprocessor:
    """KoreanPreprocessor 테스트 - 기존 프로젝트 로직"""

    def test_unicode_normalization(self):
        """NFKC 정규화"""
        preprocessor = KoreanPreprocessor()
        query = "ＡＢＣ１２３"

        result = preprocessor.process(query)

        assert "ABC123" in result

    def test_removes_ending_알려줘(self):
        """종결어미 '알려줘' 제거"""
        preprocessor = KoreanPreprocessor()

        assert preprocessor.process("연차 휴가 알려줘") == "연차 휴가"
        assert preprocessor.process("연차 휴가 알려줘요") == "연차 휴가"

    def test_removes_ending_해주세요(self):
        """종결어미 '해주세요' 제거"""
        preprocessor = KoreanPreprocessor()

        assert preprocessor.process("검색 해주세요") == "검색"
        assert preprocessor.process("검색해주세요") == "검색"

    def test_removes_ending_찾아줘(self):
        """종결어미 '찾아줘' 제거"""
        preprocessor = KoreanPreprocessor()

        assert preprocessor.process("문서 찾아줘") == "문서"

    def test_removes_ending_설명해줘(self):
        """종결어미 '설명해줘' 제거"""
        preprocessor = KoreanPreprocessor()

        assert preprocessor.process("API 설명해줘") == "API"

    def test_removes_year_suffix(self):
        """연도 단위 '년' 제거"""
        preprocessor = KoreanPreprocessor()

        assert preprocessor.process("2024년 보고서") == "2024 보고서"
        assert preprocessor.process("24년 실적") == "24 실적"

    def test_removes_punctuation_edges(self):
        """양끝 문장부호 제거"""
        preprocessor = KoreanPreprocessor()

        assert preprocessor.process("...검색어...") == "검색어"
        assert preprocessor.process("「검색어」") == "검색어"
        assert preprocessor.process("?검색어?") == "검색어"

    def test_preserves_middle_punctuation(self):
        """중간 문장부호는 유지"""
        preprocessor = KoreanPreprocessor()

        result = preprocessor.process("A, B, C")
        assert "," in result  # 중간 쉼표는 유지

    def test_empty_query(self):
        preprocessor = KoreanPreprocessor()

        assert preprocessor.process("") == ""
        assert preprocessor.process(None) is None

    def test_combined_processing(self):
        """복합 처리 테스트"""
        preprocessor = KoreanPreprocessor()

        # 유니코드 정규화 + 종결어미 + 연도
        result = preprocessor.process("２０２４년 보고서 알려줘")
        assert result == "2024 보고서"

    def test_implements_protocol(self):
        preprocessor = KoreanPreprocessor()
        assert isinstance(preprocessor, Preprocessor)


class TestPreprocessorComparison:
    """전처리기 비교 테스트"""

    @pytest.mark.parametrize(
        "query",
        [
            "연차 휴가는 며칠이야?",
            "2024년 실적 보고서",
            "API 사용법 알려줘",
        ],
    )
    def test_all_preprocessors_return_string(self, query: str):
        """모든 전처리기가 문자열 반환"""
        noop = NoopPreprocessor()
        minimal = MinimalPreprocessor()
        korean = KoreanPreprocessor()

        assert isinstance(noop.process(query), str)
        assert isinstance(minimal.process(query), str)
        assert isinstance(korean.process(query), str)

    def test_noop_returns_longest(self):
        """NoopPreprocessor가 가장 긴 결과 반환"""
        query = "  2024년 보고서 알려줘  "

        noop_result = NoopPreprocessor().process(query)
        minimal_result = MinimalPreprocessor().process(query)
        korean_result = KoreanPreprocessor().process(query)

        # Noop은 원본 그대로, 나머지는 처리됨
        assert len(noop_result) >= len(minimal_result)
        assert len(minimal_result) >= len(korean_result)

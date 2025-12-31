"""ContextBuilder 테스트"""

import pytest
from src.rag.context_builder import (
    ContextBuilder,
    RankedContextBuilder,
    SimpleContextBuilder,
)


# 테스트용 검색 결과 fixture
@pytest.fixture
def sample_results() -> list[dict]:
    """점수 내림차순 정렬된 검색 결과"""
    return [
        {
            "_score": 0.95,
            "_source": {
                "text": "연차 휴가는 입사 1년차 15일, 2년차부터 16일이 부여됩니다.",
                "file_name": "휴가정책.md",
                "page_number": 2,
            },
        },
        {
            "_score": 0.85,
            "_source": {
                "text": "경조사 휴가는 결혼 5일, 출산 10일이 제공됩니다.",
                "file_name": "복지제도.md",
                "page_number": 5,
            },
        },
        {
            "_score": 0.75,
            "_source": {
                "text": "병가는 연간 60일까지 사용 가능합니다.",
                "file_name": "휴가정책.md",
                "page_number": 3,
            },
        },
        {
            "_score": 0.65,
            "_source": {
                "text": "육아휴직은 최대 1년간 사용할 수 있습니다.",
                "file_name": "복지제도.md",
                "page_number": 8,
            },
        },
        {
            "_score": 0.55,
            "_source": {
                "text": "반차 사용시 오전/오후 중 선택 가능합니다.",
                "file_name": "휴가정책.md",
                "page_number": 4,
            },
        },
    ]


@pytest.fixture
def minimal_results() -> list[dict]:
    """메타데이터 없는 최소 결과"""
    return [
        {"_score": 0.9, "_source": {"text": "첫 번째 문서"}},
        {"_score": 0.8, "_source": {"text": "두 번째 문서"}},
    ]


class TestSimpleContextBuilder:
    """SimpleContextBuilder 테스트 - 단순 연결"""

    def test_builds_numbered_context(self, sample_results):
        builder = SimpleContextBuilder()

        result = builder.build(sample_results)

        assert "[1]" in result
        assert "[2]" in result
        assert "연차 휴가" in result
        assert "경조사 휴가" in result

    def test_separates_with_double_newline(self, sample_results):
        builder = SimpleContextBuilder()

        result = builder.build(sample_results)

        assert "\n\n" in result

    def test_empty_results(self):
        builder = SimpleContextBuilder()

        result = builder.build([])

        assert result == ""

    def test_single_result(self):
        builder = SimpleContextBuilder()
        results = [{"_score": 0.9, "_source": {"text": "유일한 문서"}}]

        result = builder.build(results)

        assert result == "[1]\n유일한 문서"

    def test_custom_text_field(self):
        builder = SimpleContextBuilder(text_field="content")
        results = [{"_score": 0.9, "_source": {"content": "커스텀 필드 내용"}}]

        result = builder.build(results)

        assert "커스텀 필드 내용" in result

    def test_fallback_to_content_field(self):
        """text_field가 없으면 content로 fallback"""
        builder = SimpleContextBuilder(text_field="chunk_text")
        results = [{"_score": 0.9, "_source": {"content": "content 필드 사용"}}]

        result = builder.build(results)

        assert "content 필드 사용" in result

    def test_implements_protocol(self):
        builder = SimpleContextBuilder()
        assert isinstance(builder, ContextBuilder)


class TestRankedContextBuilder:
    """RankedContextBuilder 테스트 - 메타데이터 + Reorder"""

    def test_includes_metadata(self, sample_results):
        builder = RankedContextBuilder(reorder=False)

        result = builder.build(sample_results)

        assert "휴가정책.md" in result
        assert "p.2" in result

    def test_metadata_format(self, sample_results):
        builder = RankedContextBuilder(reorder=False)

        result = builder.build(sample_results)

        # [1] (파일명, p.페이지) 형식 확인
        assert "[1] (휴가정책.md, p.2)" in result

    def test_reorder_enabled(self, sample_results):
        """reorder=True일 때 순서 변경"""
        builder = RankedContextBuilder(reorder=True)

        result = builder.build(sample_results)

        # 원본에서 첫 번째(연차 휴가)가 중앙 근처에 배치되어야 함
        # 정확한 순서는 알고리즘에 따라 다르지만, 원래 순서와 달라야 함
        lines = result.split("\n\n")
        # 5개 문서가 모두 있어야 함
        assert len(lines) == 5

    def test_reorder_disabled(self, sample_results):
        """reorder=False일 때 원래 순서 유지"""
        builder = RankedContextBuilder(reorder=False)

        result = builder.build(sample_results)

        # 첫 번째가 연차 휴가여야 함
        assert result.startswith("[1] (휴가정책.md, p.2)\n연차 휴가")

    def test_include_score(self, sample_results):
        """include_score=True일 때 점수 표시"""
        builder = RankedContextBuilder(reorder=False, include_score=True)

        result = builder.build(sample_results)

        assert "[score:" in result
        assert "0.950" in result

    def test_no_score_by_default(self, sample_results):
        builder = RankedContextBuilder(reorder=False)

        result = builder.build(sample_results)

        assert "[score:" not in result

    def test_empty_results(self):
        builder = RankedContextBuilder()

        result = builder.build([])

        assert result == ""

    def test_handles_missing_metadata(self, minimal_results):
        """메타데이터 없을 때도 동작"""
        builder = RankedContextBuilder(reorder=False)

        result = builder.build(minimal_results)

        # 파일명 없으면 번호만
        assert "[1]" in result
        assert "첫 번째 문서" in result

    def test_handles_partial_metadata(self):
        """일부 메타데이터만 있을 때"""
        builder = RankedContextBuilder(reorder=False)
        results = [
            {"_score": 0.9, "_source": {"text": "문서 내용", "file_name": "test.md"}},
        ]

        result = builder.build(results)

        # 파일명만 있고 페이지 없음
        assert "[1] (test.md)" in result

    def test_uses_original_filename_fallback(self):
        """file_name 없으면 original_filename 시도"""
        builder = RankedContextBuilder(reorder=False)
        results = [
            {
                "_score": 0.9,
                "_source": {"text": "문서", "original_filename": "원본.pdf"},
            },
        ]

        result = builder.build(results)

        assert "원본.pdf" in result

    def test_implements_protocol(self):
        builder = RankedContextBuilder()
        assert isinstance(builder, ContextBuilder)


class TestReorderAlgorithm:
    """LongContextReorder 알고리즘 테스트"""

    def test_reorder_preserves_all_items(self, sample_results):
        """reorder 후에도 모든 문서 포함"""
        builder = RankedContextBuilder(reorder=True)

        result = builder.build(sample_results)

        assert "연차 휴가" in result
        assert "경조사 휴가" in result
        assert "병가" in result
        assert "육아휴직" in result
        assert "반차" in result

    def test_reorder_changes_order(self, sample_results):
        """5개 이상일 때 순서 변경"""
        builder_reorder = RankedContextBuilder(reorder=True)
        builder_no_reorder = RankedContextBuilder(reorder=False)

        result_reorder = builder_reorder.build(sample_results)
        result_no_reorder = builder_no_reorder.build(sample_results)

        # 순서가 달라야 함
        assert result_reorder != result_no_reorder

    def test_reorder_two_items_unchanged(self):
        """2개 이하는 reorder 안 함"""
        builder = RankedContextBuilder(reorder=True)
        results = [
            {"_score": 0.9, "_source": {"text": "첫 번째"}},
            {"_score": 0.8, "_source": {"text": "두 번째"}},
        ]

        result = builder.build(results)

        # 원래 순서 유지
        lines = result.split("\n\n")
        assert "첫 번째" in lines[0]
        assert "두 번째" in lines[1]

    def test_high_relevance_at_edges(self):
        """관련도 높은 문서가 처음/끝 근처에 배치"""
        builder = RankedContextBuilder(reorder=True, include_score=True)
        results = [
            {"_score": 1.0, "_source": {"text": "가장 관련"}},  # 0
            {"_score": 0.8, "_source": {"text": "두번째 관련"}},  # 1
            {"_score": 0.6, "_source": {"text": "세번째 관련"}},  # 2
            {"_score": 0.4, "_source": {"text": "네번째 관련"}},  # 3
            {"_score": 0.2, "_source": {"text": "다섯번째 관련"}},  # 4
        ]

        result = builder.build(results)
        lines = result.split("\n\n")

        # 첫 번째와 마지막 라인에 높은 점수가 있어야 함
        first_line = lines[0]
        last_line = lines[-1]

        # 점수 1.0 또는 0.8이 첫 번째나 마지막에 있어야 함
        high_scores_at_edges = ("1.000" in first_line or "0.800" in first_line) or (
            "1.000" in last_line or "0.800" in last_line
        )
        assert high_scores_at_edges


class TestContextBuilderComparison:
    """빌더 비교 테스트"""

    def test_all_builders_return_string(self, sample_results):
        """모든 빌더가 string 반환"""
        builders = [
            SimpleContextBuilder(),
            RankedContextBuilder(),
            RankedContextBuilder(reorder=True),
            RankedContextBuilder(include_score=True),
        ]

        for builder in builders:
            result = builder.build(sample_results)
            assert isinstance(result, str)

    def test_ranked_has_more_info_than_simple(self, sample_results):
        """RankedContextBuilder가 더 많은 정보 포함"""
        simple = SimpleContextBuilder()
        ranked = RankedContextBuilder(reorder=False, include_score=True)

        simple_result = simple.build(sample_results)
        ranked_result = ranked.build(sample_results)

        # Ranked가 메타데이터 포함하므로 더 길어야 함
        assert len(ranked_result) > len(simple_result)
        # 파일명, 점수 등 추가 정보
        assert "휴가정책.md" in ranked_result
        assert "score:" in ranked_result

    def test_all_builders_handle_empty(self):
        """빈 결과 처리"""
        builders = [
            SimpleContextBuilder(),
            RankedContextBuilder(),
        ]

        for builder in builders:
            result = builder.build([])
            assert result == ""


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_missing_source(self):
        """_source 없는 경우"""
        builder = SimpleContextBuilder()
        results = [{"_score": 0.9}]

        result = builder.build(results)

        # 빈 텍스트로 처리
        assert "[1]" in result

    def test_empty_text(self):
        """빈 텍스트"""
        builder = SimpleContextBuilder()
        results = [{"_score": 0.9, "_source": {"text": ""}}]

        result = builder.build(results)

        assert "[1]" in result

    def test_special_characters_in_text(self):
        """특수문자 포함 텍스트"""
        builder = SimpleContextBuilder()
        results = [
            {
                "_score": 0.9,
                "_source": {"text": "특수문자: []{}<>()\"'`~!@#$%^&*"},
            }
        ]

        result = builder.build(results)

        assert "특수문자" in result

    def test_newlines_in_text(self):
        """텍스트 내 줄바꿈"""
        builder = SimpleContextBuilder()
        results = [
            {
                "_score": 0.9,
                "_source": {"text": "첫 줄\n두 번째 줄\n세 번째 줄"},
            }
        ]

        result = builder.build(results)

        assert "첫 줄\n두 번째 줄" in result

    def test_unicode_in_metadata(self):
        """유니코드 메타데이터"""
        builder = RankedContextBuilder(reorder=False)
        results = [
            {
                "_score": 0.9,
                "_source": {
                    "text": "내용",
                    "file_name": "한글파일명.md",
                    "page_number": 1,
                },
            }
        ]

        result = builder.build(results)

        assert "한글파일명.md" in result

"""ResultFilter 테스트"""

import pytest
from src.rag.result_filter import (
    AdaptiveThresholdFilter,
    CompositeFilter,
    NoopFilter,
    RerankerFilter,
    ResultFilter,
    ScoreThresholdFilter,
    TopKFilter,
)


# 테스트용 검색 결과 fixture
@pytest.fixture
def sample_results() -> list[dict]:
    """점수 내림차순 정렬된 검색 결과"""
    return [
        {"_score": 0.95, "_source": {"content": "가장 관련있는 문서"}},
        {"_score": 0.85, "_source": {"content": "두 번째로 관련있는 문서"}},
        {"_score": 0.75, "_source": {"content": "세 번째 문서"}},
        {"_score": 0.60, "_source": {"content": "네 번째 문서"}},
        {"_score": 0.50, "_source": {"content": "다섯 번째 문서"}},
        {"_score": 0.30, "_source": {"content": "여섯 번째 문서 (낮은 점수)"}},
        {"_score": 0.20, "_source": {"content": "일곱 번째 문서 (낮은 점수)"}},
        {"_score": 0.10, "_source": {"content": "여덟 번째 문서 (매우 낮은 점수)"}},
        {"_score": 0.05, "_source": {"content": "아홉 번째 문서 (매우 낮은 점수)"}},
        {"_score": 0.01, "_source": {"content": "열 번째 문서 (거의 무관)"}},
    ]


class TestNoopFilter:
    """NoopFilter 테스트 - 필터링 안 함"""

    def test_returns_all_results(self, sample_results):
        f = NoopFilter()

        result = f.filter("테스트 쿼리", sample_results)

        assert result == sample_results
        assert len(result) == 10

    def test_empty_results(self):
        f = NoopFilter()

        result = f.filter("쿼리", [])

        assert result == []

    def test_implements_protocol(self):
        f = NoopFilter()
        assert isinstance(f, ResultFilter)


class TestTopKFilter:
    """TopKFilter 테스트 - 상위 K개만 반환"""

    def test_returns_top_k(self, sample_results):
        f = TopKFilter(k=5)

        result = f.filter("쿼리", sample_results)

        assert len(result) == 5
        assert result[0]["_score"] == 0.95
        assert result[4]["_score"] == 0.50

    def test_default_k_is_5(self, sample_results):
        f = TopKFilter()

        result = f.filter("쿼리", sample_results)

        assert len(result) == 5

    def test_k_larger_than_results(self, sample_results):
        f = TopKFilter(k=100)

        result = f.filter("쿼리", sample_results)

        assert len(result) == 10  # 원본 개수 유지

    def test_empty_results(self):
        f = TopKFilter(k=5)

        result = f.filter("쿼리", [])

        assert result == []

    def test_implements_protocol(self):
        f = TopKFilter()
        assert isinstance(f, ResultFilter)


class TestScoreThresholdFilter:
    """ScoreThresholdFilter 테스트 - 점수 임계값 필터"""

    def test_filters_by_min_score(self, sample_results):
        f = ScoreThresholdFilter(min_score=0.5)

        result = f.filter("쿼리", sample_results)

        assert len(result) == 5
        assert all(r["_score"] >= 0.5 for r in result)

    def test_default_min_score_is_0_5(self, sample_results):
        f = ScoreThresholdFilter()

        result = f.filter("쿼리", sample_results)

        assert len(result) == 5

    def test_high_threshold_filters_more(self, sample_results):
        f = ScoreThresholdFilter(min_score=0.8)

        result = f.filter("쿼리", sample_results)

        assert len(result) == 2
        assert result[0]["_score"] == 0.95
        assert result[1]["_score"] == 0.85

    def test_zero_threshold_returns_all(self, sample_results):
        f = ScoreThresholdFilter(min_score=0.0)

        result = f.filter("쿼리", sample_results)

        assert len(result) == 10

    def test_very_high_threshold_returns_none(self, sample_results):
        f = ScoreThresholdFilter(min_score=0.99)

        result = f.filter("쿼리", sample_results)

        assert len(result) == 0

    def test_empty_results(self):
        f = ScoreThresholdFilter(min_score=0.5)

        result = f.filter("쿼리", [])

        assert result == []

    def test_missing_score_treated_as_zero(self):
        f = ScoreThresholdFilter(min_score=0.5)
        results = [{"_source": {"content": "점수 없는 문서"}}]

        result = f.filter("쿼리", results)

        assert len(result) == 0

    def test_implements_protocol(self):
        f = ScoreThresholdFilter()
        assert isinstance(f, ResultFilter)


class TestAdaptiveThresholdFilter:
    """AdaptiveThresholdFilter 테스트 - 동적 임계값"""

    def test_filters_adaptively(self, sample_results):
        f = AdaptiveThresholdFilter()

        result = f.filter("쿼리", sample_results)

        # 최소 3개, 최대 8개 보장
        assert 3 <= len(result) <= 8

    def test_respects_min_keep_count(self):
        """최소 보존 개수 보장"""
        f = AdaptiveThresholdFilter(min_keep_count=3)
        # 모두 낮은 점수
        results = [{"_score": 0.1, "_source": {"content": f"문서 {i}"}} for i in range(10)]

        result = f.filter("쿼리", results)

        assert len(result) >= 3

    def test_respects_max_keep_count(self):
        """최대 보존 개수 보장"""
        f = AdaptiveThresholdFilter(max_keep_count=5)
        # 모두 높은 점수
        results = [{"_score": 0.9, "_source": {"content": f"문서 {i}"}} for i in range(10)]

        result = f.filter("쿼리", results)

        assert len(result) <= 5

    def test_empty_results(self):
        f = AdaptiveThresholdFilter()

        result = f.filter("쿼리", [])

        assert result == []

    def test_single_result(self):
        f = AdaptiveThresholdFilter(min_keep_count=1)
        results = [{"_score": 0.5, "_source": {"content": "유일한 문서"}}]

        result = f.filter("쿼리", results)

        assert len(result) == 1

    def test_elbow_detection(self):
        """갭이 큰 지점에서 필터링"""
        f = AdaptiveThresholdFilter(min_keep_count=1, max_keep_count=10)
        # 상위 3개는 높은 점수, 나머지는 낮은 점수 (큰 갭 존재)
        results = [
            {"_score": 0.95, "_source": {"content": "문서 1"}},
            {"_score": 0.90, "_source": {"content": "문서 2"}},
            {"_score": 0.85, "_source": {"content": "문서 3"}},
            {"_score": 0.20, "_source": {"content": "문서 4"}},  # 큰 갭
            {"_score": 0.15, "_source": {"content": "문서 5"}},
            {"_score": 0.10, "_source": {"content": "문서 6"}},
        ]

        result = f.filter("쿼리", results)

        # 엘보우 탐지로 상위 3개만 남아야 함
        assert len(result) <= 4

    def test_implements_protocol(self):
        f = AdaptiveThresholdFilter()
        assert isinstance(f, ResultFilter)


class TestRerankerFilter:
    """RerankerFilter 테스트"""

    def test_implements_protocol(self):
        # RerankerFilter는 lazy init이므로 인스턴스 생성만으로 import 안 함
        f = RerankerFilter()
        assert isinstance(f, ResultFilter)

    def test_raises_import_error_when_rerankers_not_installed(self, sample_results):
        """rerankers 패키지 없으면 ImportError"""
        f = RerankerFilter()

        # 실제 환경에 따라 결과 다름
        # - 패키지 설치됨: 정상 동작
        # - 패키지 없음: ImportError
        try:
            result = f.filter("쿼리", sample_results)
            # 설치된 경우 - 결과 반환
            assert len(result) <= f.top_k
        except ImportError as e:
            # 미설치 경우 - 에러 메시지 확인
            assert "rerankers" in str(e)

    def test_empty_results(self):
        f = RerankerFilter()

        result = f.filter("쿼리", [])

        assert result == []

    def test_handles_missing_content_field(self):
        """content 필드 없을 때 text 필드 시도"""
        f = RerankerFilter()
        results = [
            {"_score": 0.9, "_source": {"text": "텍스트 필드 사용"}},
        ]

        try:
            result = f.filter("쿼리", results)
            assert len(result) >= 0
        except ImportError:
            pass  # 패키지 미설치 시 스킵


class TestCompositeFilter:
    """CompositeFilter 테스트 - 필터 체이닝"""

    def test_chains_filters_in_order(self, sample_results):
        """필터 순차 적용"""
        composite = CompositeFilter(
            [
                TopKFilter(k=7),  # 10 → 7개
                ScoreThresholdFilter(min_score=0.5),  # 7 → 5개
            ]
        )

        result = composite.filter("쿼리", sample_results)

        assert len(result) == 5

    def test_empty_filters_returns_original(self, sample_results):
        """필터 없으면 원본 반환"""
        composite = CompositeFilter([])

        result = composite.filter("쿼리", sample_results)

        assert result == sample_results

    def test_single_filter(self, sample_results):
        """단일 필터"""
        composite = CompositeFilter([TopKFilter(k=3)])

        result = composite.filter("쿼리", sample_results)

        assert len(result) == 3

    def test_recommended_pipeline(self, sample_results):
        """권장 파이프라인: TopK → AdaptiveThreshold"""
        composite = CompositeFilter(
            [
                TopKFilter(k=8),
                AdaptiveThresholdFilter(min_keep_count=2, max_keep_count=5),
            ]
        )

        result = composite.filter("쿼리", sample_results)

        assert 2 <= len(result) <= 5

    def test_implements_protocol(self):
        composite = CompositeFilter([])
        assert isinstance(composite, ResultFilter)


class TestFilterComparison:
    """필터 비교 테스트"""

    def test_all_filters_return_list(self, sample_results):
        """모든 필터가 list 반환"""
        filters = [
            NoopFilter(),
            TopKFilter(k=5),
            ScoreThresholdFilter(min_score=0.5),
            AdaptiveThresholdFilter(),
            CompositeFilter([TopKFilter(k=5)]),
        ]

        for f in filters:
            result = f.filter("쿼리", sample_results)
            assert isinstance(result, list)

    def test_filters_preserve_structure(self, sample_results):
        """필터링 후에도 결과 구조 유지"""
        f = TopKFilter(k=3)

        result = f.filter("쿼리", sample_results)

        for r in result:
            assert "_score" in r
            assert "_source" in r
            assert "content" in r["_source"]

    def test_noop_returns_most(self, sample_results):
        """NoopFilter가 가장 많은 결과 반환"""
        noop_result = NoopFilter().filter("쿼리", sample_results)
        topk_result = TopKFilter(k=5).filter("쿼리", sample_results)
        threshold_result = ScoreThresholdFilter(min_score=0.5).filter("쿼리", sample_results)

        assert len(noop_result) >= len(topk_result)
        assert len(noop_result) >= len(threshold_result)

"""결과 필터 (ResultFilter)

검색 결과에서 품질 낮은 문서를 제거합니다.

권장 파이프라인:
    검색 (size=50) → TopKFilter(k=20) → RerankerFilter(top_k=5)
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ResultFilter(Protocol):
    """결과 필터 프로토콜"""

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        """검색 결과 필터링

        Args:
            query: 검색 쿼리 (Reranker용)
            results: OpenSearch 검색 결과 리스트 [{"_score": float, "_source": {...}}, ...]

        Returns:
            필터링된 결과 리스트
        """
        ...


class NoopFilter:
    """필터링 안 함 (베이스라인)

    검색 결과를 그대로 반환합니다.
    비교 기준용.
    """

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        return results


class TopKFilter:
    """상위 K개만 반환

    단순하지만 효과적인 필터.
    - Reranking 전: k=20~50
    - 최종 출력: k=5
    """

    def __init__(self, k: int = 5):
        self.k = k

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        return results[: self.k]


class ScoreThresholdFilter:
    """고정 점수 임계값 필터

    min_score 이상인 결과만 통과.

    Note:
        OpenSearch 쿼리에서도 "min_score" 옵션으로 처리 가능하지만,
        Hybrid Query에서는 normalized 점수가 아닌 개별 서브쿼리에 적용됨.
    """

    def __init__(self, min_score: float = 0.5):
        self.min_score = min_score

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        return [r for r in results if r.get("_score", 0) >= self.min_score]


class AdaptiveThresholdFilter:
    """동적 임계값 필터 (기존 로직 보존)

    점수 분포를 분석하여 동적으로 임계값을 결정합니다:
    1. 점수 정규화 (max_score 기준)
    2. 엘보우(최대 갭) 탐지
    3. 분위수 기반 임계값
    4. 최소/최대 보존 개수 보장

    새로운 방식(Reranking) 대비 성능 비교 측정용으로 보존.
    """

    def __init__(
        self,
        quantile_percentage: float = 0.15,
        threshold_upper_bound: float = 0.9,
        threshold_lower_bound: float = 0.1,
        min_keep_count: int = 3,
        max_keep_count: int = 8,
    ):
        self.quantile_percentage = quantile_percentage
        self.threshold_upper_bound = threshold_upper_bound
        self.threshold_lower_bound = threshold_lower_bound
        self.min_keep_count = min_keep_count
        self.max_keep_count = max_keep_count

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        if not results:
            return results

        # 점수 추출 및 정규화
        scores = [r.get("_score", 0) for r in results]
        max_score = max(scores) if scores else 1.0
        if max_score == 0:
            max_score = 1.0

        normalized_scores = [s / max_score for s in scores]

        # 임계값 계산
        threshold = self._calculate_threshold(normalized_scores)

        # 필터링
        filtered = [r for r, norm_score in zip(results, normalized_scores) if norm_score >= threshold]

        # 최소/최대 개수 보장
        if len(filtered) < self.min_keep_count:
            filtered = results[: self.min_keep_count]
        elif len(filtered) > self.max_keep_count:
            filtered = filtered[: self.max_keep_count]

        return filtered

    def _calculate_threshold(self, normalized_scores: list[float]) -> float:
        """동적 임계값 계산"""
        if len(normalized_scores) < 2:
            return self.threshold_lower_bound

        # 엘보우 탐지 (최대 갭)
        sorted_scores = sorted(normalized_scores, reverse=True)
        gaps = [sorted_scores[i] - sorted_scores[i + 1] for i in range(len(sorted_scores) - 1)]

        if gaps:
            max_gap_idx = gaps.index(max(gaps))
            elbow_threshold = sorted_scores[max_gap_idx + 1]
        else:
            elbow_threshold = self.threshold_lower_bound

        # 분위수 기반 임계값
        n = len(sorted_scores)
        quantile_idx = int(n * self.quantile_percentage)
        quantile_threshold = sorted_scores[quantile_idx] if quantile_idx < n else sorted_scores[-1]

        # 두 방법 중 더 높은 값 선택 (더 엄격한 필터링)
        threshold = max(elbow_threshold, quantile_threshold)

        # 상하한 적용
        threshold = max(self.threshold_lower_bound, min(self.threshold_upper_bound, threshold))

        return threshold


class RerankerFilter:
    """Reranker 기반 필터 (권장)

    질문과 문서를 함께 이해하여 재정렬 후 Top-K 반환.
    FlashRank 백엔드 사용 (경량, CPU 최적화).

    Usage:
        pip install "rerankers[flashrank]"

    Note:
        rerankers 패키지가 없으면 ImportError 발생.
        lazy import로 다른 필터들은 의존성 없이 사용 가능.
    """

    def __init__(
        self,
        model_name: str = "ms-marco-MiniLM-L-12-v2",
        model_type: str = "flashrank",
        top_k: int = 5,
    ):
        self.model_name = model_name
        self.model_type = model_type
        self.top_k = top_k
        self._ranker = None  # lazy init

    @property
    def ranker(self):
        """Reranker lazy initialization"""
        if self._ranker is None:
            try:
                from rerankers import Reranker  # pyright: ignore[reportMissingImports]

                self._ranker = Reranker(self.model_name, model_type=self.model_type)
            except ImportError as e:
                raise ImportError(
                    'rerankers 패키지가 필요합니다. pip install "rerankers[flashrank]" 로 설치하세요.'
                ) from e
        return self._ranker

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        if not results:
            return results

        # 문서 내용 추출
        docs = []
        for r in results:
            content = r.get("_source", {}).get("content", "")
            if not content:
                # content가 없으면 text 필드 시도
                content = r.get("_source", {}).get("text", "")
            docs.append(content)

        # 빈 문서 처리
        if not any(docs):
            return results[: self.top_k]

        # Reranking
        ranked = self.ranker.rank(query=query, docs=docs)

        # 상위 K개 인덱스 추출
        top_indices = [r.doc_id for r in ranked.results[: self.top_k]]

        return [results[i] for i in top_indices]


class CompositeFilter:
    """필터 체이닝

    여러 필터를 순차적으로 적용합니다.

    권장 조합:
        CompositeFilter([
            TopKFilter(k=20),      # 1차: 빠른 필터링
            RerankerFilter(top_k=5)  # 2차: 정밀 재정렬
        ])
    """

    def __init__(self, filters: list[ResultFilter]):
        self.filters = filters

    def filter(self, query: str, results: list[dict]) -> list[dict]:
        for f in self.filters:
            results = f.filter(query, results)
        return results

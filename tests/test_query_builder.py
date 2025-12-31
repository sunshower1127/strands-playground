"""QueryBuilder 테스트"""

import pytest

from src.rag.query_builder import (
    HybridQueryBuilder,
    KNNQueryBuilder,
    QueryBuilder,
)


# 테스트용 더미 임베딩
DUMMY_EMBEDDING = [0.1] * 1024


class TestKNNQueryBuilder:
    """KNNQueryBuilder 테스트"""

    def test_builds_knn_query(self):
        """KNN 쿼리 구조 확인"""
        builder = KNNQueryBuilder()

        result = builder.build(
            query="연차 휴가",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
            k=5,
        )

        assert "query" in result
        assert "knn" in result["query"]
        assert "embedding" in result["query"]["knn"]

    def test_includes_vector(self):
        """벡터가 포함되는지 확인"""
        builder = KNNQueryBuilder()

        result = builder.build(
            query="테스트",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
        )

        knn = result["query"]["knn"]["embedding"]
        assert knn["vector"] == DUMMY_EMBEDDING

    def test_includes_k_value(self):
        """k 값이 포함되는지 확인"""
        builder = KNNQueryBuilder()

        result = builder.build(
            query="테스트",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
            k=10,
        )

        knn = result["query"]["knn"]["embedding"]
        assert knn["k"] == 10

    def test_includes_project_filter(self):
        """project_id 필터가 포함되는지 확인"""
        builder = KNNQueryBuilder()

        result = builder.build(
            query="테스트",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
        )

        knn = result["query"]["knn"]["embedding"]
        assert knn["filter"] == {"term": {"project_id": 334}}

    def test_implements_protocol(self):
        """Protocol 구현 확인"""
        builder = KNNQueryBuilder()
        assert isinstance(builder, QueryBuilder)


class TestHybridQueryBuilder:
    """HybridQueryBuilder 테스트"""

    def test_builds_hybrid_query(self):
        """Hybrid 쿼리 구조 확인"""
        builder = HybridQueryBuilder()

        result = builder.build(
            query="연차 휴가",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
            k=5,
        )

        assert "query" in result
        assert "hybrid" in result["query"]
        assert "queries" in result["query"]["hybrid"]

    def test_has_two_subqueries(self):
        """BM25 + KNN 두 개의 서브쿼리 확인"""
        builder = HybridQueryBuilder()

        result = builder.build(
            query="테스트",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
        )

        queries = result["query"]["hybrid"]["queries"]
        assert len(queries) == 2

    def test_bm25_subquery_structure(self):
        """BM25 서브쿼리 구조 확인"""
        builder = HybridQueryBuilder()

        result = builder.build(
            query="연차 휴가",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
        )

        bm25 = result["query"]["hybrid"]["queries"][0]
        assert "bool" in bm25
        assert "must" in bm25["bool"]
        assert "filter" in bm25["bool"]

    def test_bm25_uses_multi_match(self):
        """BM25가 multi_match 사용하는지 확인"""
        builder = HybridQueryBuilder()

        result = builder.build(
            query="연차 휴가",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
        )

        bm25 = result["query"]["hybrid"]["queries"][0]
        must = bm25["bool"]["must"][0]
        assert "multi_match" in must
        assert must["multi_match"]["query"] == "연차 휴가"

    def test_bm25_search_fields(self):
        """BM25 검색 필드 확인"""
        builder = HybridQueryBuilder()

        result = builder.build(
            query="테스트",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
        )

        bm25 = result["query"]["hybrid"]["queries"][0]
        fields = bm25["bool"]["must"][0]["multi_match"]["fields"]

        assert "chunk_text^4.0" in fields
        assert "text.ko^3.5" in fields
        assert "text.en^1.8" in fields

    def test_knn_subquery_structure(self):
        """KNN 서브쿼리 구조 확인"""
        builder = HybridQueryBuilder()

        result = builder.build(
            query="테스트",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
        )

        knn = result["query"]["hybrid"]["queries"][1]
        assert "knn" in knn
        assert "embedding" in knn["knn"]

    def test_both_have_project_filter(self):
        """BM25와 KNN 모두 project_id 필터 확인"""
        builder = HybridQueryBuilder()

        result = builder.build(
            query="테스트",
            embedding=DUMMY_EMBEDDING,
            project_id=334,
        )

        bm25 = result["query"]["hybrid"]["queries"][0]
        knn = result["query"]["hybrid"]["queries"][1]

        # BM25 필터
        assert {"term": {"project_id": 334}} in bm25["bool"]["filter"]

        # KNN 필터
        assert knn["knn"]["embedding"]["filter"] == {"term": {"project_id": 334}}

    def test_search_pipeline_constant(self):
        """SEARCH_PIPELINE 상수 확인"""
        assert HybridQueryBuilder.SEARCH_PIPELINE == "hybrid-rrf"

    def test_implements_protocol(self):
        """Protocol 구현 확인"""
        builder = HybridQueryBuilder()
        assert isinstance(builder, QueryBuilder)


class TestQueryBuilderComparison:
    """QueryBuilder 비교 테스트"""

    def test_both_return_dict(self):
        """모든 빌더가 dict 반환"""
        knn = KNNQueryBuilder()
        hybrid = HybridQueryBuilder()

        knn_result = knn.build("테스트", DUMMY_EMBEDDING, 334)
        hybrid_result = hybrid.build("테스트", DUMMY_EMBEDDING, 334)

        assert isinstance(knn_result, dict)
        assert isinstance(hybrid_result, dict)

    def test_both_have_query_key(self):
        """모든 결과에 query 키 존재"""
        knn = KNNQueryBuilder()
        hybrid = HybridQueryBuilder()

        knn_result = knn.build("테스트", DUMMY_EMBEDDING, 334)
        hybrid_result = hybrid.build("테스트", DUMMY_EMBEDDING, 334)

        assert "query" in knn_result
        assert "query" in hybrid_result

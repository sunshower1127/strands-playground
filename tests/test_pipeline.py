"""RAG 파이프라인 테스트"""

import pytest
from unittest.mock import MagicMock, patch

from src.rag.pipeline import RAGPipeline, create_minimal_pipeline
from src.rag.types import RAGResult
from src.rag.query_builder import KNNQueryBuilder
from src.rag.context_builder import SimpleContextBuilder
from src.rag.prompt_template import SimplePromptTemplate
from src.rag.result_filter import TopKFilter
from src.rag.preprocessor import NoopPreprocessor
from src.llm_client import LLMResponse


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_search_client():
    """Mock OpenSearch 클라이언트"""
    client = MagicMock()
    client.search.return_value = [
        {
            "_id": "doc1",
            "_score": 0.95,
            "_source": {
                "text": "연차 휴가는 입사 1년차에 15일이 부여됩니다.",
                "file_name": "휴가정책.md",
                "page_number": 2,
                "project_id": 334,
                "document_id": 1,
                "chunk_index": 5,
            },
        },
        {
            "_id": "doc2",
            "_score": 0.85,
            "_source": {
                "text": "경조사 휴가는 결혼 5일, 사망 3일입니다.",
                "file_name": "복지제도.md",
                "page_number": 5,
                "project_id": 334,
                "document_id": 2,
                "chunk_index": 3,
            },
        },
    ]
    return client


@pytest.fixture
def mock_embedding_client():
    """Mock 임베딩 클라이언트"""
    client = MagicMock()
    client.embed.return_value = [0.1] * 1024  # 1024차원 더미 벡터
    return client


@pytest.fixture
def mock_llm_client():
    """Mock LLM 클라이언트"""
    client = MagicMock()
    client.call.return_value = LLMResponse(
        content="연차 휴가는 입사 1년차에 15일이 부여됩니다. [1]",
        input_tokens=150,
        output_tokens=30,
        model="claude-sonnet-4-5@20250929",
    )
    return client


@pytest.fixture
def pipeline(mock_search_client, mock_embedding_client, mock_llm_client):
    """테스트용 파이프라인"""
    return RAGPipeline(
        search_client=mock_search_client,
        embedding_client=mock_embedding_client,
        llm_client=mock_llm_client,
        query_builder=KNNQueryBuilder(),
        context_builder=SimpleContextBuilder(),
        prompt_template=SimplePromptTemplate(),
        index="test-index",
        project_id=334,
        search_size=5,
    )


# =============================================================================
# Unit Tests
# =============================================================================


class TestRAGResult:
    """RAGResult 테스트"""

    def test_basic_fields(self):
        result = RAGResult(
            question="테스트 질문",
            answer="테스트 답변",
            sources=[{"_id": "1"}],
            input_tokens=100,
            output_tokens=50,
            latency_ms=1234.5,
            model="test-model",
        )

        assert result.question == "테스트 질문"
        assert result.answer == "테스트 답변"
        assert result.source_count == 1
        assert result.total_tokens == 150
        assert result.latency_ms == 1234.5

    def test_empty_sources(self):
        result = RAGResult(question="q", answer="a")
        assert result.source_count == 0
        assert result.sources == []


class TestRAGPipeline:
    """RAGPipeline 테스트"""

    def test_query_returns_result(self, pipeline):
        """query()가 RAGResult를 반환하는지 확인"""
        result = pipeline.query("연차 휴가는 며칠인가요?")

        assert isinstance(result, RAGResult)
        assert result.question == "연차 휴가는 며칠인가요?"
        assert result.answer != ""
        assert result.source_count > 0
        assert result.latency_ms >= 0  # Mock 환경에서는 0.0일 수 있음

    def test_embedding_called(self, pipeline, mock_embedding_client):
        """임베딩 클라이언트가 호출되는지 확인"""
        pipeline.query("테스트 질문")

        mock_embedding_client.embed.assert_called_once_with("테스트 질문")

    def test_search_called(self, pipeline, mock_search_client):
        """검색 클라이언트가 호출되는지 확인"""
        pipeline.query("테스트 질문")

        mock_search_client.search.assert_called_once()
        call_args = mock_search_client.search.call_args
        assert call_args.kwargs["index"] == "test-index"
        assert call_args.kwargs["size"] == 5

    def test_llm_called_with_prompts(self, pipeline, mock_llm_client):
        """LLM이 올바른 프롬프트로 호출되는지 확인"""
        pipeline.query("연차 휴가는 며칠인가요?")

        mock_llm_client.call.assert_called_once()
        call_args = mock_llm_client.call.call_args

        # user prompt에 질문 포함
        assert "연차 휴가는 며칠인가요?" in call_args.args[0]
        # system prompt 존재
        assert call_args.kwargs["system"] is not None

    def test_with_preprocessor(self, mock_search_client, mock_embedding_client, mock_llm_client):
        """전처리기가 적용되는지 확인"""
        preprocessor = MagicMock()
        preprocessor.process.return_value = "전처리된 질문"

        pipeline = RAGPipeline(
            search_client=mock_search_client,
            embedding_client=mock_embedding_client,
            llm_client=mock_llm_client,
            query_builder=KNNQueryBuilder(),
            context_builder=SimpleContextBuilder(),
            prompt_template=SimplePromptTemplate(),
            preprocessor=preprocessor,
            index="test-index",
            project_id=334,
        )

        pipeline.query("원본 질문")

        preprocessor.process.assert_called_once_with("원본 질문")
        mock_embedding_client.embed.assert_called_once_with("전처리된 질문")

    def test_with_result_filter(self, mock_search_client, mock_embedding_client, mock_llm_client):
        """결과 필터가 적용되는지 확인"""
        pipeline = RAGPipeline(
            search_client=mock_search_client,
            embedding_client=mock_embedding_client,
            llm_client=mock_llm_client,
            query_builder=KNNQueryBuilder(),
            context_builder=SimpleContextBuilder(),
            prompt_template=SimplePromptTemplate(),
            result_filter=TopKFilter(k=1),
            index="test-index",
            project_id=334,
        )

        result = pipeline.query("테스트")

        # TopKFilter(k=1)이 적용되어 1개만 남아야 함
        assert result.source_count == 1

    def test_with_search_pipeline(self, mock_search_client, mock_embedding_client, mock_llm_client):
        """search_pipeline 파라미터가 전달되는지 확인"""
        mock_search_client.search_with_pipeline = MagicMock(return_value=[])

        pipeline = RAGPipeline(
            search_client=mock_search_client,
            embedding_client=mock_embedding_client,
            llm_client=mock_llm_client,
            query_builder=KNNQueryBuilder(),
            context_builder=SimpleContextBuilder(),
            prompt_template=SimplePromptTemplate(),
            index="test-index",
            project_id=334,
            search_pipeline="hybrid-rrf",
        )

        pipeline.query("테스트")

        mock_search_client.search_with_pipeline.assert_called_once()
        call_args = mock_search_client.search_with_pipeline.call_args
        assert call_args.kwargs["pipeline"] == "hybrid-rrf"


class TestFactoryFunctions:
    """팩토리 함수 테스트"""

    @patch("src.rag.pipeline.OpenSearchClient")
    @patch("src.rag.pipeline.EmbeddingClient")
    @patch("src.rag.pipeline.LLMClient")
    def test_create_minimal_pipeline(self, mock_llm, mock_embed, mock_search):
        """create_minimal_pipeline이 올바른 구성을 생성하는지 확인"""
        pipeline = create_minimal_pipeline(project_id=123, index="test-index")

        assert isinstance(pipeline, RAGPipeline)
        assert pipeline.project_id == 123
        assert pipeline.index == "test-index"
        assert pipeline.preprocessor is None
        assert pipeline.result_filter is None
        assert pipeline.chunk_expander is None
        assert pipeline.search_pipeline is None
        assert isinstance(pipeline.query_builder, KNNQueryBuilder)
        assert isinstance(pipeline.context_builder, SimpleContextBuilder)
        assert isinstance(pipeline.prompt_template, SimplePromptTemplate)

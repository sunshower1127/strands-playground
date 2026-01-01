"""OpenSearch 클라이언트 모듈"""

import os
import warnings

import urllib3
from dotenv import load_dotenv
from opensearchpy import OpenSearch, RequestsHttpConnection

# SSL 경고 숨기기 (터널 환경에서 정상)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message=".*verify_certs=False.*")


class OpenSearchClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9443,
        username: str | None = None,
        password: str | None = None,
    ):
        load_dotenv()

        self.host = host
        self.port = port
        self.username = username or os.getenv("OPENSEARCH_USERNAME")
        self.password = password or os.getenv("OPENSEARCH_PASSWORD")

        self.client = OpenSearch(
            hosts=[{"host": self.host, "port": self.port}],
            http_auth=(self.username, self.password),
            use_ssl=True,
            verify_certs=False,
            connection_class=RequestsHttpConnection,
        )

    def get_info(self) -> dict:
        """클러스터 정보 반환"""
        return self.client.info()

    def list_indices(self) -> list[dict]:
        """인덱스 목록 반환"""
        return self.client.cat.indices(format="json")  # type: ignore[call-arg]

    def search(self, index: str, query: dict, size: int = 5) -> list[dict]:
        """검색 수행"""
        response = self.client.search(
            index=index,
            body=query,
            size=size,  # type: ignore[call-arg]
        )
        return response["hits"]["hits"]

    def search_with_pipeline(
        self,
        index: str,
        query: dict,
        size: int = 5,
        pipeline: str = "hybrid-rrf",
    ) -> list[dict]:
        """검색 파이프라인 사용 검색 (하이브리드 RRF 등)"""
        response = self.client.search(
            index=index,
            body=query,
            size=size,  # type: ignore[call-arg]
            params={"search_pipeline": pipeline},
        )
        return response["hits"]["hits"]

    def get_sample_docs(self, index: str, size: int = 1) -> list[dict]:
        """샘플 문서 조회 (구조 파악용)"""
        response = self.client.search(
            index=index,
            body={"query": {"match_all": {}}},
            size=size,  # type: ignore[call-arg]
        )
        return response["hits"]["hits"]

    def get_index_mapping(self, index: str) -> dict:
        """인덱스 매핑 정보 (필드 구조 확인)"""
        return self.client.indices.get_mapping(index=index)

    def get_doc_count(self, index: str) -> int:
        """인덱스 문서 개수"""
        response = self.client.count(index=index)
        return response["count"]

    def get_doc_count_by_project(self, index: str, project_id: int) -> int:
        """project_id별 문서 개수"""
        query = {"query": {"term": {"project_id": project_id}}}
        response = self.client.count(index=index, body=query)
        return response["count"]

    def get_docs_by_project(self, index: str, project_id: int, size: int = 100) -> list[dict]:
        """project_id로 문서 조회"""
        query = {"query": {"term": {"project_id": project_id}}}
        response = self.client.search(index=index, body=query, size=size)  # type: ignore[call-arg]
        return response["hits"]["hits"]

    def get_all_docs_by_project(self, index: str, project_id: int) -> list[dict]:
        """project_id로 모든 문서 조회 (scroll API 사용)"""
        query = {"query": {"term": {"project_id": project_id}}}
        docs = []

        # 첫 번째 요청
        response = self.client.search(index=index, body=query, size=100, scroll="2m")  # type: ignore[call-arg]
        scroll_id = response["_scroll_id"]
        hits = response["hits"]["hits"]
        docs.extend(hits)

        # scroll로 나머지 가져오기
        while hits:
            response = self.client.scroll(scroll_id=scroll_id, scroll="2m")  # type: ignore[call-arg]
            scroll_id = response["_scroll_id"]
            hits = response["hits"]["hits"]
            docs.extend(hits)

        return docs

    def get_texts_by_project(self, index: str, project_id: int) -> list[str]:
        """project_id로 text 필드만 추출"""
        docs = self.get_all_docs_by_project(index, project_id)
        return [doc["_source"].get("text", "") for doc in docs if doc["_source"].get("text")]

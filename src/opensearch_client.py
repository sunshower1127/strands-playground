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
        return self.client.cat.indices(format="json")

    def search(self, index: str, query: dict, size: int = 5) -> list[dict]:
        """검색 수행"""
        response = self.client.search(
            index=index,
            body=query,
            size=size,
        )
        return response["hits"]["hits"]

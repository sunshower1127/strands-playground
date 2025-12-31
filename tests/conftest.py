"""pytest 공통 설정 및 fixtures"""

import sys
import warnings

import pytest
import urllib3

# src 경로 추가
sys.path.insert(0, "src")

# SSL 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message=".*verify_certs=False.*")


@pytest.fixture
def opensearch_client():
    """OpenSearch 클라이언트 fixture"""
    from opensearch_client import OpenSearchClient

    return OpenSearchClient()


@pytest.fixture
def test_index():
    """테스트용 인덱스 이름"""
    return "rag-index-fargate-live"

"""OpenSearch 연결 테스트 스크립트"""

import sys

sys.path.insert(0, "src")

from opensearch_client import OpenSearchClient


def test_connection():
    client = OpenSearchClient()

    print(f"Connecting to: {client.host}")

    # 클러스터 정보 확인
    info = client.get_info()
    print(f"✓ Connected! Cluster: {info['cluster_name']}, Version: {info['version']['number']}")

    # 인덱스 목록 확인
    indices = client.list_indices()
    print(f"✓ Indices count: {len(indices)}")
    for idx in indices[:5]:  # 최대 5개만 출력
        print(f"  - {idx['index']}")

    return True


if __name__ == "__main__":
    test_connection()

"""OpenSearch 클라이언트 테스트"""


class TestOpenSearchConnection:
    """연결 테스트"""

    def test_get_info(self, opensearch_client):
        """클러스터 정보 조회"""
        info = opensearch_client.get_info()
        assert "cluster_name" in info
        assert "version" in info

    def test_list_indices(self, opensearch_client):
        """인덱스 목록 조회"""
        indices = opensearch_client.list_indices()
        assert isinstance(indices, list)
        assert len(indices) > 0


class TestOpenSearchIndex:
    """인덱스 조회 테스트"""

    def test_get_doc_count(self, opensearch_client, test_index):
        """문서 개수 조회"""
        count = opensearch_client.get_doc_count(test_index)
        assert isinstance(count, int)
        assert count >= 0

    def test_get_sample_docs(self, opensearch_client, test_index):
        """샘플 문서 조회"""
        docs = opensearch_client.get_sample_docs(test_index, size=1)
        assert isinstance(docs, list)
        if docs:
            assert "_source" in docs[0]

    def test_get_index_mapping(self, opensearch_client, test_index):
        """인덱스 매핑 조회"""
        mapping = opensearch_client.get_index_mapping(test_index)
        assert test_index in mapping
        assert "mappings" in mapping[test_index]

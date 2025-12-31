"""OpenSearch CLI 도구

Usage:
    uv run python scripts/opensearch/cli.py <command> [options]

Commands:
    test                    연결 테스트
    explore [index]         인덱스 구조 탐색
    count <project_id>      프로젝트별 청크 개수
    collect <project_id>    텍스트 수집
    get-doc <document_id>   문서 조회
"""

import argparse
import json
import sys

sys.path.insert(0, "src")

from opensearch_client import OpenSearchClient

DEFAULT_INDEX = "rag-index-fargate-live"


def cmd_test(args):
    """연결 테스트"""
    client = OpenSearchClient()
    print(f"Connecting to: {client.host}")

    info = client.get_info()
    print(f"✓ Connected! Cluster: {info['cluster_name']}, Version: {info['version']['number']}")

    indices = client.list_indices()
    print(f"✓ Indices count: {len(indices)}")
    for idx in indices[:5]:
        print(f"  - {idx['index']}")


def cmd_explore(args):
    """인덱스 구조 탐색"""
    client = OpenSearchClient()
    index = args.index

    count = client.get_doc_count(index)
    print(f"📊 Index: {index}")
    print(f"   Documents: {count}")
    print()

    print("📋 Fields (mapping):")
    mapping = client.get_index_mapping(index)
    properties = mapping[index]["mappings"].get("properties", {})
    for field, info in properties.items():
        field_type = info.get("type", "object")
        print(f"   - {field}: {field_type}")
    print()

    print("📄 Sample document:")
    docs = client.get_sample_docs(index, size=1)
    if docs:
        doc = docs[0]["_source"]
        print("\n🏷️  Metadata values:")
        for key, value in doc.items():
            if isinstance(value, list) and len(value) > 10:
                print(f"   - {key}: [vector, dim={len(value)}]")
            elif isinstance(value, str) and len(value) > 200:
                print(f"   - {key}: {value[:200]}...")
            else:
                print(f"   - {key}: {value}")


def cmd_count(args):
    """프로젝트별 청크 개수"""
    client = OpenSearchClient()
    count = client.get_doc_count_by_project(args.index, args.project_id)
    print(f"project_id={args.project_id}: {count} chunks")


def cmd_collect(args):
    """텍스트 수집"""
    client = OpenSearchClient()
    project_id = args.project_id
    index = args.index

    print(f"📥 Collecting texts for project: {project_id}")
    print(f"   Index: {index}")

    docs = client.get_all_docs_by_project(index, project_id)
    print(f"   Found {len(docs)} chunks")

    if not docs:
        print("❌ No documents found")
        return

    texts = []
    for doc in docs:
        source = doc["_source"]
        texts.append({
            "id": doc["_id"],
            "text": source.get("text", ""),
            "metadata": {k: v for k, v in source.items() if k not in ["text", "embedding"]},
        })

    output_path = f"data/texts_{project_id}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(texts, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved to {output_path}")

    if texts:
        sample = texts[0]
        print(f"\n📄 Sample (first chunk):")
        print(f"   ID: {sample['id']}")
        print(f"   Text: {sample['text'][:200]}...")


def cmd_get_doc(args):
    """문서 조회"""
    client = OpenSearchClient()
    document_id = args.document_id
    index = args.index

    query = {"query": {"term": {"document_id": document_id}}}
    response = client.client.search(index=index, body=query, size=100)
    docs = response["hits"]["hits"]

    if not docs:
        print(f"❌ No chunks found for document_id={document_id}")
        return

    print(f"📄 Document ID: {document_id}")
    print(f"   Chunks: {len(docs)}")

    for i, doc in enumerate(docs):
        source = doc["_source"]
        print(f"\n--- Chunk {i + 1} ---")
        for key, value in source.items():
            if isinstance(value, list) and len(value) > 10:
                print(f"   - {key}: [vector, dim={len(value)}]")
            elif isinstance(value, str) and len(value) > 200:
                print(f"   - {key}: {value[:200]}...")
            else:
                print(f"   - {key}: {value}")


def main():
    parser = argparse.ArgumentParser(description="OpenSearch CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # test
    subparsers.add_parser("test", help="연결 테스트")

    # explore
    p_explore = subparsers.add_parser("explore", help="인덱스 구조 탐색")
    p_explore.add_argument("index", nargs="?", default=DEFAULT_INDEX, help="인덱스 이름")

    # count
    p_count = subparsers.add_parser("count", help="프로젝트별 청크 개수")
    p_count.add_argument("project_id", type=int, help="프로젝트 ID")
    p_count.add_argument("--index", default=DEFAULT_INDEX, help="인덱스 이름")

    # collect
    p_collect = subparsers.add_parser("collect", help="텍스트 수집")
    p_collect.add_argument("project_id", type=int, help="프로젝트 ID")
    p_collect.add_argument("--index", default=DEFAULT_INDEX, help="인덱스 이름")

    # get-doc
    p_get_doc = subparsers.add_parser("get-doc", help="문서 조회")
    p_get_doc.add_argument("document_id", type=int, help="문서 ID")
    p_get_doc.add_argument("--index", default=DEFAULT_INDEX, help="인덱스 이름")

    args = parser.parse_args()

    if args.command == "test":
        cmd_test(args)
    elif args.command == "explore":
        cmd_explore(args)
    elif args.command == "count":
        cmd_count(args)
    elif args.command == "collect":
        cmd_collect(args)
    elif args.command == "get-doc":
        cmd_get_doc(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

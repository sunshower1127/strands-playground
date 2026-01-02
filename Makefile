.PHONY: format lint tunnel dashboard test os chat install

# =============================================================================
# 설치
# =============================================================================

install:
	pip install -r requirements.txt

install-uv:
	uv sync

# =============================================================================
# CLI
# =============================================================================

# RAG Chat CLI (터널 연결 필요)
# 사용법: make chat ARGS="--project-id 334 --mode agent"
chat:
	python -m src.cli.main $(ARGS)

# =============================================================================
# 개발 도구
# =============================================================================

format:
	uv run ruff format .

lint:
	uv run ruff check .

test:
	uv run pytest -v

# =============================================================================
# 인프라
# =============================================================================

# OpenSearch 터널 (CLI 실행 전 필수)
tunnel:
	ssh -i ./credentials/temp-bastion-key.cer -L 9443:vpc-wissly-opensearch-v2-ugsta6nmff7vh2jw4fytpowfsa.ap-northeast-2.es.amazonaws.com:443 ec2-user@3.36.105.225

dashboard:
	start https://localhost:9443/_dashboards

# OpenSearch CLI: make os CMD="test" 또는 make os CMD="count 300"
os:
	uv run python scripts/opensearch/cli.py $(CMD)

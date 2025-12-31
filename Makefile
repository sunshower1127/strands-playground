.PHONY: format lint tunnel dashboard test os

tunnel:
	ssh -i ./temp-bastion-key.cer -L 9443:vpc-wissly-opensearch-v2-ugsta6nmff7vh2jw4fytpowfsa.ap-northeast-2.es.amazonaws.com:443 ec2-user@3.36.105.225

format:
	uv run ruff format .

lint:
	uv run ruff check .

dashboard:
	start https://localhost:9443/_dashboards

test:
	uv run pytest -v

# OpenSearch CLI: make os CMD="test" 또는 make os CMD="count 300"
os:
	uv run python scripts/opensearch/cli.py $(CMD)

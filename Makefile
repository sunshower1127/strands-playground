.PHONY: test-opensearch format lint tunnel dashboard

tunnel:
	ssh -i ./temp-bastion-key.cer -L 9443:vpc-wissly-opensearch-v2-ugsta6nmff7vh2jw4fytpowfsa.ap-northeast-2.es.amazonaws.com:443 ec2-user@3.36.105.225

test-opensearch:
	uv run python scripts/test_opensearch.py

format:
	uv run ruff format .

lint:
	uv run ruff check .

dashboard:
	start https://localhost:9443/_dashboards

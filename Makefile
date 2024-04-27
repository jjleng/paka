.PHONY: install test lint setup policy-pack type-check check-all e2e

install:
	poetry install

test:
	poetry run pytest tests

e2e:
	poetry run pytest --cluster-config e2e/test_cluster.yaml e2e

type-check:
	poetry run mypy paka tests

policy-pack:
	poetry run python -m paka.cli cluster preview -f $(shell pwd)/tests/policy_packs/aws/test_cluster.yaml --policy-pack $(shell pwd)/tests/policy_packs/aws

setup:
	poetry run pre-commit install

lint: setup
	poetry run pre-commit run --all-files --show-diff-on-failure

check-all: lint type-check test e2e

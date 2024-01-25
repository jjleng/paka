.PHONY: install test lint setup

install:
	poetry install

test:
	poetry run pytest && poetry run python -m light.cli cluster preview -f $(shell pwd)/tests/policy_packs/test_cluster.yaml --policy-pack $(shell pwd)/tests/policy_packs/aws

setup:
	poetry run pre-commit install

lint: setup
	poetry run pre-commit run --all-files --show-diff-on-failure

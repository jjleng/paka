.PHONY: install test lint setup

install:
	poetry install

test:
	poetry run pytest

setup:
	poetry run pre-commit install

lint: setup
	poetry run pre-commit run --all-files --show-diff-on-failure

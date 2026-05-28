# person_finder — developer task runner.
#
# All targets shell out to `uv run`, which auto-syncs the venv if stale.
# `test-eval` and `test-e2e` swallow pytest's exit code 5 ("no tests collected")
# so the harness stays green while those directories are empty in early epics.

.PHONY: help install sync test-unit test-eval test-e2e test-all

UV ?= uv
PYTEST = $(UV) run pytest

help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*##"; printf "Available targets:\n"} \
		/^[a-zA-Z0-9_-]+:.*?##/ { printf "  %-12s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: sync  ## Alias for `sync`.

sync:  ## Resolve and install dependencies via uv.
	$(UV) sync

test-unit:  ## Run unit tests (tests/unit/).
	$(PYTEST) tests/unit/

test-eval:  ## Run LLM eval tests (tests/eval/). Exit 5 ("no tests collected") is treated as success.
	$(PYTEST) tests/eval/ || [ $$? -eq 5 ]

test-e2e:  ## Run end-to-end tests (tests/e2e/). Exit 5 ("no tests collected") is treated as success.
	$(PYTEST) tests/e2e/ || [ $$? -eq 5 ]

test-all: test-unit test-eval test-e2e  ## Run all test tiers in order.

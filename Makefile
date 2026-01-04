config.json: secrets.cue config.cue configSchema.cue
	cue export > config.json

.PHONY: clean verify update-goldens

clean:
	rm -f config.json

verify:
	uv run ruff format --check
	cue fmt --check
	uv run ruff check
	uv run ty check
	uv run pytest

update-goldens:
	UPDATE_GOLDENS=1 uv run pytest tests/test_cli_golden.py

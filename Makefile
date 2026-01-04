config.json: secrets.cue config.cue configSchema.cue
	cue export > config.json

.PHONY: clean verify update-goldens

clean:
	rm -f config.json

verify:
	ruff format --check
	cue fmt --check
	ruff check
	uv tool run ty check
	uv run pytest

update-goldens:
	UPDATE_GOLDENS=1 uv run pytest tests/test_cli_golden.py

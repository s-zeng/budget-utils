config.json: secrets.cue config.cue configSchema.cue
	cue export > config.json

.PHONY: clean verify

clean:
	rm -f config.json

verify:
	ruff check
	ty check
	uv run pytest

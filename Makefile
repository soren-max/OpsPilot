.PHONY: demo

demo:
	@uv run --project backend --no-sync python -m app.demo

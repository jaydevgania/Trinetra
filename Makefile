.PHONY: run test bench lint format docker-build docker-run

run:
	python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

test:
	python -m pytest tests -v

bench:
	python -m bench.run_bench --scenario latency_storm --fail-under 80

docker-build:
	docker compose build

docker-up:
	docker compose up -d

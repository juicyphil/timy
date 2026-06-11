.PHONY: up down logs restart rebuild shell open

up:
	mkdir -p data
	docker compose up -d
	@echo "timy läuft unter http://localhost:8765"

down:
	docker compose down

logs:
	docker compose logs -f

restart: down up

rebuild:
	docker compose up -d --build

shell:
	docker compose exec timy sh

open:
	xdg-open http://localhost:8765

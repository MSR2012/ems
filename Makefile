.PHONY: up down logs test lint lint-frontend test-frontend e2e check-bundle test-all seed shell migrate ps

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

test:
	docker compose exec api pytest

lint:
	docker compose exec api ruff check .
	docker compose exec api lint-imports

test-frontend:
	docker compose exec frontend npm run test

e2e:
	docker compose up -d --wait
	docker compose --profile e2e run --rm --no-deps e2e

check-bundle:
	docker compose exec frontend sh -c "npx vite build --outDir /tmp/dist >/dev/null && ! grep -rlE 'access_token|refresh_token|gAAAAA|client_secret' /tmp/dist && echo 'bundle contains no token material'"

seed:
	docker compose exec api python manage.py seed_demo

migrate:
	docker compose exec api python manage.py migrate

shell:
	docker compose exec api python manage.py shell

lint-frontend:
	docker compose exec frontend npx eslint src tests
	docker compose exec frontend npx tsc -b --noEmit

test-all: lint test lint-frontend test-frontend e2e check-bundle

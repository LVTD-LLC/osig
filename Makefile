%:
	@:

serve:
	docker compose -f docker-compose-local.yml up -d --build
	docker compose -f docker-compose-local.yml logs -f backend

shell:
	docker compose -f docker-compose-local.yml run --rm backend uv run --no-sync python ./manage.py shell_plus --ipython

manage:
	docker compose -f docker-compose-local.yml run --rm backend uv run --no-sync python ./manage.py $(filter-out $@,$(MAKECMDGOALS))

makemigrations:
	docker compose -f docker-compose-local.yml run --rm backend uv run --no-sync python ./manage.py makemigrations

migrate:
	docker compose -f docker-compose-local.yml run --rm backend uv run --no-sync python ./manage.py migrate

test:
	docker compose -f docker-compose-local.yml run --rm backend uv run --no-sync pytest $(filter-out $@,$(MAKECMDGOALS))

mcp-list:
	sh scripts/mcp-dev list

mcp-call:
	sh scripts/mcp-dev call $(TOOL) $(ARGS)

mcp-inspect:
	sh scripts/mcp-dev inspect $(ARGS)

mcp-http:
	sh scripts/mcp-dev http

mcp-migrate:
	sh scripts/mcp-dev migrate $(ARGS)

mcp-test:
	sh scripts/mcp-dev test $(ARGS)

test-webhook:
	docker compose -f docker-compose-local.yml run --rm stripe trigger customer.subscription.created

stripe-sync:
	docker compose -f docker-compose-local.yml run --rm backend uv run --no-sync python ./manage.py djstripe_sync_models

restart-worker:
	docker compose -f docker-compose-local.yml up -d workers --force-recreate

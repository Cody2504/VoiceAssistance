.PHONY: build up down restart local-build local-up local-down db-up db-down remove logs ps

# -------- Production-ish (CPU/GPU local with full stack) --------
build:
	docker compose --env-file .env build

up:
	docker compose --env-file .env up

down:
	docker compose --env-file .env down

restart:
	docker compose --env-file .env restart

# -------- Dev (mounted code, lower limits) --------
local-build:
	docker compose --env-file .env -f docker-compose.yml -f docker-compose.local.yml build

local-up:
	docker compose --env-file .env -f docker-compose.yml -f docker-compose.local.yml up

local-down:
	docker compose --env-file .env -f docker-compose.yml -f docker-compose.local.yml down

# -------- GPU override --------
gpu-up:
	docker compose --env-file .env -f docker-compose.yml -f docker-compose.gpu.yml up

# -------- Just the databases / object store --------
db-up:
	docker compose --env-file .env -f database/docker-compose.yml up -d

db-down:
	docker compose --env-file .env -f database/docker-compose.yml down

# -------- Utilities --------
remove:
	docker compose --env-file .env down --rmi all -v

logs:
	docker compose --env-file .env logs -f --tail=200

ps:
	docker compose --env-file .env ps

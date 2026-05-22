.PHONY: base-build build up down restart local-build local-up local-down gpu-up db-up db-down remove logs ps

# ---------------------------------------------------------------------------
# Service Dockerfiles `FROM jockey-base:dev` — the base image is built and kept
# **locally only**. Run `make base-build` once after cloning (and again whenever
# base_image/{Dockerfile,requirements.txt,build-constraints.txt} change), then
# `docker compose build && docker compose up` for everything else.
# ---------------------------------------------------------------------------

BASE_IMAGE ?= jockey-base
BASE_TAG   ?= dev

# Build the base image locally (only when base_image/{Dockerfile,requirements.txt,build-constraints.txt} change).
base-build:
	DOCKER_BUILDKIT=1 docker build -t $(BASE_IMAGE):$(BASE_TAG) ./base_image

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

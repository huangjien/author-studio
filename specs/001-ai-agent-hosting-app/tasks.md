---
description: "Actionable, dependency-ordered task list for the AI Agent Hosting Application feature"
---

# Tasks: AI Agent Hosting Application

**Input**: Design documents from `/Users/huangjien/workspace/author-studio/specs/001-ai-agent-hosting-app/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/openapi.yaml, quickstart.md

Tests: Per the project constitution and prompt requirements, tests are required. Write tests FIRST and ensure they FAIL before implementation.

**Organization**: Tasks are grouped by user story (US1–US4) in priority order to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions (Single-project per plan.md)
- Source: `src/`
  - `src/api/` (FastAPI endpoints)
  - `src/agents/` (agent loading & registry)
  - `src/config/` (config loading & validation)
  - `src/services/` (business logic: caching, logging, persistence)
  - `src/core/` (core models & utilities)
  - `src/main.py` (entrypoint)
- Tests: `tests/contract/`, `tests/integration/`, `tests/unit/`
- Agent configs: `agent_configs/`
- Dockerfile, requirements.txt at repo root

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create project structure per plan.md: `src/api/`, `src/agents/`, `src/config/`, `src/services/`, `src/core/`, `src/main.py`, `tests/{contract,integration,unit}/`, `agent_configs/`, `Dockerfile`, `requirements.txt`
- [X] T002 Initialize Python 3.14 project dependencies in `requirements.txt` (FastAPI, uvicorn, httpx, PyYAML, pydantic, pytest, black, isort, flake8, sqlite3/aiosqlite, cachetools)
- [X] T003 [P] Configure formatting/linting in `pyproject.toml` (black, isort, flake8 rules) and add `pre-commit` config
- [X] T004 [P] Create base `.gitignore` and `.dockerignore` at repo root aligned with Python & Docker best practices

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: Must complete before any user story work

- [X] T005 Setup FastAPI app skeleton in `src/main.py` (create app, include routers placeholder, JSON error handling)
- [X] T006 [P] Implement API key security dependency in `src/api/security.py` (header `X-API-Key`, env backed)
- [X] T007 [P] Configure logging in `src/services/logging.py` and initialize in `src/main.py`
- [X] T008 [P] Implement environment/config management in `src/config/env.py` (API key, agent config dir, persistence mode)
- [X] T009 [P] Create AgentConfig model `src/core/models/agent_config.py`
- [X] T010 [P] Create Agent model `src/core/models/agent.py`
- [X] T011 [P] Create basic caching & persistence harness:
  - `src/services/cache.py` (LRU/memoization hooks)
  - `src/services/persistence.py` (interfaces for local file & SQLite)

**Checkpoint**: Foundation ready → User stories can now begin in parallel

---

## Phase 3: User Story 1 - Agent Configuration (Priority: P1) 🎯 MVP

**Goal**: Define and manage multiple agent configurations via YAML; agents load on startup without code changes.
**Independent Test**: Creating/editing a YAML file in `agent_configs/` loads/updates the agent on app restart.

### Tests for User Story 1 ⚠️ (write first)
- [X] T012 [P] [US1] Integration test: load valid config on startup in `tests/integration/test_agent_loading.py`
- [X] T013 [P] [US1] Integration test: invalid YAML logs error and skips agent in `tests/integration/test_agent_config_error.py`

### Implementation for User Story 1
- [X] T014 [P] [US1] JSON Schema for agent config at `src/config/schema/agent_config.schema.json`
- [X] T015 [P] [US1] Config validator `src/config/validator.py` (validate YAML against schema)
- [X] T016 [P] [US1] YAML loader `src/config/loader.py` (read `agent_configs/*.yaml`, merge, return AgentConfig instances)
- [X] T017 [US1] Agent registry `src/agents/registry.py` (load, index by `agent_id`, reload on restart)
- [X] T018 [US1] Agent initialization `src/agents/loader.py` (construct Agent from AgentConfig; bind LLM/tooling per config)
- [X] T019 [US1] Logging for agent load/update in `src/agents/registry.py`

**Checkpoint**: US1 independently testable → adding a new YAML should expose agent via API upon app restart

---

## Phase 4: User Story 2 - Agent Interaction via API (Priority: P1)

**Goal**: Interact with a specific agent via REST; return valid structured responses.
**Independent Test**: POST `/agents/{agent_id}/invoke` returns agent output; unknown agent → 404.

### Tests for User Story 2 ⚠️ (write first)
- [X] T020 [P] [US2] Contract test for `POST /agents/{agent_id}/invoke` in `tests/contract/test_invoke_endpoint.py` (200, 404, 500)
- [X] T021 [P] [US2] Integration test: end-to-end invoke flow in `tests/integration/test_agent_invoke_flow.py`

### Implementation for User Story 2
- [X] T022 [P] [US2] Session model `src/core/models/session.py`
- [X] T023 [US2] SessionService `src/services/session_service.py` (create/continue sessions)
- [X] T024 [US2] AgentService.invoke `src/services/agent_service.py` (lookup agent, run workflow, return output)
- [X] T025 [US2] API router `src/api/routes/agents.py` (implement POST `/agents/{agent_id}/invoke`; depends on T022, T023)
- [X] T026 [US2] Wire router in `src/main.py` and ensure ApiKey dependency is enforced
- [X] T027 [US2] Error handling in `src/api/routes/agents.py` (404 unknown agent; 500 internal)
- [X] T028 [US2] Request/response logging in `src/api/routes/agents.py`

**Checkpoint**: US1 & US2 both independently functional

---

## Phase 5: User Story 3 - Dockerized Deployment (Priority: P2)

**Goal**: Build and run the app in Docker; container serves agent API requests.
**Independent Test**: `docker build` creates image; `docker run` starts app and responds to API.

### Tests for User Story 3 ⚠️ (write first)
- [X] T029 [P] [US3] Script/test: Docker build succeeds `tests/integration/test_docker_build.py`
- [X] T030 [P] [US3] Script/test: Run container and hit API `tests/integration/test_docker_run.py`

### Implementation for User Story 3
- [X] T031 [US3] Create `Dockerfile` at repo root (Python 3.14, uvicorn, mount `agent_configs/`)
- [X] T032 [US3] Create `.dockerignore` at repo root
- [X] T033 [US3] Add container entrypoint (uvicorn) and environment wiring in `Dockerfile`
- [X] T034 [US3] Document container usage in `quickstart.md` (verify paths & `host.docker.internal` note)

**Checkpoint**: Containerized app builds and serves API

---

## Phase 6: User Story 4 - Internationalization (Priority: P3)

**Goal**: Respect `Accept-Language` header; agent/system messages localized.
**Independent Test**: Request with `Accept-Language: es` returns Spanish; unsupported → English fallback.

### Tests for User Story 4 ⚠️ (write first)
- [X] T035 [P] [US4] Integration test: language header selection `tests/integration/test_i18n.py`

### Implementation for User Story 4
- [X] T036 [P] [US4] i18n utility `src/core/i18n.py` (select localized prompt/messages from AgentConfig)
- [X] T037 [US4] Update invoke router to honor language in `src/api/routes/agents.py` (fallback to `en`)

**Checkpoint**: i18n behavior verified by tests

---

## Phase N: Polish & Cross-Cutting Concerns

- [X] T038 [P] Documentation updates in `docs/` and `specs/001-ai-agent-hosting-app/quickstart.md`
- [X] T039 Code cleanup and refactoring across `src/`
- [X] T040 Performance optimization (caching strategies) in `src/services/cache.py`
- [X] T041 [P] Additional unit tests in `tests/unit/` (validator, loader, registry, services)
- [ ] T042 Security hardening (API key rotation, input validation) across `src/api/` and `src/services/`
- [X] T043 Run quickstart.md validation steps to ensure instructions succeed

---

## Dependencies & Execution Order

### Phase Dependencies
- Setup (Phase 1): No dependencies
- Foundational (Phase 2): Depends on Setup completion – BLOCKS all user stories
- User Stories (Phase 3+): Each depends on Foundational; proceed by priority (P1 → P2 → P3)
- Polish: Depends on target stories completion

### Within Stories
- Tests MUST be written and fail before implementation
- Models → Services → Endpoints → Integration
- Different files = [P] parallel; Same file = sequential

### Key Task Dependencies
- T005 → T006–T011
- T014 → T015 → T016 → T017–T019
- T022 → T023 → T024 → T025–T028
- T029 → T030 depends on successful build (T031–T034)

---

## Parallel Execution Examples

### User Story 1
- Launch tests in parallel:
  - Task: "T012 Integration test: load valid config on startup"
  - Task: "T013 Integration test: invalid YAML logs error and skips agent"
- Launch model/validator tasks in parallel:
  - Task: "T014 JSON Schema for agent config"
  - Task: "T015 Config validator"
  - Task: "T016 YAML loader"

Example commands:
- `pytest -q tests/integration/test_agent_loading.py tests/integration/test_agent_config_error.py`

### User Story 2
- Launch tests in parallel:
  - Task: "T020 Contract test for POST /agents/{agent_id}/invoke"
  - Task: "T021 Integration test: end-to-end invoke flow"

Example commands:
- `pytest -q tests/contract/test_invoke_endpoint.py tests/integration/test_agent_invoke_flow.py`

### Docker (US3)
- `make docker-build`
- `make docker-run PORT=8000`

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1 – Agent Configuration
4. Stop and validate US1 independently, then proceed

### Incremental Delivery
1. Setup + Foundational → Foundation ready
2. Add US1 → Test independently → Demo
3. Add US2 → Test independently → Demo
4. Add US3 → Test independently → Demo
5. Add US4 → Test independently → Demo

### Parallel Team Strategy
1. Team completes Setup + Foundational
2. After Foundational:
   - Developer A: US1
   - Developer B: US2
   - Developer C: US3/US4

---

## Summary
- Feature: AI Agent Hosting Application
- Contracts: `POST /agents/{agent_id}/invoke` (OpenAPI v3) → Contract test in T020
- Entities: Agent, AgentConfig, Session/Conversation → Models in T009, T022
- Parallel opportunities: T003–T004 (Setup), T006–T011 (Foundational), T012–T016 (US1), T020–T021 (US2), T029–T030 (US3), T035–T036 (US4)
- MVP Scope: US1 only
- Format validation: All tasks use `- [ ] TXXX [P?] [US?] Description with file path`

---

## Optional Add-on: AutoGen Integration (Safe, Non-Blocking)

The following tasks add a minimal, optional integration with the Microsoft AutoGen library. These do NOT alter existing tested flows and will be skipped if AutoGen is not installed in the environment.

- [X] T100 [P] Add optional AutoGen adapter: `src/agents/autogen_adapter.py` (lazy import, single-turn chat)
- [X] T101 [P] Demo script: `scripts/run_autogen_demo.py` (standalone; prints result or helpful error)
- [X] T102 [P] Documentation: Add a "Using AutoGen" section to `README.md` (install, env vars, demo command)
- [X] T103 [P] Unit tests: `tests/unit/test_autogen_adapter.py` (skip if AutoGen not installed; assert graceful behavior)
- [ ] T104 [P] Extend adapter: support system prompts and simple group chat (Assistant + UserProxy + GroupChatManager)
- [X] T105 [P] Config mapping: allow `agent_configs/*.yaml` to opt-in with `workflow.type: autogen` (ignored by default)
- [ ] T106 [P] (Removed) Endpoint prototype for optional `/autogen/{agent_id}/invoke` — route removed; use canonical `/agents/{agent_id}/invoke`.

Execution notes:
- No dependency changes required for core app/tests.
- AutoGen usage is isolated; if `autogen` is missing, tests and the app remain unaffected.
- Start with T100–T103 (already completed here), then proceed with docs and opt-in endpoints if desired.

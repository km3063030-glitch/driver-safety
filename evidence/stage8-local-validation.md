# Stage 8 Local Validation

Date: 2026-10-01
Environment: Windows, Python 3.14.7, Docker Compose local stack

## Verified

- `python -m pytest -q --cov-fail-under=80`: 79 passed; 89.19% backend statement coverage.
- `python -m ruff check .`: passed.
- `npm audit --audit-level=high`: zero vulnerabilities.
- `npm run build`: Vite production build passed.
- `docker compose config --quiet`: passed; Postgres, Redis, ClickHouse, Redpanda, and Mongo containers were running.
- Live API login and fleet leaderboard succeeded. Browser login, overview, vehicle detail, and similar-vehicle results rendered. At a 390px viewport, document width was 375px (no horizontal overflow).
- Gemini agent returned a tool-grounded fleet answer; an out-of-fleet VIN was denied, and an unrelated poem request was declined. The first live request produced `question`, `tool_call`, and `answer` audit records.
- Unit tests cover rate limiting, audit fail-closed behavior, fleet isolation, location masking, ClickHouse flush/offset ordering, and idempotent DLQ persistence.
- `.env` is ignored by Git and is not tracked. Do not commit or publish it.

## Not Yet Measured

- 100K events/sec for five minutes, the 3x burst, and the one-hour soak were not run. Use `load_tests/README.md` from a same-VPC EC2 load generator; producer acknowledgements alone do not prove consumer throughput or zero loss.
- Broker restart/chaos behavior was not run against this local stack. The single-node Redpanda Compose service cannot demonstrate high availability.
- Semgrep, Trivy, and ZAP workflows were added but have not yet run in GitHub Actions. ZAP is manual and requires a disposable deployed target URL.
- No AWS deployment, p95/p99 latency results, or cloud recovery proof is included here.

## Warnings

The test suite emits two third-party deprecation warnings (google-genai/Python 3.14 typing alias and Starlette TestClient/httpx). They do not fail tests. CI currently uses Python 3.12; that hosted CI run remains to be observed.

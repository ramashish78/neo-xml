# Neo XML backend

REST API for the Neo XML authoring flow: login, data modules, graphics, validation, review, and publishing.

If you have built Java REST services, the mapping is:

| Java | This project |
| --- | --- |
| `@RestController` | `app/api/v1` routers |
| DTO + `@Valid` | `app/schemas/dto.py` |
| `@Service` | `app/services` |
| Spring Data repository | `app/repositories` |
| Security filter | `Depends(require("dm.update"))` in `app/core/deps.py` |
| `application.yml` | `.env` via `app/core/config.py` |

Routers do not query MongoDB. Repositories do not check permissions.

## Run with Docker

```bash
docker compose up --build
```

API: `http://127.0.0.1:8017`  
Swagger: `http://127.0.0.1:8017/docs`  
Health: `http://127.0.0.1:8017/health`

## Run locally

Requirements: Python 3.12 and MongoDB.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8017
```

The app refuses to start if `MONGODB_URI` or `JWT_SECRET` is missing. `JWT_SECRET` must be at least 16 characters.

Seeded login (change this outside your laptop):

- email: `admin@neo-xml.local`
- password: `ChangeMe123!`

## Tests

```bash
pytest
```

Tests use an in-memory MongoDB. They do not need a running database.

## What the API covers

- JWT login, refresh, logout, `/auth/me`, change password
- Roles from the permission matrix, users, workspaces
- File upload and download under `var/uploads` (UUID names, checksum, no public folder)
- Data modules, DMC, revisions. Approved and published revisions are not overwritten
- Graphics / ICN upload, revision, and reuse on a data module
- XSD, BREX, CALS, applicability, STE, and reference checks
- Review tasks, comments, track changes, accept/reject, approval, audit log
- CSDB counts, publication modules, DMRL, DDN
- Web, PDF, and IETP transformation jobs

`GET /ready` checks MongoDB. Put Nginx in front for HTTPS in production. Do not expose MongoDB publicly.

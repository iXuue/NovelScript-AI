# NovelScript AI Code

This directory contains the runnable application code for NovelScript AI.

## Directory Layout

- `backend/`: FastAPI backend, SQLAlchemy models, Alembic migrations, services, API routes, and backend tests.
- `frontend/`: React + TypeScript + Vite frontend.
- `test/`: acceptance notes and end-to-end test entry points.
- `docker-compose.yml`: local PostgreSQL, backend, frontend, and test orchestration.

## One-Command Docker Setup

Recommended for normal development and validation:

```bash
docker compose up --build
```

Then open:

- Frontend: `http://localhost:5173`
- Backend health check: `http://localhost:8000/health`

The backend Docker image installs the document conversion runtime automatically:

- `libreoffice-writer`: converts legacy `.doc` uploads and generates `.doc` / `.pdf` exports.
- `fonts-noto-cjk`: provides CJK fonts for generated PDFs.
- `fontconfig`: makes installed fonts discoverable to LibreOffice.

No manual LibreOffice setup is required when using Docker.

## Local Development Without Docker

Use Docker unless you specifically need to run services directly on your machine. Local mode requires PostgreSQL and LibreOffice to be installed separately.

Backend:

```bash
cd code/backend
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd code/frontend
npm install
npm run dev
```

Common backend environment variables:

```bash
DATABASE_URL=postgresql+psycopg://novelscript:novelscript@localhost:5433/novelscript
STORAGE_ROOT=./storage
SOFFICE_BINARY=soffice
DOCUMENT_CONVERSION_TIMEOUT_SECONDS=60
```

If LibreOffice is not on `PATH`, set `SOFFICE_BINARY` to the full path of the `soffice` executable.

## Tests

Docker backend tests:

```bash
docker compose --profile test run --rm backend-test
```

Docker frontend tests:

```bash
docker compose --profile test run --rm frontend-test
```

Docker frontend production build:

```bash
docker compose --profile test run --rm frontend-build
```

Local backend tests:

```bash
cd code/backend
pytest tests -q
```

Local frontend tests:

```bash
cd code/frontend
npm test
npm run build
```

## File Support

Uploads:

- Novel uploads: `.md`, `.txt`, `.doc`, `.docx`, `.pdf`
- Style reference uploads: `.md`, `.txt`, `.doc`, `.docx`, `.pdf`

Exports:

- `yaml`
- `markdown`
- `txt`
- `clean_json`
- `docx`
- `doc`
- `pdf`

`docx`, `doc`, and `pdf` are generated as readable script documents with Chinese labels. Dialogue blocks use `speaker: line` style rendered with the Chinese colon, for example `林雨：我回来了。`; non-dialogue blocks use `type: text`, for example `动作：她推开门。`. `yaml`, `markdown`, `txt`, and `clean_json` keep the structured text export format.

PDF upload extracts embedded text. Scanned image-only PDFs may not contain usable text unless OCR is performed before upload.

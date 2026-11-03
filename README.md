# Printer of A's

A lightweight, dark-themed PDF print-kiosk application. Upload one or more PDFs, review the job and price, then send it to a queue that a Raspberry Pi print worker can process.

## Features

- Upload and merge one or more PDF documents into one print job
- Preview the selected document before confirming
- Select black-and-white or colour printing, copies, and duplex mode
- Calculate pricing automatically
- Track queued, printing, completed, and failed jobs
- Provide a small authenticated API for a Raspberry Pi print worker

## Requirements

- Python 3.9 or later
- `pip`

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PI_TOKEN="replace-with-a-secret" .venv/bin/python app.py
```

Open [http://localhost:5001](http://localhost:5001).

The app stores queued PDFs in `uploads/` and job data in `jobs.db`. Both are created automatically and intentionally ignored by Git.

## Deploying to Vercel

Vercel automatically detects this project as a Flask application because it exposes `app` from `app.py` and lists its dependencies in `requirements.txt`; no custom start command or `vercel.json` is required.

Add `PI_TOKEN` as an environment variable in **Vercel → Project Settings → Environment Variables**, then redeploy. The application automatically writes temporary runtime files to Vercel's writable `/tmp` directory instead of the read-only deployment directory.

> `/tmp` is temporary and is not shared between all function instances. It is enough to run the demo without a startup error, but it is not suitable for a real print queue: uploaded PDFs and job records can disappear or be unavailable to another function instance. For a production deployment, use durable object storage for PDFs and a hosted database for jobs.

## Print workflow

1. Upload one or more PDFs. Multiple files are merged into one job.
2. Preview the document and set its colour mode, copy count, and duplex preference.
3. Confirm the simulated payment to place the job in the queue.
4. A worker polls the API, downloads the queued PDF, sends it to the printer, and reports the final status.

### Limits and pricing

| Setting | Value |
| --- | --- |
| Maximum upload size | 50 MB |
| Maximum combined pages | 100 |
| Copies | 1–20 |
| Black & white | ₹2/page |
| Colour | ₹8/page |

## Raspberry Pi worker API

Set `PI_TOKEN` to a strong shared secret in both the web app and worker. Every worker request must include:

```http
Authorization: Bearer <PI_TOKEN>
```

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/next-job` | Fetches and marks the oldest queued job as `printing` |
| `GET` | `/api/job/<job_id>/file` | Downloads the PDF for a job |
| `POST` | `/api/job/<job_id>/status` | Marks a job as `done` or `failed` |

The status endpoint accepts JSON such as:

```json
{ "status": "done" }
```

> The default `PI_TOKEN` value is only suitable for local development. Always set a secret value before connecting a real worker or exposing the service on a network.

## Project structure

```text
.
├── app.py             # Flask application, UI, queue, and worker API
├── requirements.txt   # Python dependencies
├── uploads/           # Runtime PDF storage (ignored by Git)
└── jobs.db            # Runtime SQLite database (ignored by Git)
```

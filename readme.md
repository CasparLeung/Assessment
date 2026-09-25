# Identifier Processing Service

A backend REST API service built with FastAPI and MySQL that accepts a pair of identifiers (`id1`, `id2`), checks for existing mappings, and deterministically returns or generates an idempotent UUID v4 `userID`.

---

## Project Overview

This service implements a persistent identifier mapping workflow designed to guarantee consistency and idempotency across requests:
- Accepts a JSON payload containing two required parameters: `id1` and `id2`.
- Queries MySQL to determine if a record with the exact `(id1, id2)` combination already exists.
- If found, retrieves and returns the existing `userID`.
- If not found, generates a new UUID v4 `userID`, persists the record to MySQL, and returns the generated `userID`.
- Concurrency race conditions are safely resolved at the database level via a composite unique constraint and transaction rollback mechanism.

---

## Prerequisites

Ensure the following tools are installed on the host system:
- **Python**: Version 3.10 or higher
- **MySQL Server**: Version 8.0 or higher
- **Git**

---

## Installation Instructions

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd assessment
   ```

2. **Create and activate an isolated virtual environment:**
     ```cmd
     python -m venv venv
     venv\Scripts\activate
     ```

3. **Install the required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## Environment / Configuration Instructions

All sensitive credentials and database connection parameters are decoupled from the codebase using `python-dotenv` and loaded via `os.getenv`.

1. Create a local `.env` configuration file from the provided template:
     ```cmd
     copy .env.example .env
     ```

2. Open `.env` and provide your local MySQL credentials:
   ```env
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_HOST=127.0.0.1
   DB_PORT=3306
   DB_NAME=assessment_db
   ```

---

## Database Setup Instructions

The application requires the target schema and table to exist before handling traffic.

1. Open your terminal or MySQL command line and apply the initialization file:
   ```bash
   $mysqlPath = (Get-ChildItem -Path "C:\Program Files\MySQL" -Filter mysql.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName)
Get-Content Assessment-schema.sql | & $mysqlPath -u root -p
   ```

2. The schema creates the database and provisions the table with a composite unique key:
   ```sql
   CREATE DATABASE IF NOT EXISTS `assessment_db`
     DEFAULT CHARACTER SET utf8mb4
     COLLATE utf8mb4_unicode_ci;

   USE `assessment_db`;

   CREATE TABLE IF NOT EXISTS `assessment` (
     `userID` char(36) NOT NULL,
     `id1` varchar(255) NOT NULL,
     `id2` varchar(255) NOT NULL,
     PRIMARY KEY (`userID`),
     UNIQUE KEY `uq_id1_id2` (`id1`, `id2`)
   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
   ```

---

## Instructions for Starting the Application

1. Launch the ASGI server using Uvicorn:

```bash
.\venv\Scripts\uvicorn.exe API:app --host 127.0.0.1 --port 8000 --reload
```
2. Access Application Interfaces & Documentation

- **Base URL:** `http://127.0.0.1:8000`
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`
- **Alternative ReDoc:** `http://127.0.0.1:8000/redoc`

---

## API Endpoint and Example Request

### Endpoint Definition
- **Route:** `POST /process-identifiers`
- **Content-Type:** `application/json`

### Example Request Body
```json
{
  "id1": "ABC123",
  "id2": "XYZ456"
}
```

### Response Statuses

- **`200 OK` (Success)**:
  ```json
  {
    "userID": "550e8400-e29b-41d4-a716-446655440000"
  }
  ```

- **`400 Bad Request` (Whitespace Only Input)**:
  ```json
  {
    "status_code": 400,
    "error": "Client Error",
    "detail": "Fields 'id1' and 'id2' must not be blank whitespace."
  }
  ```

- **`422 Unprocessable Entity` (Missing / Invalid Fields)**:
  ```json
  {
    "status_code": 422,
    "error": "Unprocessable Entity",
    "detail": [
      "Field 'id2': Field required"
    ]
  }
  ```

- **`500 Internal Server Error` (Database Failure)**:
  ```json
  {
    "status_code": 500,
    "error": "Internal Database Error",
    "detail": "An unexpected database error occurred. Please try again later."
  }
  ```

---

## Instructions for Running Tests

An integrated end-to-end self-test suite using Starlette's `TestClient` is embedded directly inside `API.py`. It sends consecutive payloads to verify both initial record generation and deterministic retrieval on repeated calls.

Execute the test directly:
```bash
python API.py
```

Expected terminal verification output:
```text
--- 1. First Request ---
Status: 200
Response: {'userID': '<generated-uuid-v4>'}

--- 2. Second Request (Identical Payload) ---
Status: 200
Response: {'userID': '<generated-uuid-v4>'}

SUCCESS: Both calls returned the same userID.
```

---

## Assumptions & Important Technical Decisions

1. **Database-Level Concurrency Protection (`uq_id1_id2`):**
   - Relying solely on `SELECT` queries before `INSERT` introduces race conditions when identical requests arrive concurrently.
   - The database enforces a composite `UNIQUE KEY (id1, id2)`.
   - If a concurrent transaction inserts the pair first, the subsequent transaction catches the resulting `IntegrityError`, executes `db.rollback()`, and retrieves the committed record's `userID`.

2. **String Sanitization:**
   - Pydantic ensures input fields are populated, and application logic strips leading/trailing whitespace via `.strip()`.
   - Strings containing only empty spaces are rejected with `400 Bad Request` to preserve data integrity.

3. **Information Disclosure Prevention:**
   - Internal database connection traces and SQLAlchemy crash dumps are logged privately to the console via `logging.getLogger`.
   - Client-facing responses return clean, sanitized messages to prevent the exposure of internal schemas, credentials, or environment paths.

4. **Connection Pool Management:**
   - SQLAlchemy engine configuration includes `pool_pre_ping=True` to prune stale/dropped connections and `pool_recycle=3600` to prevent MySQL wait-timeout disconnections during idle periods.
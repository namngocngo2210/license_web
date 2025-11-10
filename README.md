# License Manager Web (Django)

Web application that mirrors the behavior described in the [License Management API documentation](https://raw.githubusercontent.com/namngocngo2210/license/main/API.md). Users can register, sign in, and self-manage license codes tied to phone numbers, while administrators can oversee all users and licenses via Django admin. An unauthenticated `/verify` endpoint is exposed for external services to validate licenses.

## Prerequisites

- Python 3.9+
- PostgreSQL instance reachable from the app (Docker or local)

### Default database credentials

The project targets a PostgreSQL database with the following defaults (override via environment variables if needed):

```
POSTGRES_DB=license_db
POSTGRES_USER=namnn
POSTGRES_PASSWORD=Ngocnam2210
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# copy env.sample to .env and adjust if needed
cp env.sample .env

# OR export variables in your shell (optional alternative)
# export POSTGRES_DB=license_db
# export POSTGRES_USER=namnn
# export POSTGRES_PASSWORD=Ngocnam2210
# export POSTGRES_HOST=127.0.0.1      # or Docker container hostname
# export POSTGRES_PORT=5432

python manage.py migrate
python manage.py createsuperuser    # optional, for Django admin
python manage.py runserver
```

Access the site at `http://127.0.0.1:8000/`.

## Features

- User registration, login, and logout flows
- License CRUD for authenticated users (unique per phone number, UUIDv4 codes auto-generated)
- License expiry extension aligned with the API spec
- Admin interface (`/admin/`) for managing users and licenses
- Public REST endpoint `POST /verify` returning the documented JSON contract

## Verify Endpoint

```
POST http://127.0.0.1:8000/verify
Content-Type: application/json

{
  "code": "...",
  "phone_number": "..."
}
```

Responses follow the structure in the upstream documentation, including status codes `200`, `400`, `404`, `410`, and `500` for invalid `expired_at` values.

## Static Files

During development, static assets (Bootstrap + custom CSS) are served automatically. For production, run `python manage.py collectstatic` and point your web server to `staticfiles/`.

## Running checks

- `python manage.py check` – validate Django project configuration
- `python manage.py test` – (add tests as the project evolves)


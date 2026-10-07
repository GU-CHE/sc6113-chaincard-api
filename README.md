# ChainCard transaction API

Flask API that checks an Ethereum mainnet transaction by hash through JSON-RPC and stores verified public details in PostgreSQL. It never accepts wallet keys or user-supplied transaction details.

## Environment variables

- `DATABASE_URL`: PostgreSQL connection URL. Keep this only in Render backend environment variables.
- `FRONTEND_ORIGIN`: allowed browser origin; defaults to `https://sc6113-chaincard.onrender.com`.

## Render deployment

1. Create a Render Postgres database and a Python Web Service from this repository. Keep them in the same region.
2. Run `pip install -r requirements.txt` as the build command and `python init_db.py && gunicorn app:app` as the start command.
3. Set the backend's `DATABASE_URL` to the database **internal** URL.
4. `init_db.py` creates the table and index on startup. The API exposes `GET /health`, `GET /api/transactions`, and `POST /api/transactions` with JSON `{ "tx_hash": "0x..." }`.

The saved list is public and shared. Add wallet authentication before storing private notes or user-specific data. Render Free Postgres expires after 30 days and has no managed backups.

"""Create the demo schema before starting the web service."""

from pathlib import Path

from app import db_connect


statements = Path(__file__).with_name("schema.sql").read_text().split(";")
with db_connect() as connection:
    for statement in statements:
        if statement.strip():
            connection.execute(statement)
print("Database schema ready")

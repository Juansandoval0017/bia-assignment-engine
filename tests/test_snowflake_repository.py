from datetime import date

from app.snowflake_repository import _lowercase_row


def test_lowercase_row_maps_snowflake_columns():
    row = _lowercase_row(["ID", "FECHA_CREACION"], (7, date(2026, 9, 17)))

    assert row == {"id": 7, "fecha_creacion": date(2026, 9, 17)}

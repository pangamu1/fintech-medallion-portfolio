"""
Reverse-ETL serving layer: read curated gold marts from the Databricks SQL
warehouse and publish them to a Google Sheet (one tab per mart) for Tableau Public.
"""
import logging
from datetime import date, datetime
from decimal import Decimal

import gspread

from databricks import sql

import config

logging.basicConfig(level=logging.INFO, format="%(name)s [%(levelname)s] %(message)s")
logging.getLogger("databricks.sql").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def fetch_table(fqn: str) -> tuple[list[str], list[tuple]]:
    """
    Run SELECT * on a fully-qualified gold mart, return (column_names, rows).

    fqn comes only from config.BI_MARTS (trusted constants), never user input,
    so f-string interpolation of the identifier is safe — and SQL bind params
    can't bind table names anyway.
    """
    server_hostname = config.DATABRICKS_HOST.replace("https://", "").rstrip("/")
    with sql.connect(
        server_hostname=server_hostname,
        http_path=config.DATABRICKS_HTTP_PATH,
        access_token=config.DATABRICKS_TOKEN,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {fqn}")
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

    logger.info("Fetched %s — %d rows x %d cols", fqn, len(rows), len(columns))
    return columns, rows

def _to_cell(value):
    """Coerce a warehouse value into a Sheets-safe cell."""
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def write_sheet(spreadsheet, tab_name: str, columns: list[str], rows: list[tuple]) -> None:
    """Write one mart to its own tab: header + coerced rows, sized exactly."""
    n_rows = len(rows) + 1  # +1 for the header row
    n_cols = len(columns)
    try:
        worksheet = spreadsheet.worksheet(tab_name)
        worksheet.clear()
        worksheet.resize(rows=n_rows, cols=n_cols)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=n_rows, cols=n_cols)

    values = [columns] + [[_to_cell(v) for v in row] for row in rows]
    worksheet.update(values, value_input_option="USER_ENTERED")
    logger.info("Wrote tab %s — %d data rows", tab_name, len(rows))

def main() -> None:
    gc = gspread.service_account(filename=config.GOOGLE_APPLICATION_CREDENTIALS)
    spreadsheet = gc.open_by_key(config.BI_SHEET_ID)

    for fqn in config.BI_MARTS:
        tab_name = fqn.split(".")[-1]
        columns, rows = fetch_table(fqn)
        write_sheet(spreadsheet, tab_name, columns, rows)

    logger.info(
        "Serving complete — %d marts written to Sheet %s",
        len(config.BI_MARTS), config.BI_SHEET_ID,
    )


if __name__ == "__main__":
    main()
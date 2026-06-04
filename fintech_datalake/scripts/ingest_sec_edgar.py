"""
Fetch SEC EDGAR Form 4 (insider transactions) for the ticker universe,
parse the ownershipDocument XML into normalized transaction-line records,
and land the JSON in Bronze.

Keyless API — politeness via a descriptive User-Agent + rate pacing.
"""
import json
import logging
import time
import xml.etree.ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
import utils

logging.basicConfig(level=logging.INFO, format="%(name)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Pace under SEC's 10 req/s ceiling: 1/10 = 0.1s minimum spacing per call.
_SEC_SECONDS_BETWEEN_CALLS = 1.0 / config.SEC_RATE_LIMIT_PER_SECOND


def _log(ticker: str, status: str, error: str | None = None) -> None:
    """Wrap utils.log_run with this module's source/endpoint baked in."""
    utils.log_run(
        log_path=config.INGESTION_LOG_PATH,
        ticker=ticker,
        source="sec",
        endpoint=config.SEC_ENDPOINT_NAME,
        status=status,
        error=error,
    )

def _v(el: ET.Element, path: str) -> str | None:
    """
    Return the stripped text at a relative path, or None if absent/empty.

    Form 4 nests real values under a '/value' leaf, and optional fields may
    be present-but-empty (e.g. a price that carries only a footnoteId). This
    collapses both "no element" and "empty text" to None.
    """
    text = el.findtext(path)
    if text is None:
        return None
    text = text.strip()
    return text or None


def _document_context(root: ET.Element) -> dict:
    """Pull the filing-level fields shared by every transaction line."""
    rel = "reportingOwner/reportingOwnerRelationship"
    return {
        "period_of_report": _v(root, "periodOfReport"),
        "issuer_cik": _v(root, "issuer/issuerCik"),
        "issuer_name": _v(root, "issuer/issuerName"),
        "issuer_symbol": _v(root, "issuer/issuerTradingSymbol"),
        "rpt_owner_cik": _v(root, "reportingOwner/reportingOwnerId/rptOwnerCik"),
        "rpt_owner_name": _v(root, "reportingOwner/reportingOwnerId/rptOwnerName"),
        "is_director": _v(root, f"{rel}/isDirector"),
        "is_officer": _v(root, f"{rel}/isOfficer"),
        "officer_title": _v(root, f"{rel}/officerTitle"),
        "is_ten_percent_owner": _v(root, f"{rel}/isTenPercentOwner"),
        "is_other": _v(root, f"{rel}/isOther"),
    }

# Per-line leaf paths shared by non-derivative AND derivative transactions.
_COMMON_FIELDS = {
    "security_title": "securityTitle/value",
    "transaction_date": "transactionDate/value",
    "transaction_code": "transactionCoding/transactionCode",
    "transaction_form_type": "transactionCoding/transactionFormType",
    "equity_swap_involved": "transactionCoding/equitySwapInvolved",
    "transaction_shares": "transactionAmounts/transactionShares/value",
    "transaction_price_per_share": "transactionAmounts/transactionPricePerShare/value",
    "acquired_disposed_code": "transactionAmounts/transactionAcquiredDisposedCode/value",
    "shares_owned_following": "postTransactionAmounts/sharesOwnedFollowingTransaction/value",
    "direct_or_indirect": "ownershipNature/directOrIndirectOwnership/value",
}
# Extra leaves present only on derivative lines (options / RSUs).
_DERIVATIVE_FIELDS = {
    "conversion_or_exercise_price": "conversionOrExercisePrice/value",
    "exercise_date": "exerciseDate/value",
    "expiration_date": "expirationDate/value",
    "underlying_security_title": "underlyingSecurity/underlyingSecurityTitle/value",
    "underlying_security_shares": "underlyingSecurity/underlyingSecurityShares/value",
}

def _transaction_lines(root: ET.Element) -> list[dict]:
    """
    One record per transaction line across both tables (holdings excluded).

    nonDerivativeTransaction + derivativeTransaction are matched explicitly,
    so nonDerivativeHolding (no date/code) is skipped by design.
    """
    records: list[dict] = []
    tables = [
        ("non_derivative", "nonDerivativeTable/nonDerivativeTransaction", {}),
        ("derivative", "derivativeTable/derivativeTransaction", _DERIVATIVE_FIELDS),
    ]
    for table_name, path, extra in tables:
        for i, tx in enumerate(root.findall(path)):
            fields = {**_COMMON_FIELDS, **extra}
            record = {key: _v(tx, leaf) for key, leaf in fields.items()}
            record["table"] = table_name
            record["line_index"] = i
            records.append(record)
    return records

def _parse_form4(
    session: requests.Session,
    ticker: str,
    cik10: str,
    accession: str,
    primary_doc: str,
) -> list[dict]:
    """
    Fetch + parse one Form 4 into flat transaction-line records.

    Each record = identifiers (ticker, accession) + document context + the
    line's own fields. Returns [] for a filing carrying no transaction lines
    (e.g. holdings-only).
    """
    xml = _fetch_form4_xml(session, cik10, accession, primary_doc)
    root = ET.fromstring(xml)
    context = _document_context(root)

    records = []
    for line in _transaction_lines(root):
        records.append({
            "ticker": ticker,
            "accession": accession,
            **context,
            **line,
        })
    return records

def _build_session() -> requests.Session:
    """
    Session with retry/backoff AND the mandatory SEC User-Agent header.

    The header is set on the session so EVERY request carries it — EDGAR
    returns 403 Forbidden for requests without a descriptive User-Agent.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": config.SEC_USER_AGENT})
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

def _load_cik_map(session: requests.Session) -> dict[str, str]:
    """
    Fetch the ticker -> CIK map once and return {ticker: cik10} for our universe.

    company_tickers.json is a dict keyed by row index; each value is
    {"cik_str": int, "ticker": str, "title": str}. We invert it to a
    ticker-keyed lookup and zero-pad the CIK to the 10-digit form the
    submissions API expects.
    """
    logger.info("Fetching CIK map from %s", config.SEC_TICKERS_URL)
    response = session.get(config.SEC_TICKERS_URL, timeout=30)
    response.raise_for_status()
    raw = response.json()

    by_ticker = {row["ticker"]: row["cik_str"] for row in raw.values()}

    cik_map: dict[str, str] = {}
    for ticker in config.TICKERS:
        cik_int = by_ticker.get(ticker)
        if cik_int is None:
            logger.error("Ticker %s not found in SEC CIK map", ticker)
            continue
        cik_map[ticker] = f"{cik_int:010d}"
    return cik_map

def _recent_form4_filings(
    session: requests.Session, cik10: str
) -> list[tuple[str, str]]:
    """
    Return up to SEC_MAX_FILINGS_PER_TICKER recent (accession, primary_doc)
    pairs where form == "4", newest first.

    The submissions JSON stores filings as PARALLEL arrays under
    filings.recent (accessionNumber[i] <-> form[i] <-> primaryDocument[i]),
    already ordered newest-first. We read only this recent page (~1000 most
    recent filings); older pages under filings.files are out of scope.
    """
    url = f"{config.SEC_SUBMISSIONS_BASE}/CIK{cik10}.json"
    logger.info("Fetching submissions %s", url)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    recent = response.json()["filings"]["recent"]

    filings: list[tuple[str, str]] = []
    for accession, form, primary_doc in zip(
        recent["accessionNumber"], recent["form"], recent["primaryDocument"]
    ):
        if form == config.SEC_FORM_TYPE:
            filings.append((accession, primary_doc))
        if len(filings) >= config.SEC_MAX_FILINGS_PER_TICKER:
            break
    return filings

def _fetch_form4_xml(
    session: requests.Session, cik10: str, accession: str, primary_doc: str
) -> str:
    """
    Fetch the raw Form 4 ownershipDocument XML for one filing.

    URL = {archives}/{cik}/{accession_nodash}/{doc_basename}
      - cik: UN-padded (archives uses the plain int, not the 10-digit form)
      - accession_nodash: dashes stripped
      - doc_basename: primaryDocument minus any 'xslF345X.../' viewer prefix
        (that prefix points at the HTML-styled view; the basename is raw XML)
    """
    cik = int(cik10)
    accession_nodash = accession.replace("-", "")
    doc = primary_doc.split("/")[-1]
    url = f"{config.SEC_ARCHIVES_BASE}/{cik}/{accession_nodash}/{doc}"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text

def main() -> None:
    session = _build_session()
    cik_map = _load_cik_map(session)
    time.sleep(_SEC_SECONDS_BETWEEN_CALLS)

    for ticker, cik10 in cik_map.items():
        logger.info("Ingesting SEC Form 4 for %s (CIK %s)", ticker, cik10)
        try:
            filings = _recent_form4_filings(session, cik10)
            time.sleep(_SEC_SECONDS_BETWEEN_CALLS)

            records: list[dict] = []
            for accession, primary_doc in filings:
                records.extend(
                    _parse_form4(session, ticker, cik10, accession, primary_doc)
                )
                time.sleep(_SEC_SECONDS_BETWEEN_CALLS)
        except (requests.exceptions.RequestException, ET.ParseError) as e:
            logger.error("SEC ingest failed for %s: %s", ticker, e)
            _log(ticker, "error", str(e))
        else:
            saved = utils.save_to_lake(
                data=records,
                source="sec",
                endpoint_name=config.SEC_ENDPOINT_NAME,
                ticker=ticker,
                lake_path=config.BRONZE_PATH,
            )
            logger.info("Bronze file: %s (%d records, %d bytes)",
                        saved, len(records), saved.stat().st_size)
            _log(ticker, "success")


if __name__ == "__main__":
    main()
"""Discover and download official management-language reports for 23 banks."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import argparse
import hashlib
import json
import re

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE_DIR = Path(__file__).resolve().parent
USER_AGENT = "EuroBank-Prism/1.0 research-document-discovery"
TIMEOUT = (8, 15)
MAX_BYTES = 30 * 1024 * 1024
CURRENT_YEAR = datetime.now(timezone.utc).year
# Four quarters usually span two calendar years.  This is deliberately wider
# than the current-report search, but discovery output remains review-only.
ACCEPTED_FULL_YEARS = {str(CURRENT_YEAR - offset) for offset in range(3)}
CORE_RESULT_TERMS = (
    "results", "result", "earnings", "quarter", "q1", "q2", "q3", "q4",
    "half year", "half yearly", "half-year", "interim", "h1", "1h",
    "nine month", "nine-month", "9m", "full year", "full-year", "fy",
)
NON_ENGLISH_TERMS = ("risultati", "resultados", "ergebnisse", "résultats")

POSITIVE_TERMS = {
    "results presentation": 18,
    "result presentation": 18,
    "earnings presentation": 18,
    "half-year results": 16,
    "half year results": 16,
    "interim results": 15,
    "quarterly results": 15,
    "financial results": 12,
    "results": 8,
    "presentation": 8,
    "q1": 8,
    "q2": 8,
    "q3": 8,
    "q4": 8,
    "h1": 8,
    "first half": 8,
    "6m": 8,
    "9m": 8,
    "nine month": 8,
    "full year": 8,
    "fy": 8,
    "english": 5,
    " en ": 3,
}
NEGATIVE_TERMS = {
    "annual report": -25,
    "universal registration": -25,
    "pillar 3": -30,
    "pillar iii": -30,
    "pillar": -100,
    "esg": -100,
    "sustainability": -25,
    "remuneration": -25,
    "compensation": -25,
    "solvency": -15,
    "financial statements": -12,
    "transcript": -5,
    "invitation": -100,
    "fixed income": -60,
    "media release": -25,
    "press release": -20,
}

CHILD_PAGE_TERMS = (
    "result", "results", "quarter", "earnings", "financial", "interim",
    "presentation", "report", "2025", "2026", "q1", "q2", "q3", "q4",
)
CHILD_PAGE_REJECT = (
    "calendar", "contact", "career", "governance", "sustainability", "esg",
    "remuneration", "privacy", "cookie", "annual-general-meeting", "rating",
)
# These issuer archives contain links to very slow or non-responsive media
# endpoints. Their verified current source remains in the curated registry and
# historical periods are resolved manually from the issuer archive.
DEEP_DISCOVERY_SKIP = {"BNP", "DBK", "SAB", "BPE"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized(value: str) -> str:
    return " " + re.sub(r"[_/\-]+", " ", value.lower()) + " "


def anchor_context(anchor) -> str:
    """Include nearby period/title text when the link itself only says PDF."""
    own = " ".join(anchor.stripped_strings)
    best = own
    node = anchor
    for _ in range(5):
        node = node.parent
        if node is None:
            break
        nearby = " ".join(node.stripped_strings)
        if len(nearby) > 700:
            continue
        best = nearby
        if any(term in normalized(nearby) for term in CORE_RESULT_TERMS) and re.search(
            r"(?:20\d{2}|\b(?:q[1-4]|h1|1h|9m|fy)\s*\d{2}\b)", nearby, re.I
        ):
            break
    return best[:700]


def candidate_score(label: str, url: str) -> int:
    text = normalized(f"{label} {url}")
    if not any(term in text for term in CORE_RESULT_TERMS):
        return -100
    short_years = "|".join(year[2:] for year in ACCEPTED_FULL_YEARS)
    has_recent_period = any(year in text for year in ACCEPTED_FULL_YEARS) or bool(
        re.search(rf"\b(?:q[1-4]|h1|1h)\s*(?:{short_years})\b", text)
    )
    if not has_recent_period:
        return -100
    if any(term in text for term in NON_ENGLISH_TERMS):
        return -100
    score = sum(weight for term, weight in POSITIVE_TERMS.items() if term in text)
    score += sum(weight for term, weight in NEGATIVE_TERMS.items() if term in text)
    if ".pdf" in url.lower():
        score += 12
    for age in range(4):
        if str(CURRENT_YEAR - age) in text:
            score += 16 - age * 4
            break
    return score


def discover_candidates(page_url: str) -> list[dict]:
    response = requests.get(page_url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    candidates = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        absolute = urljoin(response.url, href)
        own_label = " ".join(anchor.stripped_strings)
        direct_text = f"{own_label} {absolute}"
        has_direct_period = bool(re.search(
            r"(?:20\d{2}.*\b(?:q[1-4]|h1|1h|9m|fy)\b|"
            r"\b(?:q[1-4]|h1|1h|9m|fy)\b.*20\d{2})",
            direct_text,
            re.I,
        ))
        label = own_label if has_direct_period else anchor_context(anchor)
        combined = f"{label} {absolute}".lower()
        if ".pdf" not in combined and "download" not in combined:
            continue
        score = candidate_score(label, absolute)
        if score < 35:
            continue
        existing = candidates.get(absolute)
        record = {"label": label[:300], "url": absolute, "score": score}
        if not existing or record["score"] > existing["score"]:
            candidates[absolute] = record

    # Some issuer sites embed document URLs in JSON rather than anchor tags.
    for match in re.findall(r"https?[^\"'<>\\ ]+?\.pdf(?:\?[^\"'<>\\ ]*)?", response.text, flags=re.I):
        absolute = match.replace("\\/", "/")
        score = candidate_score("", absolute)
        if score >= 35 and absolute not in candidates:
            candidates[absolute] = {"label": "Embedded PDF", "url": absolute, "score": score}
    return sorted(candidates.values(), key=lambda row: row["score"], reverse=True)


def discover_child_pages(page_url: str, limit: int = 8) -> list[str]:
    """Find a small, same-domain set of likely results pages to inspect."""
    response = requests.get(page_url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    origin = urlparse(response.url)
    ranked = {}
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(response.url, anchor.get("href", "").strip())
        parsed = urlparse(absolute)
        if parsed.netloc != origin.netloc or absolute == response.url:
            continue
        text = normalized(f"{' '.join(anchor.stripped_strings)} {parsed.path} {parsed.query}")
        if any(term in text for term in CHILD_PAGE_REJECT):
            continue
        score = sum(3 for term in CHILD_PAGE_TERMS if term in text)
        if any(year in text for year in ACCEPTED_FULL_YEARS):
            score += 8
        if score < 6 or ".pdf" in parsed.path.lower():
            continue
        clean = absolute.split("#", 1)[0]
        ranked[clean] = max(score, ranked.get(clean, -1))
    return [url for url, _ in sorted(ranked.items(), key=lambda row: row[1], reverse=True)[:limit]]


def discover_candidates_deep(page_url: str) -> list[dict]:
    """Inspect the archive and a bounded set of same-domain results pages."""
    merged = {row["url"]: row for row in discover_candidates(page_url)}
    for child_url in discover_child_pages(page_url):
        try:
            for row in discover_candidates(child_url):
                row = {**row, "discovered_on": child_url}
                previous = merged.get(row["url"])
                if previous is None or row["score"] > previous["score"]:
                    merged[row["url"]] = row
        except requests.RequestException:
            continue
    return sorted(merged.values(), key=lambda row: row["score"], reverse=True)


def period_from_candidate(candidate: dict) -> tuple[str, str]:
    text = normalized(f"{candidate.get('label', '')} {candidate['url']}")
    def expanded_year(short_or_full: str) -> str:
        digits = re.sub(r"\D", "", short_or_full)
        return digits if len(digits) == 4 else f"20{digits[-2:]}"

    quarter_patterns = (
        r"\bq([1-4])\D{0,5}(20\d{2}|\d{2})\b",
        r"\b([1-4])q\D{0,5}(20\d{2}|\d{2})\b",
        r"\b(20\d{2})\D{0,5}q([1-4])\b",
    )
    for index, pattern in enumerate(quarter_patterns):
        match = re.search(pattern, text)
        if not match:
            continue
        if index == 2:
            year, quarter = match.group(1), match.group(2)
        else:
            quarter, year = match.group(1), expanded_year(match.group(2))
        return "quarterly_results", f"Q{quarter} {year}"

    year_match = re.search(r"20\d{2}", text)
    year = year_match.group(0) if year_match else str(CURRENT_YEAR)
    short_period = re.search(r"\b(h1|1h|9m|fy)\D{0,5}(20\d{2}|\d{2})\b", text)
    if short_period:
        token, matched_year = short_period.groups()
        year = expanded_year(matched_year)
        if token in {"h1", "1h"}:
            return "half_year_results", f"H1 {year}"
        if token == "9m":
            return "nine_month_results", f"9M {year}"
        return "full_year_results", f"FY{year}"
    if any(term in text for term in (" h1 ", "first half", "half year", "half-year", "6m")):
        return "half_year_results", f"H1 {year}"
    if any(term in text for term in (" 9m ", "nine month", "nine-month", "third quarter")):
        return "nine_month_results", f"9M {year}"
    if any(term in text for term in (" full year ", "full-year", " fy ", "annual results")):
        return "full_year_results", f"FY{year}"
    return "results_material", year


def period_order(period: str) -> int:
    """Map European reporting checkpoints to a sortable quarter sequence."""
    year_match = re.search(r"20\d{2}", period)
    if not year_match:
        return -1
    year = int(year_match.group(0))
    upper = period.upper()
    if upper.startswith("Q1"):
        checkpoint = 1
    elif upper.startswith(("Q2", "H1")):
        checkpoint = 2
    elif upper.startswith(("Q3", "9M")):
        checkpoint = 3
    elif upper.startswith(("Q4", "FY")):
        checkpoint = 4
    else:
        return -1
    return year * 4 + checkpoint


def safe_filename(ticker: str, candidate: dict) -> str:
    document_type, period = period_from_candidate(candidate)
    period_slug = re.sub(r"[^A-Za-z0-9]+", "_", period).strip("_")
    return f"{ticker}_{period_slug}_{document_type}_en.pdf"


def download_pdf(ticker: str, candidate: dict) -> dict:
    folder = BASE_DIR / "reports" / ticker
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / safe_filename(ticker, candidate)
    if destination.exists() and destination.read_bytes()[:4] == b"%PDF":
        return {
            "status": "already_downloaded",
            "path": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
        }

    response = requests.get(
        candidate["url"],
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        stream=True,
        allow_redirects=True,
    )
    response.raise_for_status()
    content_length = int(response.headers.get("content-length", 0) or 0)
    if content_length > MAX_BYTES:
        raise ValueError(f"document exceeds {MAX_BYTES // (1024 * 1024)} MB limit")
    received = 0
    first = b""
    with destination.open("wb") as handle:
        for chunk in response.iter_content(1024 * 256):
            if not chunk:
                continue
            if not first:
                first = chunk[:4]
                if first != b"%PDF":
                    raise ValueError("download is not a PDF")
            received += len(chunk)
            if received > MAX_BYTES:
                raise ValueError(f"document exceeds {MAX_BYTES // (1024 * 1024)} MB limit")
            handle.write(chunk)
    return {
        "status": "downloaded",
        "path": str(destination),
        "bytes": received,
        "sha256": sha256(destination),
    }


def discover_one(bank: dict, pages: dict, download: bool) -> dict:
    ticker = bank["ticker"]
    page_url = pages.get(ticker, {}).get("quarterly")
    result = {
        "ticker": ticker,
        "bank_name": bank["bank_name"],
        "official_page": page_url,
        "checked_at": utc_now(),
        "status": "manual_review_required",
        "selected": None,
        "alternatives": [],
    }
    if not page_url:
        result["error"] = "missing official quarterly-results page"
        return result
    try:
        candidates = (
            discover_candidates(page_url)
            if ticker in DEEP_DISCOVERY_SKIP
            else discover_candidates_deep(page_url)
        )
        result["alternatives"] = candidates[:12]
        if not candidates:
            result["error"] = "no suitable PDF link discovered"
            return result
        selected_periods = []
        seen_periods = set()
        seen_checkpoints = set()
        eligible = []
        for candidate in candidates:
            document_type, period = period_from_candidate(candidate)
            # Language drift compares interim/quarterly management material;
            # annual reports are intentionally excluded from this candidate set.
            if document_type not in {
                "quarterly_results", "half_year_results", "nine_month_results",
                "full_year_results",
            }:
                continue
            candidate_text = normalized(f"{candidate.get('label', '')} {candidate['url']}")
            # Compare one consistent management-facing genre. Regulatory
            # reports, releases and trading statements have different writing
            # conventions and would create artificial language drift.
            if "presentation" not in candidate_text:
                continue
            if any(term in candidate_text for term in (
                "modern slavery", "trading update", "annual report",
                "financial report", "press release", " rns ", "infographic",
            )):
                continue
            eligible.append((period_order(period), candidate, document_type, period))
        # Recency, not keyword score, determines the four-period window.  The
        # score only breaks ties between multiple files for the same period.
        eligible.sort(key=lambda row: (row[0], row[1]["score"]), reverse=True)
        for _, candidate, document_type, period in eligible:
            if period in seen_periods:
                continue
            checkpoint = period_order(period)
            if checkpoint in seen_checkpoints:
                continue
            seen_periods.add(period)
            seen_checkpoints.add(checkpoint)
            selected_periods.append({
                **candidate,
                "document_type": document_type,
                "document_series": "management_results",
                "period": period,
                "source_status": "pending_human_review",
            })
            if len(selected_periods) == 4:
                break
        result["selected_periods"] = selected_periods
        result["selected"] = selected_periods[0] if selected_periods else candidates[0]
        result["status"] = "discovered"
        if download:
            result.update(download_pdf(ticker, result["selected"]))
    except Exception as exc:
        result["error"] = str(exc)
    return result


def run(download: bool, workers: int = 6) -> list[dict]:
    banks = json.loads((BASE_DIR / "bank_master.json").read_text(encoding="utf-8"))["constituents"]
    pages = json.loads((BASE_DIR / "official_report_pages.json").read_text(encoding="utf-8"))
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(discover_one, bank, pages, download): bank["ticker"]
            for bank in banks
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"{result['ticker']}: {result['status']}", flush=True)
    order = {bank["ticker"]: index for index, bank in enumerate(banks)}
    results.sort(key=lambda row: order[row["ticker"]])
    output = BASE_DIR / "language_report_registry.json"
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output}")
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download each top-ranked candidate. Discovery is not automatic curation.")
    parser.add_argument("--workers", type=int, default=6)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    run(download=arguments.download, workers=arguments.workers)

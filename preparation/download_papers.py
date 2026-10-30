"""Download available open-access PDFs listed by DOI in Paper_info.csv."""

from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAPER_FILE = PROJECT_ROOT / "resources" / "Paper_info.csv"
PDF_DIR = PROJECT_ROOT / "resources" / "paper_pdf"
OPENALEX_URL = "https://api.openalex.org/works"
USER_AGENT = "Paper-PDF-downloader/1.0 (educational research)"
PMID_PATTERN = re.compile(r"^\d+$")
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
PMCID_PATTERN = re.compile(r"^PMC\d+$", re.IGNORECASE)


def read_papers(path: Path) -> list[tuple[str, str, str]]:
    """Read unique PMID, PMCID, DOI rows from the paper metadata CSV."""
    papers: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    with path.open(encoding="utf-8-sig", newline="") as paper_file:
        reader = csv.DictReader(paper_file)
        required_columns = {"PMID", "PMCID", "DOI"}
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise ValueError(f"{path} must contain PMID, PMCID, and DOI columns")

        for row in reader:
            pmid = (row.get("PMID") or "").strip()
            pmcid = (row.get("PMCID") or "").strip()
            doi = (row.get("DOI") or "").strip()
            if not PMID_PATTERN.fullmatch(pmid):
                print(f"Skipping row with invalid PMID: {pmid}")
                continue
            if pmcid and not PMCID_PATTERN.fullmatch(pmcid):
                print(f"Ignoring invalid PMCID for PMID {pmid}: {pmcid}")
                pmcid = ""
            if doi.lower().startswith("https://doi.org/"):
                doi = doi[len("https://doi.org/") :]
            if doi and not DOI_PATTERN.fullmatch(doi):
                print(f"Ignoring invalid DOI for PMID {pmid}: {doi}")
                doi = ""
            if not pmcid and not doi:
                print(f"No PMCID or DOI for PMID {pmid}; skipping")
                continue
            if pmid not in seen:
                papers.append((pmid, pmcid, doi.lower()))
                seen.add(pmid)

    if not papers:
        raise ValueError(f"No usable paper records found in {path}")
    return papers


def lookup_pdf_urls(dois: list[str]) -> dict[str, str]:
    """Find direct open-access PDF URLs by DOI, using bounded batches."""
    pdf_urls: dict[str, str] = {}

    dois = list(dict.fromkeys(doi for doi in dois if doi))
    for start in range(0, len(dois), 100):
        batch = dois[start : start + 100]
        params = urlencode(
            {
                "filter": "doi:" + "|".join(batch),
                "per_page": 100,
                "select": "doi,best_oa_location,locations",
            }
        )
        request = Request(
            f"{OPENALEX_URL}?{params}",
            headers={"User-Agent": USER_AGENT},
        )
        with urlopen(request, timeout=30) as response:
            data = json.load(response)

        for work in data.get("results", []):
            doi = (work.get("doi") or "").removeprefix("https://doi.org/").lower()
            location = work.get("best_oa_location") or {}
            pdf_url = location.get("pdf_url") or next(
                (
                    item["pdf_url"]
                    for item in work.get("locations", [])
                    if item.get("is_oa") and item.get("pdf_url")
                ),
                None,
            )
            if doi and pdf_url:
                pdf_urls[doi] = pdf_url

    return pdf_urls


def download_pdf(pdf_url: str, destination: Path) -> None:
    """Download a PDF to a temporary file and publish it only if valid."""
    request = Request(pdf_url, headers={"User-Agent": USER_AGENT})
    temporary_path: str | None = None

    try:
        with urlopen(request, timeout=60) as response:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent, suffix=".tmp", delete=False
            ) as temporary_file:
                temporary_path = temporary_file.name
                first_chunk = response.read(8192)
                if not first_chunk.startswith(b"%PDF-"):
                    raise ValueError("the server response was not a PDF")
                temporary_file.write(first_chunk)
                while chunk := response.read(1024 * 1024):
                    temporary_file.write(chunk)

        os.replace(temporary_path, destination)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def main() -> None:
    papers = read_papers(PAPER_FILE)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pending = []
    skipped = 0
    for paper in papers:
        if (PDF_DIR / f"{paper[0]}.pdf").is_file():
            print(f"Already exists: {paper[0]}.pdf")
            skipped += 1
        else:
            pending.append(paper)

    try:
        pdf_urls = lookup_pdf_urls([doi for _, _, doi in pending])
    except (URLError, TimeoutError, ConnectionError, ValueError) as error:
        print(f"OpenAlex DOI lookup failed: {error}")
        pdf_urls = {}
    downloaded = 0

    for pmid, pmcid, doi in pending:
        destination = PDF_DIR / f"{pmid}.pdf"
        candidates = []
        if doi in pdf_urls:
            candidates.append(pdf_urls[doi])
        if pmcid:
            candidates.append(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/")
        if not candidates:
            print(
                f"No direct open-access PDF found for PMID {pmid} "
                f"(DOI: {doi or 'none'})"
            )
            skipped += 1
            continue

        for pdf_url in candidates:
            try:
                download_pdf(pdf_url, destination)
                break
            except (URLError, TimeoutError, ConnectionError, ValueError) as error:
                print(f"Could not download PMID {pmid} from {pdf_url}: {error}")
        else:
            skipped += 1
            continue

        print(f"Downloaded PMID {pmid} to {destination}")
        downloaded += 1

    print(f"Finished: {downloaded} downloaded, {skipped} skipped.")


if __name__ == "__main__":
    main()

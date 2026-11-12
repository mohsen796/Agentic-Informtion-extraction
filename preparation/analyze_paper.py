"""Extract PDFs with GROBID and convert its TEI output to JSON."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = PROJECT_ROOT / "resources" / "paper_pdf"
OUTPUT_DIR = PROJECT_ROOT / "resources" / "analyzed_papers"
STATUS_FILE = OUTPUT_DIR / "extraction_status.json"
GROBID_URL = os.environ.get("GROBID_URL", "http://localhost:8070").rstrip("/")
GROBID_ENDPOINT = f"{GROBID_URL}/api/processFulltextDocument"


def _tag(element: ET.Element) -> str:
    """Return an XML element's local tag name."""
    return element.tag.rsplit("}", 1)[-1]


def _text(element: ET.Element | None) -> str:
    """Return normalized text content, or an empty string for a missing element."""
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _first_text(element: ET.Element, tag: str) -> str:
    """Return the first nonempty descendant text for a local tag name."""
    return next(
        (_text(node) for node in element.iter() if _tag(node) == tag and _text(node)),
        "",
    )


def _person_records(parent: ET.Element) -> list[dict[str, Any]]:
    """Extract named people and affiliations from author or editor elements."""
    people = []
    for person in parent.iter():
        if _tag(person) != "author":
            continue
        name_element = next(
            (node for node in person if _tag(node) == "persName"), None
        )
        name_parts = [
            _text(node)
            for node in name_element.iter()
            if _tag(node) in {"forename", "surname", "nameLink", "roleName"}
            and _text(node)
        ] if name_element is not None else []
        name = " ".join(name_parts) or _text(name_element) or _first_text(person, "orgName")
        affiliations = []
        for affiliation in person.iter():
            if _tag(affiliation) != "affiliation":
                continue
            parts = [
                _text(node)
                for node in affiliation.iter()
                if _tag(node)
                in {"orgName", "addrLine", "settlement", "region", "country", "postCode"}
                and _text(node)
            ]
            affiliation_text = ", ".join(dict.fromkeys(parts)) or _text(affiliation)
            if affiliation_text and affiliation_text not in affiliations:
                affiliations.append(affiliation_text)
        if name:
            people.append({"name": name, "affiliations": affiliations})
    return people


def _sections(body: ET.Element) -> list[dict[str, Any]]:
    """Return body headings and paragraphs grouped by their TEI section."""
    sections: list[dict[str, Any]] = []

    def visit(container: ET.Element, path: list[str]) -> None:
        direct_paragraphs = [
            _text(child)
            for child in container
            if _tag(child) == "p" and _text(child)
        ]
        direct_heading = next(
            (_text(child) for child in container if _tag(child) == "head" and _text(child)),
            "",
        )
        divs = [child for child in container if _tag(child) == "div"]

        if _tag(container) == "div" or direct_paragraphs:
            heading_path = path + ([direct_heading] if direct_heading else [])
            if direct_paragraphs or direct_heading:
                sections.append(
                    {
                        "section": " / ".join(heading_path) or "Unsectioned",
                        "paragraphs": direct_paragraphs,
                    }
                )
            for div in divs:
                visit(div, heading_path)
        else:
            for div in divs:
                visit(div, path)

    visit(body, [])
    return sections


def _references(root: ET.Element) -> list[dict[str, Any]]:
    """Extract structured bibliography entries from the TEI back matter."""
    references = []
    back = next((node for node in root.iter() if _tag(node) == "back"), root)
    bibliography = next(
        (node for node in back.iter() if _tag(node) == "listBibl"), back
    )
    for entry in bibliography.iter():
        if _tag(entry) != "biblStruct":
            continue
        analytic = next((node for node in entry if _tag(node) == "analytic"), None)
        monograph = next((node for node in entry if _tag(node) == "monogr"), None)
        analytic = analytic if analytic is not None else entry
        monograph = monograph if monograph is not None else entry
        title = next(
            (
                _text(node)
                for node in analytic.iter()
                if _tag(node) == "title" and _text(node)
            ),
            "",
        )
        container_title = next(
            (
                _text(node)
                for node in monograph.iter()
                if _tag(node) == "title" and _text(node)
            ),
            "",
        )
        doi = next(
            (
                _text(node)
                for node in entry.iter()
                if _tag(node) == "idno"
                and node.attrib.get("type", "").lower() == "doi"
            ),
            "",
        )
        scopes = {
            node.attrib.get("unit", ""): node.attrib.get("from")
            or node.attrib.get("n")
            or _text(node)
            for node in entry.iter()
            if _tag(node) == "biblScope"
        }
        date = next(
            (
                node.attrib.get("when") or _text(node)
                for node in entry.iter()
                if _tag(node) == "date" and (node.attrib.get("when") or _text(node))
            ),
            "",
        )
        references.append(
            {
                "id": entry.attrib.get("{http://www.w3.org/XML/1998/namespace}id", ""),
                "authors": _person_records(analytic),
                "title": title,
                "container_title": container_title,
                "date": date,
                "doi": doi,
                "volume": scopes.get("volume", ""),
                "issue": scopes.get("issue", ""),
                "pages": scopes.get("page", scopes.get("pp", "")),
                "text": _text(entry),
            }
        )
    return references


def _figures(root: ET.Element) -> list[dict[str, str]]:
    """Extract figure captions, labels, and image references."""
    figures = []
    for figure in root.iter():
        if _tag(figure) != "figure" or figure.attrib.get("type", "").lower() == "table":
            continue
        figures.append(
            {
                "id": figure.attrib.get("{http://www.w3.org/XML/1998/namespace}id", ""),
                "label": _first_text(figure, "label"),
                "caption": _first_text(figure, "head") or _first_text(figure, "figDesc"),
                "image": next(
                    (
                        node.attrib.get("url", "")
                        for node in figure.iter()
                        if _tag(node) == "graphic"
                    ),
                    "",
                ),
            }
        )
    return figures


def _tables(root: ET.Element) -> list[dict[str, Any]]:
    """Extract table captions and cell text from TEI tables."""
    parents = {child: parent for parent in root.iter() for child in parent}
    tables = []
    for table in root.iter():
        if _tag(table) != "table":
            continue
        wrapper = parents.get(table)
        rows = [
            [_text(cell) for cell in row if _tag(cell) == "cell"]
            for row in table.iter()
            if _tag(row) == "row"
        ]
        tables.append(
            {
                "label": _first_text(wrapper, "label") if wrapper is not None else "",
                "caption": _first_text(wrapper, "head") if wrapper is not None else "",
                "rows": rows,
                "text": _text(table),
            }
        )
    return tables


def parse_tei(tei: str) -> dict[str, Any]:
    """Extract requested paper fields from one GROBID TEI document."""
    root = ET.fromstring(tei)
    header = next((node for node in root.iter() if _tag(node) == "teiHeader"), None)
    body = next((node for node in root.iter() if _tag(node) == "body"), None)
    if header is None:
        raise ValueError("GROBID TEI is missing the document header")

    title_statement = next(
        (node for node in header.iter() if _tag(node) == "titleStmt"), header
    )
    profile = next((node for node in header.iter() if _tag(node) == "profileDesc"), header)
    title = _first_text(title_statement, "title")
    abstract = next((node for node in profile.iter() if _tag(node) == "abstract"), None)
    doi = next(
        (
            _text(node)
            for node in header.iter()
            if _tag(node) == "idno" and node.attrib.get("type", "").lower() == "doi"
        ),
        "",
    )
    date = next(
        (
            node.attrib.get("when") or _text(node)
            for node in header.iter()
            if _tag(node) == "date" and (node.attrib.get("when") or _text(node))
        ),
        "",
    )
    journal = next(
        (
            _text(node)
            for node in header.iter()
            if _tag(node) == "title"
            and node.attrib.get("level") == "j"
            and _text(node)
        ),
        "",
    )
    keywords = [
        _text(node)
        for node in profile.iter()
        if _tag(node) in {"term", "keyword"} and _text(node)
    ]
    authors = _person_records(header)
    return {
        "title": title,
        "abstract": _text(abstract),
        "date": date,
        "doi": doi,
        "journal": journal,
        "authors": authors,
        "keywords": list(dict.fromkeys(keywords)),
        "text": _sections(body) if body is not None else [],
        "references": _references(root),
        "figures": _figures(root),
        "tables": _tables(root),
    }


def extract_pdf(pdf_path: Path) -> str:
    """Send one PDF to GROBID and return its complete TEI response."""
    boundary = f"----CodexGrobid{uuid.uuid4().hex}"
    filename = pdf_path.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="input"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + pdf_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    request = Request(
        GROBID_ENDPOINT,
        data=body,
        headers={
            "Accept": "application/xml",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8")


def extract_papers() -> list[dict[str, Any]]:
    """Save GROBID TEI responses and a separate per-PDF extraction status manifest."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {PDF_DIR}")

    statuses = []
    for pdf_path in pdf_files:
        status: dict[str, Any] = {
            "source_pdf": pdf_path.name,
            "tei_file": f"{pdf_path.stem}.tei.xml",
            "extraction_error": False,
            "error": None,
        }
        try:
            tei = extract_pdf(pdf_path)
            (OUTPUT_DIR / status["tei_file"]).write_text(tei, encoding="utf-8")
            print(f"Extracted {pdf_path.name}")
        except Exception as error:
            status.update(extraction_error=True, error=str(error), tei_file=None)
            print(f"Failed {pdf_path.name}: {error}")
        statuses.append(status)

    STATUS_FILE.write_text(
        json.dumps(statuses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return statuses


def convert_tei_to_json() -> None:
    """Convert every saved TEI file to JSON, retaining extraction errors per PDF."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    statuses = json.loads(STATUS_FILE.read_text(encoding="utf-8")) if STATUS_FILE.exists() else []
    status_by_tei = {entry.get("tei_file"): entry for entry in statuses}
    status_by_pdf = {entry.get("source_pdf"): entry for entry in statuses}
    tei_files = sorted(OUTPUT_DIR.glob("*.tei.xml"))
    processed: set[str] = set()
    converted = 0

    for tei_path in tei_files:
        source_pdf = tei_path.name.removesuffix(".tei.xml") + ".pdf"
        status = status_by_pdf.get(source_pdf, status_by_tei.get(tei_path.name, {}))
        record: dict[str, Any] = {
            "source_pdf": source_pdf,
            "extraction_error": bool(status.get("extraction_error", False)),
            "error": status.get("error"),
            "grobid_tei": None if status.get("extraction_error") else tei_path.name,
        }
        processed.add(tei_path.name)
        try:
            if record["extraction_error"]:
                raise ValueError(str(record["error"] or "GROBID extraction failed"))
            record.update(parse_tei(tei_path.read_text(encoding="utf-8")))
        except Exception as error:
            record.update(
                extraction_error=True,
                error=str(error),
                title="",
                abstract="",
                date="",
                doi="",
                journal="",
                authors=[],
                keywords=[],
                text=[],
                references=[],
                figures=[],
                tables=[],
            )
        json_path = OUTPUT_DIR / f"{tei_path.name.removesuffix('.tei.xml')}.json"
        json_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        converted += 1

    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        tei_name = f"{pdf_path.stem}.tei.xml"
        if tei_name in processed:
            continue
        status = status_by_pdf.get(pdf_path.name, {})
        json_path = OUTPUT_DIR / f"{pdf_path.stem}.json"
        previous = (
            json.loads(json_path.read_text(encoding="utf-8"))
            if json_path.exists()
            else {}
        )
        record = {
            "source_pdf": pdf_path.name,
            "extraction_error": True,
            "error": status.get("error") or previous.get("error") or "No GROBID TEI file found",
            "grobid_tei": status.get("tei_file"),
            "title": "",
            "abstract": "",
            "date": "",
            "doi": "",
            "journal": "",
            "authors": [],
            "keywords": [],
            "text": [],
            "references": [],
            "figures": [],
            "tables": [],
        }
        json_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"Converted {converted} TEI files to JSON.")


def main() -> None:
    """Run the GROBID extraction and/or saved-TEI conversion stages."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--convert-only",
        action="store_true",
        help="convert existing TEI files without calling GROBID",
    )
    args = parser.parse_args()
    if not args.convert_only:
        extract_papers()
    convert_tei_to_json()


if __name__ == "__main__":
    main()

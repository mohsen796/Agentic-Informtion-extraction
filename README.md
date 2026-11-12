# Agentic-Informtion-extraction

## Downloading papers by DOI

Run the downloader from the project root:

```bash
python preparation/download_papers.py
```

It reads `resources/Paper_info.csv`, tries the PMC PDF when a PMCID is present,
then looks up a direct open-access PDF by DOI. Downloads are saved as
`resources/paper_pdf/<PMID>.pdf`. Papers without a direct open-access PDF are
reported and skipped; the script does not access subscription-only content.

## Extracting papers with GROBID

Start a GROBID service, then run:

```bash
python preparation/analyze_paper.py
```

The script sends every PDF in `resources/paper_pdf/` to
`http://localhost:8070/api/processFulltextDocument`. Set `GROBID_URL` to a
different service base URL if needed. It saves GROBID TEI XML files and an
extraction status manifest in `resources/analyzed_papers/`, then converts the
TEI files into one JSON record per paper. The JSON contains title, abstract,
date, DOI, journal, authors and affiliations, keywords, text grouped by section,
references, figures, tables, and an `extraction_error` flag. To convert
existing TEI files without contacting GROBID, run:

```bash
python preparation/analyze_paper.py --convert-only
```

## Configuration and API keys

Keep secrets such as API keys in the root `.env` file, using `NAME=value` lines.
Do not commit `.env`. Put non-secret application settings in `configs.yaml` so
they can be shared with the project. Do not put keys or other secrets in YAML.

These files are conventions for future scripts; the downloader and GROBID
extractor do not load them or require an API key.

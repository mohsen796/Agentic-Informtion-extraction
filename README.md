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

## Configuration and API keys

Keep secrets such as API keys in the root `.env` file, using `NAME=value` lines.
Do not commit `.env`. Put non-secret application settings in `configs.yaml` so
they can be shared with the project. Do not put keys or other secrets in YAML.

These files are conventions for future scripts; the current paper downloader
does not load them or require an API key.

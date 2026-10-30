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

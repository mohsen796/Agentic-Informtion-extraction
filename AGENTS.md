# Repository Guidelines

## Project Structure

- `main.py` is the top-level module (currently empty).
- `preparation/` contains data preparation and download scripts. The paper downloader is `preparation/download_papers.py`.
- `resources/` stores input data, including `Paper_info.csv` and `PMID_papers.txt`. Downloaded PDFs go in `resources/paper_pdf/`.
- There is no test directory or separate asset directory currently.

## Run and Develop

Run commands from the repository root:

```bash
python preparation/download_papers.py
python -m py_compile preparation/download_papers.py
```

The downloader reads `resources/Paper_info.csv`, uses OpenAlex and PMC over the network, and writes PDFs under `resources/paper_pdf/`. It only downloads a response that starts with a PDF signature. No build system or dependency manifest is currently configured; the script uses Python’s standard library.

## Style and Naming

Use Python with four-space indentation, `snake_case` for functions and variables, and `UPPER_SNAKE_CASE` for module constants. Prefer standard-library modules and small functions that follow the downloader’s existing patterns. Keep input validation and temporary-file cleanup when changing download behavior. Use UTF-8 for text files and preserve the CSV header names (`PMID`, `PMCID`, `DOI`).

## Tests and Validation

No test framework or coverage target is configured. For code changes, at minimum compile changed Python files with `python -m py_compile <file>`. For downloader changes that affect parsing or URL selection, add focused tests if a test suite is introduced; avoid running the network downloader as a routine test because it can make external requests and write PDFs.

## Commits and Pull Requests

The short history uses plain, lowercase descriptive commit subjects (for example, `added paper download script to the project`). Follow that style and describe one change per commit. Pull requests should summarize the behavior change, list validation performed, note any new network/API assumptions, and include a linked issue when one exists. Screenshots are unnecessary for this command-line project.

## Data and Access

Do not commit downloaded PDFs, credentials, API keys, or other private files. Respect publisher access controls: the downloader should use direct open-access copies and report papers it cannot access.

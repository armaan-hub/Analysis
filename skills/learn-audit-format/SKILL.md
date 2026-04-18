# learn-audit-format

> Learn an audit PDF format from a reference document so it can be applied to future reports.

## Description

Extracts page layout, fonts, margins, and section structure from a reference
audit PDF.  The extracted template config is verified for correctness and can
optionally be saved to the server and published to the global template library.

**Trigger phrases**: "learn audit format", "learn template from PDF",
"extract audit template", "import audit format"

## Usage

```
python -m cli.template_learner --pdf <path> --name <template-name> [options]
```

### Options

| Flag             | Required | Default                | Description                                   |
|------------------|----------|------------------------|-----------------------------------------------|
| `--pdf`          | Yes      | —                      | Path to the reference audit PDF               |
| `--name`         | Yes      | —                      | Human-readable template name                  |
| `--user-id`      | No       | `cli_user`             | Owner user ID for the saved template          |
| `--save`         | No       | off                    | Save the template to the server via REST API  |
| `--publish`      | No       | off                    | Publish to the global template library        |
| `--api-url`      | No       | `http://localhost:8000` | Base URL of the running backend server       |
| `--skip-verify`  | No       | off                    | Skip the verification step                    |
| `--json`         | No       | off                    | Output raw JSON instead of pretty-printed text|

### Examples

**Extract and display** (no server required):

```
python -m cli.template_learner \
  --pdf "Draft FS - Castle Plaza 2025.pdf" \
  --name "castle-plaza-2025"
```

**Extract, save, and publish** (requires running server):

```
python -m cli.template_learner \
  --pdf "Draft FS - Castle Plaza 2025.pdf" \
  --name "castle-plaza-2025" \
  --save --publish --user-id admin
```

**JSON output for scripting**:

```
python -m cli.template_learner \
  --pdf report.pdf --name my-template --json
```

## Workflow

```
┌───────────┐     ┌──────────┐     ┌──────────┐     ┌─────────┐
│  Extract   │────▶│  Verify  │────▶│   Save   │────▶│ Publish │
│ (analyze)  │     │ (report) │     │ (API)    │     │ (API)   │
└───────────┘     └──────────┘     └──────────┘     └─────────┘
  always           default          --save           --publish
```

1. **Extract** — `TemplateAnalyzer.analyze(pdf)` reads the PDF with PyMuPDF and
   returns a `template_config` dict (page dims, margins, fonts, sections).
2. **Verify** — `TemplateVerifier.generate_report(config)` runs dimension,
   margin, font, and section checks.  Skipped with `--skip-verify`.
3. **Save** — POSTs the PDF to `/api/templates/upload-reference`, then triggers
   `/api/templates/learn/{job_id}` and polls `/api/templates/status/{job_id}`.
   Only runs when `--save` is given.
4. **Publish** — Calls `/api/templates/publish/{template_id}` to make the
   template globally available.  Only runs when `--publish` is given (implies
   `--save`).

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `PyMuPDF not installed` | `fitz` missing | `pip install PyMuPDF` |
| `File not found` | Bad path | Use an absolute path or check the filename |
| `Connection refused` on save | Server not running | Start backend with `run_project.bat` or pass `--api-url` |
| Low confidence (< 0.5) | Scanned / image-only PDF | Use a text-based PDF as reference |
| `Template status 'needs_review'` | Verification failed | Fix the source PDF or lower tolerance |

# ItemFinder — Demand Intelligence System

Analyzes Discord chat logs (DiscordChatExporter JSON format) to extract demand signals, brand trends, and community sentiment.

## What It Does

- **Most Requested Items** — identifies items users are actively seeking
- **Missed Opportunities** — items users regret not buying (unmet demand)
- **Most Loved Items** — items with high satisfaction mentions
- **Ownership Tracking** — what the community currently owns
- **Trending Now** — velocity-based spike detection
- **Channel Breakdown** — per-channel intent analysis

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### 1. Ingest Discord Logs

```bash
python -m src.ingest.discord_ingest
```

### 2. Process & Score

```bash
python -m src.process.pipeline
```

### 3. Generate Reports

```bash
python -m src.report.generate_report
```

### 4. Launch Dashboard

```bash
python -m src.dashboard.app
```

Open http://127.0.0.1:8050 in your browser.

## Outputs

| File | Description |
|------|-------------|
| `out/report.md` | Executive summary with top items, brands, trends |
| `out/items.csv` | Scored item data |
| `out/brands.csv` | Scored brand data |
| `out/insights.json` | Structured insights for programmatic use |

## Project Structure

```
src/
  common/     — config, database, logging
  ingest/     — Discord JSON ingestion (streaming for large files)
  process/    — normalize, classify, extract, score
  analytics/  — trend detection, channel breakdown
  dashboard/  — Plotly Dash interactive dashboard
  report/     — markdown, CSV, JSON report generation
tests/        — unit tests
data/         — SQLite database
out/          — generated reports
```

## Running Tests

```bash
python -m pytest tests/ -v
```

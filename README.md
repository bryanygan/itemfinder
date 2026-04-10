# ItemFinder — Demand Intelligence System

Analyzes Discord chat logs, Reddit communities, and external market data (Weidian/1688 live sales, QC platforms) to extract demand signals, brand trends, purchasing recommendations, and community sentiment.

## What It Does

- **Most Requested Items** — identifies items users are actively seeking
- **Missed Opportunities** — items users regret not buying (unmet demand)
- **Most Loved Items** — items with high satisfaction mentions
- **Ownership Tracking** — what the community currently owns
- **Trending Now** — velocity-based spike detection
- **Channel Breakdown** — per-channel/subreddit intent analysis
- **Market Intelligence** — external trend data from Reddit, Weidian, 1688, and QC platforms
- **Purchase Recommendations** — scored buy signals combining internal + external data
- **Batch Quality Guide** — community-consensus best batches per sneaker model
- **Upcoming Hype Releases** — retail drops that drive future replica demand

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### 1. Ingest Data

**Discord Logs:**
```bash
python -m src.ingest.discord_ingest
```

**Reddit (authenticated via PRAW):**
```bash
python -m src.ingest.reddit_ingest
```

**Reddit (public, no API key required):**
```bash
python -m src.ingest.reddit_public
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

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Overview** | KPI summary, top brands, intent breakdown, action items |
| **Market Intelligence** | External trend data: Reddit community trends, Weidian/1688 live sales, purchase recommendations, batch guide, upcoming releases, QC platform info |
| **What to Stock** | Unmet demand analysis, inventory recommendations, size/color demand |
| **Customer Insights** | Buyer profiles, segments, cross-sell opportunities, conversions |
| **Item Explorer** | Searchable/sortable table of all detected items with scores |
| **Market Trends** | Daily activity time-series, fastest rising items, seasonality |
| **Channel Analysis** | Per-channel mention volume, intent mix, signal strength |
| **Demand Signals** | Breakdown by intent type: requests, satisfaction, regret, ownership |

## Data Sources

### Internal (Community Analysis)
- **Discord** — DiscordChatExporter JSON format, streaming parser (ijson)
- **Reddit** — PRAW API or public `.json` endpoints with proxy support

### External (Market Intelligence)
- **Reddit Communities** — Aggregated trends from 9+ subreddits (4.5M+ combined members)
- **Weidian** — Live agent-tracked purchase data via JadeShip/RepArchive
- **1688** — Bulk/budget segment sales tracking
- **QC Platforms** — doppel.fit, FinderQC (finderqc.com), FindQC (findqc.com)
- **Hype Releases** — Upcoming retail drops from Hypebeast, Complex, SoleRetriever

### Monitored Subreddits

| Subreddit | Weight | Focus |
|-----------|--------|-------|
| r/FashionReps (2.2M) | 1.5x | General fashion reps |
| r/Repsneakers (969K) | 1.5x | Sneaker reps |
| r/DesignerReps (450K) | 1.5x | Luxury & designer |
| r/QualityReps (320K) | 1.5x | High-quality / archive fashion |
| r/RepBudgetSneakers (229K) | 1.3x | Budget sneaker finds |
| r/FashionRepsBST (180K) | 1.4x | Buy/Sell/Trade |
| r/CloseToRetail | 1.3x | Near-1:1 quality reps |
| r/WeidianWarriors | 1.1x | Weidian finds & deals |
| r/1688Reps | 1.2x | 1688 bulk/budget finds |
| + shipping agent subs | 0.9x | Sugargoo, Superbuy, cssbuy, etc. |

## Scoring System

### Intent Classification (5 types)
| Intent | Weight | Examples |
|--------|--------|----------|
| **Regret** | 1.0 | "should have copped", "missed out", "slept on" |
| **Request** | 0.8 | "WTB", "W2C", "looking for", "need" |
| **Satisfaction** | 0.6 | "fire", "10/10", "best cop", "GL" |
| **Ownership** | 0.4 | "just copped", "in hand", "arrived" |
| **Neutral** | 0.1 | General discussion, informational |

### Final Score Formula
```
final_score = 0.5 × intent_score + 0.3 × velocity + 0.2 × volume
```

### Purchase Recommendation Scoring
```
combined_score = 0.5 × external_score + 0.5 × internal_score
```
- **BUY NOW** (0.85+) — Top priority, very high demand
- **STRONG BUY** (0.70+) — Stock immediately
- **BUY** (0.55+) — Solid opportunity
- **WATCH** (0.40+) — Monitor closely
- **HOLD** (<0.40) — Lower priority

## Outputs

| File | Description |
|------|-------------|
| `out/report.md` | Executive summary with top items, brands, trends |
| `out/items.csv` | Scored item data (brand, item, variant, mentions, velocity, score) |
| `out/brands.csv` | Scored brand data (mentions, avg_intent, trend_score) |
| `out/insights.json` | Structured insights for programmatic use |

## Project Structure

```
src/
  common/       — config, database, logging
  ingest/       — Discord JSON + Reddit ingestion (streaming for large files)
  process/      — normalize, classify intent, extract entities, score
  analytics/    — trend detection, sales intelligence, market intelligence
  dashboard/    — Plotly Dash interactive dashboard (8 tabs)
  report/       — markdown, CSV, JSON report generation
tests/          — unit tests (168 tests)
data/           — SQLite database
out/            — generated reports
scripts/        — helper scripts (Reddit setup)
```

### Key Files

| File | Purpose |
|------|---------|
| `src/common/config.py` | Centralized config: brand aliases, intent keywords, subreddit weights, batch names |
| `src/common/db.py` | SQLite schema (raw_messages, processed_mentions, reddit_metadata) |
| `src/ingest/discord_ingest.py` | Discord JSON streaming parser |
| `src/ingest/reddit_ingest.py` | Reddit PRAW-based collector |
| `src/ingest/reddit_public.py` | Reddit public API scraper (no auth required) |
| `src/process/pipeline.py` | Main processing pipeline (normalize → classify → extract → store) |
| `src/process/classify.py` | Intent classification (keyword + flair matching) |
| `src/process/extract.py` | Entity extraction (brand, item, variant, batch, agent) |
| `src/process/scoring.py` | Demand scoring (intent + velocity + volume) |
| `src/analytics/trends.py` | Trend detection, channel breakdown, daily volume |
| `src/analytics/sales_intel.py` | Unmet demand, buyer profiles, cross-sell, inventory recs |
| `src/analytics/market_intel.py` | External market intelligence, purchase recommendations |
| `src/dashboard/app.py` | Plotly Dash dashboard (8 tabs) |
| `src/dashboard/components.py` | Reusable UI components (KPI cards, charts, tables) |
| `src/report/generate_report.py` | Report generation (MD, CSV, JSON) |

## Running Tests

```bash
python -m pytest tests/ -v
```

## Dependencies

- `pandas` — DataFrames and data manipulation
- `plotly` — Interactive visualizations
- `dash` — Web dashboard framework
- `dash-bootstrap-components` — Bootstrap theming
- `praw` — Reddit API wrapper
- `ijson` — Streaming JSON parser for large Discord exports

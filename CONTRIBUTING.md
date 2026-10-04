# Contributing to Eliminate Cigarettes

Eliminate Cigarettes is an open-source data pipeline monitoring prohibited tobacco and nicotine advertising using mandatory ad transparency archives under Article 39 of the EU Digital Services Act.

## Project Structure

- `src/google_harvest.py`: Harvester for Google Ads Transparency Center records.
- `src/tiktok_harvest.py`: Scraper and harvester for the TikTok Commercial Content Library.
- `src/evidence.py`: Generates standardized evidence packets citing violated platform policies and statutory guidelines.
- `data/ads.db`: SQLite database storing normalized ad creatives, advertisers, and impressions.

## Development Setup

Python 3.11+ is required:

```bash
# Clone
git clone https://github.com/Ahmet-Dedeler/eliminate-cigarettes.git
cd eliminate-cigarettes

# Create virtual environment and install requirements
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt # or uv sync
```

## How to Contribute

- Check [open issues](https://github.com/Ahmet-Dedeler/eliminate-cigarettes/issues) for starter tasks.
- Contributions welcomed for new platform harvesters (Meta Ad Library, X ad repository), keyword classification filters, and automated evidence report export formats.

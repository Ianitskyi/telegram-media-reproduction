# Відтворення контенту професійних медіа в українських Telegram-каналах (2020–2026)

Дослідницький репозиторій статті для журналу *Communications and Communicative Technologies*. Автор: Андрій Яніцький.

- **Як ми працюємо:** [`docs/WORKFLOW.md`](docs/WORKFLOW.md) · **Рішення:** [`docs/DECISIONS.md`](docs/DECISIONS.md) · **Журнал:** [`docs/WORKLOG.md`](docs/WORKLOG.md)
- **Аудит методу:** [`docs/AUDIT_2026-10-21.md`](docs/AUDIT_2026-10-21.md) · **Результати v2:** [`results/v2/SUMMARY.md`](results/v2/SUMMARY.md) · **Промпти:** [ChatGPT-перевіряльник](docs/CHATGPT_PROMPT.md), [незалежний аудитор](docs/AUDITOR_PROMPT.md) · **Дані:** [`DATA.md`](DATA.md) · **Контекст:** [`docs/handoff/`](docs/handoff/)

Початковий код (збір даних і аналіз) написав Олег Семенюк ([osemeoseme/tg-influence-media](https://github.com/osemeoseme/tg-influence-media)); історію його комітів збережено. Відомі проблеми цього коду описано в аудиті й виправляються тут.

---

## Оригінальний README

# Content Reproduction of Traditional Media in Telegram Channels

Research project analyzing how traditional Ukrainian media content is reproduced in popular Telegram news channels.

## Quick Links

- **[QUICKSTART.md](QUICKSTART.md)** - Step-by-step setup and usage guide
- **[METHODOLOGY.md](METHODOLOGY.md)** - Detailed research methodology
- **[examples/](examples/)** - Custom analysis examples

## Project Overview

This project investigates the content reproduction from traditional media outlets in popular Telegram channels by analyzing what percentage of Telegram content can be traced back to traditional media sources. The goal is to demonstrate the continued value of professional journalism in the social media ecosystem.

### Problem Statement

Traditional media faces devaluation against unprofessional content producers on social networks, leading to declining advertiser and reader interest. This research aims to demonstrate the observable reproduction of traditional media content in popular Telegram channels.

## Methodology

The project uses three complementary detection methods:

### 1. Direct Link Detection
Identifies explicit citations through hyperlinks to traditional media sources.

### 2. Media Mention Detection
Finds references to media outlet names in message text (e.g., "according to Babel...").

### 3. Semantic Similarity Detection
Uses NLP to detect rephrased or uncredited content by comparing message embeddings with media article embeddings.

**For detailed methodology, see [METHODOLOGY.md](METHODOLOGY.md)**

## Data Sources

- **Telegram Channels**: 13 popular Ukrainian news channels
- **Traditional Media**: 142 Ukrainian media outlets (national and regional)
- **Time Range**: Configurable (default: last 48 hours)

All data sources are configurable in `config/` directory.

## Project Structure

```
├── config/                      # Configuration files
│   ├── telegram_channels.json   # Telegram channels to analyze
│   └── media_sources.json       # Media outlets to track
├── data/                        # Data storage (created on first run)
│   ├── raw/                     # Raw scraped data
│   ├── processed/               # Processed data
│   └── results/                 # Analysis results and reports
├── examples/                    # Example scripts
│   └── custom_analysis.py       # Custom analysis examples
├── notebooks/                   # Analysis notebooks
│   └── exploratory_analysis.py  # Exploratory data analysis
├── src/                         # Source code
│   ├── analyzers/               # Analysis modules
│   │   ├── link_detector.py     # Direct link detection
│   │   ├── mention_detector.py  # Media mention detection
│   │   ├── similarity_detector.py # Semantic similarity
│   │   └── combined_analyzer.py # Combined analysis
│   ├── scrapers/                # Data collection
│   │   ├── telegram_scraper.py  # Telegram API scraper
│   │   └── media_scraper.py     # Web scraper for media
│   ├── processors/              # Data processing
│   │   └── report_generator.py  # Report and visualization
│   └── utils/                   # Utilities
│       └── config.py            # Configuration management
├── .env.template                # Environment variables template
├── .gitignore                   # Git ignore rules
├── main.py                      # Main execution script
├── Makefile                     # Make commands for common tasks
├── METHODOLOGY.md               # Detailed methodology
├── QUICKSTART.md                # Quick start guide
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── setup.sh                     # Setup script (Unix)
└── setup.bat                    # Setup script (Windows)
```

## Quick Start

### 1. Automated Setup (Recommended)

**Unix/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

### 2. Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.template .env
# Edit .env and add your Telegram API credentials
```

### 3. Configure Telegram API

1. Go to https://my.telegram.org/apps
2. Create a new application
3. Copy API ID and API Hash to `.env` file

### 4. Run Analysis

```bash
# Run complete pipeline
python main.py all

# Or run steps individually:
python main.py scrape   # Collect data
python main.py analyze  # Analyze data
python main.py report   # Generate reports
```

**Using Make:**
```bash
make all      # Run complete pipeline
make scrape   # Scrape data only
make analyze  # Analyze only
make report   # Generate reports only
make explore  # Run exploratory analysis
```

## Output

The analysis generates:

- **Interactive Presentation**:
  - `presentation.html`: Full presentation with charts (requires `data/results/` folder)
  - `presentation_standalone.html`: Self-contained version with embedded images (3MB, shareable as single file)
- **Text Report** (`data/results/report.txt`): Summary statistics
- **Visualizations**:
  - `analysis_visualizations.png`: Channel-by-channel analysis
  - `reference_categories.png`: Distribution of citation types
  - `influence_by_method.png`: Detection method breakdown (separated independent vs traditional media channels)
  - `temporal/`: Time-based visualizations
- **CSV Files**:
  - `summary.csv`: Per-channel statistics
  - `detailed_messages.csv`: Message-level data
- **JSON Files**: Complete analysis results

## Key Metrics

- **Percentage Reproduced**: Portion of Telegram content traced to traditional media
- **Detection Breakdown**: How content reproduction was detected (links, mentions, similarity)
- **Media Rankings**: Most referenced media outlets
- **Channel Comparison**: Which channels rely most on traditional media

## Technologies

- **Python 3.8+**: Core language
- **Telethon**: Telegram API client
- **Sentence Transformers**: Multilingual semantic similarity
- **BeautifulSoup4 & newspaper3k**: Web scraping
- **Pandas**: Data analysis
- **Matplotlib & Seaborn**: Visualization

## Project Context

This is a university project for the Machine Learning course at UCU (Ukrainian Catholic University), in collaboration with ProMedia NGO.

**Project Supervisor**: Andrii Ianitskyi (a.ianitskyi@gmail.com)

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)**: Detailed setup and usage instructions
- **[METHODOLOGY.md](METHODOLOGY.md)**: Research methodology and technical details
- **[examples/custom_analysis.py](examples/custom_analysis.py)**: Code examples for custom analysis

## Contributing

This is an educational project. For improvements or issues:
1. Review the code documentation
2. Check existing analysis results
3. Propose enhancements based on methodology

## License

This project is for educational and research purposes.

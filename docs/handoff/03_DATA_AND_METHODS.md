# Data and methods: verified state and risks

## GitHub methodology

Repository documents describe a multi-method pipeline:

1. **Direct link detection**
2. **Media mention detection**
3. **Semantic similarity**

Semantic model:
- `paraphrase-multilingual-MiniLM-L12-v2`

Current documented semantic rules:
- cosine similarity threshold: **0.75**
- media article must precede Telegram message
- maximum time gap: **48 hours**
- Telegram messages shorter than 50 characters are skipped for semantic matching
- semantic matching is intended for messages without links or mentions according to `METHODOLOGY.md`

Primary combined indicator in old code/docs is effectively:

`has_media_link OR has_media_mention OR has_similar_content`

Old variable names may still say `influenced_percentage`. In the paper rename conceptually to content reproduction / traceability.

## Telegram scraper fields

Verified scraper output fields include:
- id
- date
- text
- views
- forwards
- channel_username
- channel_name
- urls

No subscriber-count field appears in the shown scraper.

## Telegram channel config: 13 channels

1. Труха Україна — `truexanewsua`
2. ТСН Новини — `TCH_channel`
3. Суспільне Новини — `suspilnenews`
4. Київ Інфo I Новини України — `kievinfo_kyiv`
5. Інсайдер ЗСУ — `insider_zsy`
6. Україна 24/7 - новини — `ukraina_novosti`
7. Україна Онлайн — `UaOnlii`
8. Николаевский Ванек — `vanek_nikolaev`
9. УНИАН — `uniannet`
10. Лачен пише — `lachentyt`
11. Українська правда — `ukrpravda_news`
12. Times of Ukraine — `times_ukraina`
13. Батальон “Монако” — `batalionmonako`

The intended selection criterion was the Internews 2025 media consumption study. This must be verified against the exact table/list in the primary Internews report.

## Professional media source list

`config/media_sources.json` is large and appears to include national and regional media. Project docs describe 142 media sources (18 national + 124 regional), but presentation materials also use other counts.

The config fields include:
- name
- url
- domains
- region
- type

There is **no provenance field** identifying whether each source came from:
- IMI White List,
- Map of Recommended Media,
- both,
- or another source.

This provenance must be reconstructed before the paper claims what media universe was used.

## Critical longitudinal validity issue: media article corpus

Raw Google Drive file `media_all_articles.json` is ~9.8 MB, while the Telegram corpus is ~903 MB.

This raises a serious methodological question: did the media scraper actually collect professional-media articles across the entire 2020–2026 period, or mainly recent material around April 2026?

This is crucial because:
- link detection and brand mentions can work historically without a six-year article corpus;
- semantic similarity cannot be longitudinally comparable if historical media articles are missing.

Before publishing any 2020–2026 semantic trend, inspect:
- article count;
- min/max publish dates;
- date distribution by source;
- proportion of articles with missing `publish_date`;
- whether `scraped_at` is being used as a proxy;
- whether archive pages/RSS/API were capable of retrieving historical articles.

## Example of a false-positive risk already visible in data

The analysis output can mark a media mention based on ambiguous outlet names that happen to occur as ordinary words or place names. For example short/generic media names such as “Є”, “КУРС”, “Море Людей”, “Точка Сходу” may produce false positives unless matching is context-aware.

This means mention detection needs validation, especially for short or ambiguous brand names.

## Semantic similarity validation risk

A high semantic score does not prove direction of copying. A Telegram post and a media article can both derive from the same official source. In wartime, official statements are commonly republished by many actors.

The article therefore should avoid wording such as “Telegram channel copied media X” unless direct evidence supports that direction. Safer wording:
- “семантично пов’язане з матеріалом медіа”
- “відтворює той самий інформаційний зміст”
- “має високу семантичну подібність до матеріалу професійного медіа”

## Manual validation needed

Current docs mention manual inspection but do not clearly document a completed validation sample.

For a journal article, ideally validate a stratified sample across:
- direct links
- mentions
- semantic matches near threshold 0.75
- high semantic matches
- different years/channels

Report precision/false-positive patterns at minimum; ideally inter-coder agreement if two authors code a sample independently.

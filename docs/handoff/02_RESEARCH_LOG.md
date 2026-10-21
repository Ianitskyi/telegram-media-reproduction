# Research log and decisions

## Terminology

- Early project language used “influence”.
- Supervisor/advisor feedback prompted a terminology change.
- Current preferred term: **“відтворення контенту професійних медіа в Telegram-каналах”**.
- Rationale: methods capture links, mentions, and semantic similarity; they do not prove causal influence.

## Corpus interpretation

- Config contains 13 Telegram channels.
- Two channels have almost no usable observations:
  - “Інсайдер ЗСУ”: 3 messages;
  - “Україна 24/7 - новини”: 1 message.
- Therefore 11 channels are substantively analyzable.
- Four of those 11 are Telegram channels of professional media:
  - ТСН Новини
  - Суспільне Новини
  - УНИАН
  - Українська правда
- Core non-media comparison group therefore contains 7 channels.

## Why 41.87% should not be the main article finding

The global 41.87% combines:
- non-media channels, and
- Telegram channels of media organizations themselves.

This inflates/changes the interpretation because self-publication/self-reference is structurally different from reproduction by outside actors.

## Per-channel percentages from current summary

- Труха Україна — 29.98%
- ТСН Новини — 56.01%
- Суспільне Новини — 77.21%
- Київ Інфo I Новини України — 52.85%
- Інсайдер ЗСУ — 0% (3 messages only)
- Україна 24/7 - новини — 0% (1 message only)
- Україна Онлайн — 30.51%
- Николаевский Ванек — 19.92%
- УНИАН — 23.18%
- Лачен пише — 22.42%
- Українська правда — 78.81%
- Times of Ukraine — 38.77%
- Батальон “Монако” — 32.36%

Important correction: an earlier presentation statement that all traditional-media Telegram channels were around 77–79% is false. TСН is ~56%; УНИАН ~23%.

## Methodology inconsistencies found in project documentation

The project documentation contains stale or mutually inconsistent descriptions:
- 13 channels and 142 traditional media outlets;
- “Top 20+ Ukrainian media outlets” in a presentation;
- “whitelist of 100+ media domains” elsewhere;
- “max 10,000 messages per channel” in the presentation, which is incompatible with >1M total messages;
- “analysis period: 3 months” on one slide, while another slide says 2020–2026 / 6 years.

Do not copy these claims into the article until reconciled with actual code/data.

## Direct links issue

In `summary.csv`, `Link Only = 0` for every channel.

This must be investigated before making any claim that links are rare or that mentions/similarity dominate. Possible explanations:
- messages with links are always simultaneously classified by another method and thus fall under “Multiple Methods”;
- a bug or aggregation rule is hiding link-only cases.

## Self-citation issue

Oleh wrote in chat that he “removed self-links / self-citation” and updated visualizations. This needs verification in current code/output before it is described in Methods.

## Temporal analysis

Existing code generates:
- daily share classified as reproduced by any method;
- 7-day rolling average;
- weekly detection-method rates with a 4-week rolling average;
- top-media mention trends;
- monthly message volume with a 3-month average.

Two channels are explicitly excluded from temporal visualizations because of insufficient data/redirects:
- Україна 24/7 - новини
- Інсайдер ЗСУ

## Preliminary temporal pattern

For five non-media channels whose analysis files were downloadable and re-aggregated, annual reproduction shares were approximately:
- 2020: 11.9% (N=2,556)
- 2021: 17.1% (N=5,917)
- 2022: 23.9% (N=65,507)
- 2023: 38.9% (N=59,138)
- 2024: 43.3% (N=66,905)
- 2025: 34.5% (N=51,236)
- 2026 partial: 31.4% (N=15,213)

These are **not yet final article figures** because:
- they exclude Труха Україна and Україна Онлайн due connector file-size limits;
- channel composition changes over time;
- pooled annual trends can reflect entry/exit and changing activity rather than within-channel change.

A safer preliminary statement is that several channels show clear post-2022 increases, but the pattern is heterogeneous.

Within-channel 365-day pre/post comparison around 24 Feb 2022 for channels with data:
- Times of Ukraine: ~14.9% → ~46.8%
- Київ Інфо: ~21.0% → ~33.4%
- Лачен пише: ~21.9% → ~20.9%

This is evidence against a simplistic universal “war caused an increase in all channels” claim.

## Popularity / views

Telegram scraper stores:
- `views`
- `forwards`

Subscriber counts are not stored in the shown scraper code.

Views can be useful descriptively, but are not a clean longitudinal audience metric because they are cumulative snapshots at scrape time; older posts had more time to accumulate views, and the channel mix changes across years.

Preliminary median views for five channels showed a major post-2022 scale-up, but this should be described only as an indirect descriptive signal, not causal proof of audience growth.

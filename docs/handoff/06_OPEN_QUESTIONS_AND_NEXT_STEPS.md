# Open questions and next steps

Priority order matters. Do not rush to final prose before these are resolved.

## 1. Verify the professional media universe

Need to establish exactly which sources in `config/media_sources.json` belong to:
- IMI White List;
- Map of Recommended Media;
- both;
- neither.

Also record:
- date/version of each list used;
- exact counts;
- overlap.

This is essential because the article’s core claim depends on the definition of “professional media”.

## 2. Verify Telegram channel selection from Internews 2025

Need the exact primary Internews table/list showing popular Telegram channels and the rule used to select the 13 configured channels.

Record:
- criterion/ranking;
- date of report;
- whether any channels were manually added/removed;
- how channels later reclassified as online media (e.g. Труха Україна) are treated analytically.

## 3. Audit the media article corpus over time

Highest methodological risk.

For `media_all_articles.json` calculate:
- article count;
- min/max dates;
- monthly/yearly counts;
- counts by source;
- missing `publish_date` rate;
- whether dates reflect actual publication date or scrape time.

If the media article corpus does not cover 2020–2026 consistently, semantic similarity cannot be interpreted as a stable longitudinal measure across the whole period.

## 4. Reconcile “direct links” statistics

Investigate why `Link Only = 0` for all channels.

Need raw counts for:
- any media link;
- any media mention;
- any semantic match;
- overlap combinations.

## 5. Validate mention detection

Potential false positives for short/generic outlet names. Build a validation sample and quantify precision.

## 6. Validate semantic similarity

Manually code a sample around:
- 0.75–0.80 threshold band;
- >0.85 high-confidence matches;
- multiple years;
- multiple channels;
- official-source duplication cases.

If possible, two-author coding with agreement statistics.

## 7. Produce final temporal analysis

Preferred outputs:
- yearly and quarterly reproduction share;
- message count denominator;
- within-channel trends;
- pooled weighted trend;
- unweighted channel-average robustness check;
- pre/post 24 Feb 2022 comparison;
- confidence intervals where appropriate.

Control for changing channel composition.

## 8. Separate media-owned Telegram channels from core non-media analysis

Primary analysis: seven non-media channels.

Media-owned Telegram channels can be included as a comparison group, but not pooled into the primary headline percentage.

## 9. Decide treatment of views/forwards

Use only as secondary descriptive indicators unless a defensible normalization strategy is developed.

Do not use raw views as proof of audience growth without discussing snapshot-age bias.

## 10. Complete literature review and novelty audit

Search systematically for:
- Telegram + professional/legacy/traditional media;
- content reproduction / text reuse / news reuse;
- source attribution;
- intermedia agenda-setting;
- distributed news;
- Telegram Ukraine wartime;
- computational text reuse / semantic similarity in journalism research.

Only after this should novelty claims be finalized.

## 11. Write next article sections

After the methodological audit:
1. finalize Literature Review / Theory;
2. Methods;
3. Results;
4. Discussion;
5. Conclusions;
6. Abstract and keywords last.

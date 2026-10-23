# Перепис джерел у 7 немедійних каналах (евристика, 2026-10-23)

Частка повідомлень з текстом, у яких є хоч одне джерело даного типу (повідомлення може мати кілька типів).
`no_explicit_source` — не знайдено ні атрибуції в тексті, ні посилання. `list_media` — медіа з «білого списку» (детектор v2).
Пересилання (forward) не враховано: збирач даних не зберігав, звідки переслано повідомлення.
Посилання t.me не вважаються джерелом (це переважно реклама й «підпишись»); `telegram` — лише текстові атрибуції («— монітори», «місцеві канали»).

|                |   msgs_with_text |   no_explicit_source |   official_ua |   foreign_official |   ua_politicians_experts |   telegram |   list_media |   ua_media_other |   unnamed_media |   foreign_media |   russian |   social |   other_site |   unclassified |
|:---------------|-----------------:|---------------------:|--------------:|-------------------:|-------------------------:|-----------:|-------------:|-----------------:|----------------:|----------------:|----------:|---------:|-------------:|---------------:|
| truexanewsua   |            97406 |                 40.3 |          14   |                1.7 |                      1.6 |        2.2 |          3.1 |              4.3 |             1.3 |             4.1 |       1.2 |      4   |          8   |           33.9 |
| kievinfo_kyiv  |            48909 |                 64.5 |           6.4 |                0.3 |                      0.6 |        0.4 |          0.4 |              0.7 |             0.3 |             0.6 |       0.2 |      0.9 |          3.1 |           26.7 |
| UaOnlii        |            85282 |                 32.8 |          18.6 |                2.6 |                      2.7 |        3.4 |          1.5 |              2.5 |             3.2 |             5.4 |       2.3 |      2.4 |          4   |           35.2 |
| vanek_nikolaev |            36926 |                 69.8 |           1.3 |                0.1 |                      0   |        0.2 |          0.1 |              0.1 |             0   |             0   |       0   |      1.5 |          1.3 |           28.3 |
| lachentyt      |            49125 |                 50.9 |          15.5 |                2.1 |                      0.4 |        0.3 |          2.3 |              1.2 |             0.3 |             5.1 |       0.8 |      3   |          2.8 |           21.2 |
| times_ukraina  |            45495 |                 24.3 |          21.2 |                1.7 |                      2.5 |        6.5 |          2.1 |              2.1 |             3.5 |             5.8 |       2   |      2   |          2.9 |           38.3 |
| batalionmonako |            47488 |                 39.4 |          11.7 |                2.8 |                      2.3 |        2.4 |          2.5 |              3.8 |             1.9 |             4.2 |       1.3 |      3.2 |          7.4 |           34.1 |
| ALL (pooled)   |           410631 |                 43.7 |          13.6 |                1.8 |                      1.6 |        2.3 |          1.9 |              2.4 |             1.7 |             3.9 |       1.3 |      2.6 |          4.7 |           31.8 |

## По роках (разом)

|      |   no_explicit_source |   official_ua |   foreign_official |   ua_politicians_experts |   telegram |   list_media |   ua_media_other |   unnamed_media |   foreign_media |   russian |   social |   other_site |   unclassified |
|-----:|---------------------:|--------------:|-------------------:|-------------------------:|-----------:|-------------:|-----------------:|----------------:|----------------:|----------:|---------:|-------------:|---------------:|
| 2020 |                 53.3 |           5.1 |                0.1 |                      0.4 |        0.4 |          2.4 |              0.8 |             0.1 |             0.1 |       0.1 |      2.3 |          5.7 |           35.6 |
| 2021 |                 47.9 |           7.1 |                0.2 |                      0.7 |        0.7 |          3   |              2.3 |             0.3 |             0.3 |       0.3 |      4.1 |          8.4 |           38.7 |
| 2022 |                 59.1 |          10.1 |                0.9 |                      1.1 |        0.5 |          1   |              1   |             0.4 |             2.4 |       0.8 |      1.6 |          2.2 |           25   |
| 2023 |                 43.3 |          16.1 |                1   |                      0.9 |        1.1 |          2.4 |              2.8 |             0.6 |             3.7 |       1.4 |      2.3 |          4.2 |           32.7 |
| 2024 |                 36.8 |          16.8 |                1.1 |                      2.3 |        3.3 |          2.4 |              3.2 |             1.8 |             4.5 |       1.4 |      2.9 |          6   |           35.1 |
| 2025 |                 32   |          14   |                4.6 |                      2.4 |        4.9 |          1.9 |              3.3 |             3.8 |             6.5 |       2.1 |      3.6 |          6.2 |           34   |
| 2026 |                 29.1 |          17.4 |                3.1 |                      2.2 |        5   |          1.9 |              3   |             5.4 |             4.9 |       1.1 |      3.6 |          6.1 |           35.1 |

## Найчастіші атрибуції (перші 80)

| category               | attributed_to               |   count |
|:-----------------------|:----------------------------|--------:|
| official_ua            | Зеленський                  |    9777 |
| telegram               | монітори                    |    5046 |
| unnamed_media          | ЗМІ                         |    4725 |
| official_ua            | ПС                          |    3961 |
| foreign_official       | Трамп                       |    3808 |
| unnamed_media          | місцеві ЗМІ                 |    3770 |
| russian                | росЗМІ                      |    3256 |
| foreign_media          | Reuters                     |    3152 |
| official_ua            | ОВА                         |    3086 |
| foreign_media          | Bloomberg                   |    2004 |
| telegram               | місцеві канали              |    1977 |
| official_ua            | Генштаб                     |    1649 |
| official_ua            | Укренерго                   |    1548 |
| foreign_media          | CNN                         |    1149 |
| official_ua            | КМВА                        |    1079 |
| list_media             | Суспільне                   |    1059 |
| official_ua            | Кличко                      |    1005 |
| foreign_media          | Politico                    |    1005 |
| ua_politicians_experts | Арестович                   |     962 |
| official_ua            | ГУР                         |     864 |
| official_ua            | ДСНС                        |     829 |
| unclassified           | ДТЕК                        |     783 |
| official_ua            | Нацполіція                  |     762 |
| russian                | путін                       |     757 |
| official_ua            | ДПСУ                        |     725 |
| foreign_media          | WSJ                         |     705 |
| official_ua            | Міноборони                  |     689 |
| foreign_media          | ISW                         |     678 |
| official_ua            | Буданов                     |     629 |
| foreign_media          | Forbes                      |     620 |
| official_ua            | поліція                     |     615 |
| foreign_official       | Білий дім                   |     612 |
| foreign_media          | The Guardian                |     608 |
| list_media             | УП                          |     605 |
| unclassified           | Повітряний простір України  |     597 |
| unnamed_media          | СМИ                         |     588 |
| unclassified           | соцмережі                   |     587 |
| foreign_media          | NYT                         |     586 |
| official_ua            | СБУ                         |     581 |
| official_ua            | Зеленский                   |     577 |
| telegram               | моніторингові канали        |     577 |
| foreign_media          | FT                          |     560 |
| ua_politicians_experts | Гончаренко                  |     549 |
| foreign_media          | The Telegraph               |     547 |
| official_ua            | Шмигаль                     |     537 |
| official_ua            | МВС                         |     531 |
| telegram               | МОНІТОРУКРАЇНА              |     526 |
| unclassified           | Єрмак                       |     521 |
| foreign_media          | Financial Times             |     492 |
| foreign_media          | Axios                       |     488 |
| telegram               | радар Times of Ukraine      |     488 |
| ua_media_other         | РБК-Україна                 |     484 |
| telegram               | DeepState                   |     461 |
| official_ua            | ДБР                         |     461 |
| official_ua            | Федоров                     |     458 |
| foreign_media          | The New York Times          |     438 |
| unclassified           | Подоляк                     |     427 |
| foreign_media          | BILD                        |     418 |
| telegram               | підписники Times of Ukraine |     417 |
| official_ua            | КМДА                        |     414 |
| official_ua            | Міненерго                   |     406 |
| telegram               | місцеві пабліки             |     405 |
| foreign_media          | The Times                   |     403 |
| ua_politicians_experts | нардеп Железняк             |     402 |
| official_ua            | мер                         |     398 |
| official_ua            | ОП                          |     398 |
| foreign_media          | Sky News                    |     395 |
| foreign_media          | Bild                        |     388 |
| official_ua            | Володимир Зеленський        |     377 |
| russian                | росСМИ                      |     376 |
| unclassified           | Daily Mail                  |     357 |
| foreign_official       | Пентагон                    |     356 |
| ua_media_other         | ТСН                         |     351 |
| ua_politicians_experts | Железняк                    |     346 |
| unclassified           | 31К                         |     340 |
| foreign_media          | The Washington Post         |     337 |
| unclassified           | Свириденко                  |     318 |
| unclassified           | до перемоги                 |     315 |
| ua_politicians_experts | нардеп Гончаренко           |     313 |
| unclassified           | Пєсков                      |     313 |

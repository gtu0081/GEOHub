# Migration Source Ledger

Read-only source baseline: `yaojingang/yao-geo-skills` commit `201c0c45dcf09bb37bc46a467b4baf4d721db205`. The 21 source skills map as follows.

| # | Source skill | Destination | Decision |
| ---: | --- | --- | --- |
| 1 | yao-geo-intent-miner | geo-discover | implemented |
| 2 | yao-geo-panorama-audit | geo-diagnose | implemented |
| 3 | yao-geo-page-audit | geo-diagnose | implemented |
| 4 | yao-geo-title-optimizer | geo-content | implemented |
| 5 | yao-geo-explainer-builder | geo-content | implemented |
| 6 | yao-geo-comparison-builder | geo-content | implemented |
| 7 | yao-geo-ranking-article-builder | geo-content | implemented |
| 8 | yao-geo-page-blueprint | geo-content | implemented |
| 9 | yao-geo-content-refiner | geo-content | implemented |
| 10 | yao-geo-article-friendly | geo-content | implemented |
| 11 | yao-geo-knowledge-base-builder | geo-knowledge | planned |
| 12 | yao-geo-brand-graph | geo-knowledge | planned |
| 13 | yao-geo-execution-roadmap | geo-strategy | planned |
| 14 | yao-geo-effect-monitor | geo-measure | planned |
| 15 | yao-geo-tracking | geo-measure | planned |
| 16 | yao-chatgpt-crawler | excluded | connector/crawler boundary |
| 17 | yao-deepseek-crawler | excluded | connector/crawler boundary |
| 18 | yao-doubao-crawler | excluded | connector/crawler boundary |
| 19 | yao-geoflow-cli | excluded | GEOFlow boundary |
| 20 | yao-geoflow-design | excluded | GEOFlow boundary |
| 21 | yao-geoflow-template | excluded | GEOFlow boundary |

Publishing remains a planned registry domain even though the baseline has no standalone publish package. Local Explainer and Ranking work improved the deliverable into “内容主体 + 补充说明与参考来源”; this behavior informed `geo-content` while preserving evidence limitations. No historical customer reports, font files, or generated outputs were copied.

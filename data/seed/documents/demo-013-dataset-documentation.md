---
title: "Demo Indicator Dataset: Documentation and Provenance (DEMO)"
authors: ["Platform Team"]
organization: "SIH26019 Prototype Team"
publication_date: 2025-01-10
document_type: dataset_description
authority_level: demo
state_code: null
geography_label: "Demo geography (four states)"
topics: ["Data quality", "Indicators"]
source_url: ""
is_demo: true
provenance_note: "Describes the synthetic indicator dataset shipped with the prototype."
---
# Purpose
This document describes the indicator dataset used by the map and scenario modules in the prototype. All indicator values are synthetic demonstration data and are labelled DEMO / SYNTHETIC DATA wherever they appear.

<!-- page: 2 -->
## Indicators
The dataset contains district-level values by year for digitization coverage, pending land-dispute pressure index, climate vulnerability index, agricultural land share and mutation processing time. Values were generated with a seeded random process with plausible trends and have no relationship to real district statistics. District areas on the map are schematic tiles, not survey boundaries.

## Replacing demo data
To use official statistics, ingest a dataset with its source organization, licence and publication date, mark the data source as non-demo, and re-import observations. The interface then removes the DEMO label from the affected indicators.

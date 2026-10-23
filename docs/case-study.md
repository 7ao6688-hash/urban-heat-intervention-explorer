# Glasgow case study and evidence boundary

This portfolio case study rebuilds an MSc coursework analysis of Glasgow's land-surface temperature, greenness and land cover. The original study used Landsat 8 imagery acquired on 28 June 2019, ENVI-based LST/NDVI processing, a four-class land-cover classification and 200 random samples.

The public version keeps the case-specific question - how urban greenness and land-cover composition relate to daytime surface heat in Glasgow - while adding reproducible Python analysis, statistical rules, bootstrap uncertainty and tests.

The observed analysis lives in [`case-studies/glasgow-2019`](../case-studies/glasgow-2019/). It commits a boundary-clipped scene derived from public-domain Landsat 8 data plus the resulting maps and tables. The boundary file itself, the full-scene coursework rasters and the original coursework maps are not redistributed. The dashboard and the quick-start demo remain synthetic. This repository is not an official Glasgow City Council product, and LST must not be interpreted as air temperature or heat-health risk.

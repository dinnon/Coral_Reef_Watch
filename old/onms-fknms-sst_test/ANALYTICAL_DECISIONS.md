# FKNMS pilot decisions

- Inventory each native 0.05° CoralTemp grid-cell center inside the NOAA FKNMS polygon. Exclude holes and cells whose centers lie outside. Keep counts for polygon parts with no interior center.
- Pull `sea_surface_temperature` in quarterly time blocks and approximately one-degree latitude bands; retry historical quarters by month if needed. Start with recent data; resume completed checkpoints. Publish the summary only after all historical blocks succeed.
- Use OceanWatch CoralTemp v3.1 first and CoastWatch's monthly dataset as fallback. Keep the actual dataset ID with each pixel observation; reject missing or out-of-range SST.
- Weight valid cell SST by cosine(latitude) for the monthly mean. Record minimum, maximum, valid count, inventory count, and data completeness. Keep fully masked months with blank SST.
- Calculate anomalies from the new FKNMS 1991–2020 same-calendar-month means when at least 20 reference years are present. Do not splice in the old two-cell FKNMS history.
- Check geographic cell placement, zero-center polygon parts, low-coverage months, and example NOAA cell values before scientific use.

# Qafila gross margin



Submitted by: Asyah Saad Alqahtani — academy: @SDAIAAcademy

The task, rules and grading are in [BRIEF.md](BRIEF.md).

```bash
uv sync
uv run python tools/make_data.py          # data/
uv run python run.py                      # data/ -> warehouse/ (DuckDB + Iceberg)
uv run python tools/check.py              # contract self-check
```



## Design

Supplier CSV files and SQLite data → raw tables (Python and DuckDB) → staging (dbt) → silver cost history (dbt) → gold weekly margins (dbt) → Apache Iceberg tables (PyIceberg).

|Model|Layer|Grain (one row per ...)|Materialization|
|-|-|-|-|
|stg\_products|staging|Product|View|
|product\_cost\_history|silver|SKU and cost version|DuckDB view, published to Iceberg|
|weekly\_margin|gold|ISO week, city, and category|DuckDB view, published to Iceberg|
|price\_quarantine|quality|Invalid supplier price record|DuckDB view, published to Iceberg|

**How the SCD2 history is built:** Each SKU has a cost history with valid\_from and valid\_to dates. Missing weeks keep the previous cost, and unchanged costs do not create new versions. The correction file takes priority over the original file for the same week, and a new version is created only when the cost changes.

**How each order line finds its cost:** Each order line is matched to the product SKU and the supplier cost that was valid on the order date. If no valid cost is available, the line is counted as uncosted instead of assigning an incorrect cost.



## Data problems I found

|Problem|Where|Rows affected|What I did|
|-|-|-|-|
|<br />Invalid supplier costs<br /><br />Unknown product SKUs <br />|<br />Supplier CSV files<br /><br />Supplier CSV files<br />|4 rows<br /><br />3 rows|Excluded invalid costs from calculations and recorded them in price\_quarantine.<br /><br />Quarantined unknown SKUs with reason unknown\_sku.|

## Tests

|Test|On|What it protects against|
|-|-|-|
|Unique order IDs<br />Not-null order IDs<br />Unique product IDs and SKUs<br />Not-null product IDs and SKUs<br />Unique and not-null store IDs<br />Not-null SKU and cost<br />SCD2 history checks<br />Margin reconciliation<br />Quarantine validation <br />Iceberg output checks|dbt staging<br />dbt staging<br />dbt staging<br />dbt staging<br />dbt staging<br />dbt silver<br />tools/check.py<br />tools/check.py<br />tools/check.py<br />tools/check.py|Duplicate orders<br />Missing order identifiers<br />Duplicate product records<br />Missing product information<br />Duplicate or missing stores<br />Incomplete cost history<br />Overlapping versions, invalid costs, and unnecessary versions <br />Incorrect revenue, costs, or margins<br />Invalid supplier rows entering calculations Missing tables or incorrect output columns|

## 

The pipeline passed 18/18 dbt operations, including 10 data tests. The official checker returned 22/22 checks passed on both the original dataset and a second dataset generated with seed 11.



## Re-runs and the correction



Running the pipeline again with unchanged data produced `Unchanged` for all three Iceberg tables. This was verified on both the original dataset and the dataset generated with seed 11.



After applying the late supplier correction, the older Iceberg snapshot (ID: 5048413883765148226) showed a total margin of SAR 801,016.88. The updated margin was SAR 803,515.80, an increase of SAR 2,498.92. The older snapshot remained available for time-travel queries.



## What I'd do next

With 100× more data, processing the full dataset on every run would become slower. I would use incremental processing to handle only new or changed records. If supplier files arrived daily, I would add checks for missing files and late corrections.





## AI assistance

I used Ai to understand technical concepts, get help with coding errors, and troubleshoot issues during testing. I ran the project and verified the results locally.


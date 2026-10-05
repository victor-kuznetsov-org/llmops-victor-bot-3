# Databricks notebook source
# MAGIC %md
# MAGIC # Lecture 1.3: arXiv Data Ingestion with Databricks Connect

# COMMAND ----------

from datetime import UTC, datetime
from pathlib import Path

import arxiv
from databricks.connect import DatabricksSession
from pyspark.sql.types import ArrayType, LongType, StringType, StructField, StructType

from arxiv_curator.config import ProjectConfig

# Profile comes from DATABRICKS_CONFIG_PROFILE (student-bot-3)
spark = DatabricksSession.builder.profile("student-bot-3").serverless(True).getOrCreate()
print(f"Spark version: {spark.version}")

# COMMAND ----------

cfg = ProjectConfig.from_yaml(str(Path(__file__).parent.parent / "project_config.yml"), "dev")
CATALOG = cfg.catalog
SCHEMA = cfg.schema
TABLE_NAME = "arxiv_papers"
print(f"Unity Catalog: {CATALOG}.{SCHEMA}.{TABLE_NAME}")

# COMMAND ----------


def fetch_arxiv_papers(query: str = "cat:cs.AI OR cat:cs.LG", max_results: int = 100):
    """Fetch recent arXiv papers with the arxiv package."""
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    papers = []
    for result in client.results(search):
        papers.append(
            {
                "arxiv_id": result.entry_id.split("/")[-1],
                "title": result.title,
                "authors": [a.name for a in result.authors],
                "summary": result.summary,
                "published": int(result.published.strftime("%Y%m%d%H%M")),
                "updated": result.updated.isoformat() if result.updated else None,
                "categories": ", ".join(result.categories),
                "pdf_url": result.pdf_url,
                "primary_category": result.primary_category,
                "ingestion_timestamp": datetime.now(UTC).isoformat(),
                "processed": None,
                "volume_path": None,
            }
        )
    return papers


papers = fetch_arxiv_papers(max_results=50)
print(f"Fetched {len(papers)} papers")
print(papers[0]["title"], papers[0]["arxiv_id"])

# COMMAND ----------

schema = StructType(
    [
        StructField("arxiv_id", StringType(), False),
        StructField("title", StringType(), False),
        StructField("authors", ArrayType(StringType()), True),
        StructField("summary", StringType(), True),
        StructField("published", LongType(), True),
        StructField("updated", StringType(), True),
        StructField("categories", StringType(), True),
        StructField("pdf_url", StringType(), True),
        StructField("primary_category", StringType(), True),
        StructField("ingestion_timestamp", StringType(), True),
        StructField("processed", LongType(), True),
        StructField("volume_path", StringType(), True),
    ]
)

df = spark.createDataFrame(papers, schema=schema)
table_path = f"{CATALOG}.{SCHEMA}.{TABLE_NAME}"
df.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(table_path)
print(f"Created Delta table: {table_path}, records: {df.count()}")

# COMMAND ----------

papers_df = spark.table(table_path)
papers_df.printSchema()
papers_df.select("arxiv_id", "title", "primary_category", "published").show(5, truncate=50)
papers_df.groupBy("primary_category").count().orderBy("count", ascending=False).show()

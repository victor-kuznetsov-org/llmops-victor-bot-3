# Databricks notebook source
# MAGIC %md
# MAGIC # Lecture 2.2: PDF parsing with ai_parse_document (stops before the chunks)

# COMMAND ----------

import os
import tempfile
import time
from pathlib import Path

import arxiv
from databricks.connect import DatabricksSession
from databricks.sdk import WorkspaceClient
from loguru import logger
from pyspark.sql import functions as F
from pyspark.sql import types as T

from arxiv_curator.config import ProjectConfig

spark = DatabricksSession.builder.profile("student-bot-3").serverless(True).getOrCreate()
w = WorkspaceClient(profile="student-bot-3")
cfg = ProjectConfig.from_yaml(str(Path(__file__).parent.parent / "project_config.yml"), "dev")
catalog, schema, volume = cfg.catalog, cfg.schema, cfg.volume
metadata_table = f"{catalog}.{schema}.arxiv_papers"

# COMMAND ----------

papers_df = spark.table(metadata_table)
unprocessed = papers_df.filter(F.col("processed").isNull())
print(f"Total papers: {papers_df.count()}, unprocessed: {unprocessed.count()}")
papers_to_process = unprocessed.limit(3).collect()

# COMMAND ----------

# Download locally, then upload with the Files API (/Volumes does not exist on the laptop)
end = time.strftime("%Y%m%d%H%M", time.gmtime())
vol_dir = f"/Volumes/{catalog}/{schema}/{volume}/{end}"
tmp = tempfile.mkdtemp()
client = arxiv.Client()
records = []
for row in papers_to_process:
    pid = row.arxiv_id
    try:
        paper = next(client.results(arxiv.Search(id_list=[pid])))
        paper.download_pdf(dirpath=tmp, filename=f"{pid}.pdf")
        with open(os.path.join(tmp, f"{pid}.pdf"), "rb") as f:
            w.files.upload(f"{vol_dir}/{pid}.pdf", f, overwrite=True)
        records.append({"paper_id": pid, "processed": int(end), "volume_path": f"{vol_dir}/{pid}.pdf"})
        print(f"uploaded {pid}")
    except Exception as e:
        logger.warning(f"Paper {pid} was not processed: {e}")
    time.sleep(3)

# COMMAND ----------

if records:
    upd_schema = T.StructType(
        [
            T.StructField("paper_id", T.StringType(), False),
            T.StructField("processed", T.LongType(), True),
            T.StructField("volume_path", T.StringType(), True),
        ]
    )
    spark.createDataFrame(records, schema=upd_schema).createOrReplaceTempView("pdf_updates")
    spark.sql(f"""
        MERGE INTO {metadata_table} target USING pdf_updates source
        ON target.arxiv_id = source.paper_id
        WHEN MATCHED THEN UPDATE SET target.processed = source.processed,
                                     target.volume_path = source.volume_path
    """)

    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.{schema}.ai_parsed_docs (
            path STRING, parsed_content STRING, processed LONG)
    """)
    spark.sql(f"""
        INSERT INTO {catalog}.{schema}.ai_parsed_docs
        SELECT path, CAST(ai_parse_document(content) AS STRING) AS parsed_content, {end} AS processed
        FROM READ_FILES("{vol_dir}", format => 'binaryFile')
    """)
    spark.table(f"{catalog}.{schema}.ai_parsed_docs").select("path", "processed").show(truncate=80)

# COMMAND ----------

# Stopping here: no chunks, no arxiv_chunks table.

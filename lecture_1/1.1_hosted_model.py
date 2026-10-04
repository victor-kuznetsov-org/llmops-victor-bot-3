# Databricks notebook source
# MAGIC %md
# MAGIC # Lecture 1.1: Hosted model through the course AI Gateway

# COMMAND ----------

from pathlib import Path

import yaml
from databricks_openai import DatabricksOpenAI

cfg = yaml.safe_load((Path(__file__).parent.parent / "project_config.yml").read_text())["dev"]

client = DatabricksOpenAI(use_ai_gateway=True)

# COMMAND ----------

response = client.chat.completions.create(
    model=cfg["llm_endpoint"],
    messages=[
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Explain LLMOps in 3 sentences."},
    ],
    max_tokens=200,
    temperature=0.7,
)

print("Response:")
print(response.choices[0].message.content)
print(f"\nTokens used: {response.usage.total_tokens}")
print(f"Input tokens: {response.usage.prompt_tokens}")
print(f"Output tokens: {response.usage.completion_tokens}")

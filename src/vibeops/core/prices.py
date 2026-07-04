from __future__ import annotations

# OpenAI token pricing (USD per 1K tokens), used by the LLM client to estimate
# spend on the bring-your-own-key OpenAI calls. GCP VM/GPU pricing lives in
# vibeops.cost.pricing_constants — not here.
PRICES_AS_OF = "2025-01"

GPT_4O_MINI_INPUT_PER_1K: float = 0.00015
GPT_4O_MINI_OUTPUT_PER_1K: float = 0.00060

GPT_4O_INPUT_PER_1K: float = 0.00250
GPT_4O_OUTPUT_PER_1K: float = 0.01000

"""One-time setup script: embeds the Indian law knowledge base and loads it
into Supabase's `law_sections` table.

Run this once after applying supabase/schema.sql and setting
SUPABASE_SERVICE_ROLE_KEY + HUGGINGFACE_API_KEY:

    cd legal-ai-v2
    python -m scripts.index_law_kb
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.indian_law_kb import index_law_knowledge

if __name__ == "__main__":
    count = index_law_knowledge()
    print(f"Indexed {count} law sections into Supabase.")

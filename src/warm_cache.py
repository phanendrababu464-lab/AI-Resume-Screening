"""Resolve a complete pinned embedding snapshot with a bounded download."""

import os
from pathlib import Path

from src.config import EMBEDDING_MODEL_NAME, EMBEDDING_REVISION

ARTIFACTS = (
    "1_Pooling/config.json",
    "config.json",
    "config_sentence_transformers.json",
    "model.safetensors",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
)


def ensure_embedding_snapshot() -> str:
    """Reuse a complete local snapshot before downloading missing artifacts."""
    # Streaming HTTP avoids starting the parallel Xet downloader in a small web instance.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        cached = Path(snapshot_download(EMBEDDING_MODEL_NAME, revision=EMBEDDING_REVISION, local_files_only=True))
        if all((cached / name).is_file() for name in ARTIFACTS):
            return str(cached)
    except LocalEntryNotFoundError:
        pass

    return snapshot_download(
        EMBEDDING_MODEL_NAME,
        revision=EMBEDDING_REVISION,
        allow_patterns=ARTIFACTS,
        max_workers=1,
    )


if __name__ == "__main__":
    os.environ["HF_HUB_OFFLINE"] = "0"
    ensure_embedding_snapshot()

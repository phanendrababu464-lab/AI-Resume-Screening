"""Fetch the pinned model artifacts at build time, without importing PyTorch."""

import os

os.environ["HF_HUB_OFFLINE"] = "0"

from huggingface_hub import snapshot_download

from src.config import EMBEDDING_MODEL_NAME, EMBEDDING_REVISION

if __name__ == "__main__":
    snapshot_download(
        EMBEDDING_MODEL_NAME,
        revision=EMBEDDING_REVISION,
        allow_patterns=["*.json", "*.txt", "model.safetensors"],
        ignore_patterns=["onnx/*", "openvino/*"],
    )

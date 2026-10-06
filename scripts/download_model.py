#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Download a Transformers-format SAM3 model after Hugging Face authorization."""

import argparse

from huggingface_hub import snapshot_download


def main():
    """Use the existing login or HF_TOKEN without printing credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="facebook/sam3")
    parser.add_argument("--revision", default=None)
    parser.add_argument("--output", help="Optional directory for portable offline deployment")
    args = parser.parse_args()
    path = snapshot_download(
        repo_id=args.model_id, revision=args.revision, local_dir=args.output,
        allow_patterns=["*.json", "*.txt", "*.safetensors"],
        ignore_patterns=["*tracker*", "*video*"],
    )
    print(f"Model directory: {path}")
    print("Use model_id:=<this directory> local_files_only:=true for offline deployment.")


if __name__ == "__main__":
    main()

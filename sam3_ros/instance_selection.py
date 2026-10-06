# SPDX-License-Identifier: Apache-2.0
"""Pure confidence filtering helpers for SAM3 prompt instances."""

import numpy as np


def select_instance_indices(
    scores: np.ndarray,
    *,
    absolute_threshold: float,
    relative_threshold: float,
    max_instances: int,
) -> np.ndarray:
    """Keep a bounded, confidence-relative set of prompt instances."""
    flat_scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    if flat_scores.size == 0:
        return np.empty(0, dtype=np.int64)
    best_score = float(np.max(flat_scores))
    threshold = max(
        float(absolute_threshold),
        best_score * max(float(relative_threshold), 0.0),
    )
    indices = np.flatnonzero(flat_scores >= threshold)
    if indices.size == 0:
        return indices.astype(np.int64)
    order = np.argsort(flat_scores[indices])[::-1]
    limit = max(int(max_instances), 1)
    return indices[order[:limit]].astype(np.int64)

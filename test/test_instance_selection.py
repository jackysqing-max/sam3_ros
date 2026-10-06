# SPDX-License-Identifier: Apache-2.0
"""Confidence filtering regression tests extracted with the ROS wrapper."""

import numpy as np

from sam3_ros.instance_selection import select_instance_indices


def test_instance_selection_applies_relative_threshold_and_limit():
    scores = np.asarray([0.90, 0.60, 0.19, 0.18, 0.05])

    selected = select_instance_indices(
        scores,
        absolute_threshold=0.05,
        relative_threshold=0.20,
        max_instances=3,
    )

    assert selected.tolist() == [0, 1, 2]


def test_instance_selection_does_not_promote_below_absolute_threshold():
    selected = select_instance_indices(
        np.asarray([0.04, 0.03]),
        absolute_threshold=0.05,
        relative_threshold=0.20,
        max_instances=16,
    )

    assert selected.size == 0


def test_empty_instance_list():
    selected = select_instance_indices(
        np.asarray([]), absolute_threshold=0.3, relative_threshold=0.2, max_instances=16,
    )
    assert selected.size == 0
    assert selected.dtype == np.int64


def test_relative_threshold_excludes_weak_instances():
    selected = select_instance_indices(
        np.asarray([0.1, 0.9, 0.4]), absolute_threshold=0.0,
        relative_threshold=0.5, max_instances=16,
    )
    assert selected.tolist() == [1]


def test_select_highest_scores_before_instance_limit():
    selected = select_instance_indices(
        np.asarray([0.4, 0.9, 0.7]), absolute_threshold=0.3,
        relative_threshold=0.0, max_instances=2,
    )
    assert selected.tolist() == [1, 2]

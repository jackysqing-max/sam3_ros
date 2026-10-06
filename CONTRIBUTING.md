# Contributing

Open an issue or pull request with the ROS distribution, Python/model dependency
versions, reproduction steps, and expected versus observed behavior.

Run the unit tests in [README](README.md) for image conversion and selection changes.
For runtime changes, also build the package and run `scripts/smoke_test.py` with your
authorized local SAM3 model. Public CI validates unit tests and ROS package building;
it does not download gated weights or claim GPU runtime coverage.

Keep public examples camera-independent. Do not commit model weights, authentication
files, ROS bags, or experiment datasets. Contributions are under Apache-2.0.

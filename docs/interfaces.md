# ROS interfaces

## Executables

| Executable | Purpose |
| --- | --- |
| `sam3_mask_node` | Text-guided SAM3 image segmentation. |
| `sam3_image_file_node` | Publish a local image for demos; parameters `image_path`, `image_topic` (default `/image_raw`), `frame_id` (default `camera_optical_frame`), `publish_hz` (default `1.0`). |

## Topics and QoS

| Direction | Default topic | Type | QoS / meaning |
| --- | --- | --- | --- |
| Input | `/image_raw` | `sensor_msgs/msg/Image` | Best effort, volatile, depth 1. `rgb8`/`bgr8`, including row padding. |
| Input | `/sam3/prompt` | `std_msgs/msg/String` | Reliable, volatile, depth 10. Accepts ordinary CLI and transient-local publishers; history before node subscription is not replayed. Empty/unchanged prompts ignored. |
| Output | `/sam3/mask` | `sensor_msgs/msg/Image` | Reliable, volatile, depth 1. `mono8`, 0 background / 255 foreground. Original dimensions and image header. |
| Output | `/sam3/score` | `std_msgs/msg/Float32` | Reliable, volatile, depth 1. Best model confidence before filtering; 0 if no instances. No header. |
| Output | `/sam3/active_prompt` | `std_msgs/msg/String` | Reliable, transient local, depth 1. Current accepted prompt; also periodically republished. |

ROS QoS reliability rules allow a best-effort image subscriber to receive from
either a best-effort or a reliable camera publisher. A reliable prompt subscriber
requires a reliable publisher. To read the latched prompt immediately:

```bash
ros2 topic echo /sam3/active_prompt std_msgs/msg/String --qos-durability transient_local
```

## Startup parameters

All parameters below are read-only after node startup. Runtime prompt changes use
the topic; other changes require restarting the node with updated YAML/arguments.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `image_topic` | `/image_raw` | Raw RGB/BGR input. |
| `mask_topic` | `/sam3/mask` | Union mask output. |
| `score_topic` | `/sam3/score` | Best score output. |
| `prompt_topic` | `/sam3/prompt` | Runtime prompt input. |
| `active_prompt_topic` | `/sam3/active_prompt` | Accepted prompt output. |
| `prompt` | `glasses` | Initial nonempty text prompt. |
| `model_id` | `facebook/sam3` | Hub model ID or local Transformers model directory. |
| `model_revision` | empty | Optional immutable Hub commit/tag; empty uses default revision. |
| `local_files_only` | `false` | Prevent downloads during model loading. |
| `device` | `cpu` | `cpu`, `auto`, `cuda`, or `cuda:N`; unavailable CUDA falls back to CPU. |
| `use_amp` | `true` | CUDA float16 autocast; CPU always uses normal precision. |
| `score_th` | `0.3` | Absolute instance confidence threshold, in [0,1]. |
| `relative_score_th` | `0.2` | Relative threshold multiplied by the best confidence, in [0,1]. |
| `max_instances` | `16` | Maximum number of retained instances, positive integer. |
| `mask_th` | `0.5` | Mask probability cutoff, in [0,1]. |
| `max_side` | `640` | Resize input before processor; longest side limit, positive integer. Not the model's internal resolution. |
| `infer_hz` | `0.5` | Maximum inference start rate, positive float. |
| `prompt_republish_sec` | `1.0` | Active prompt broadcast interval; 0 disables periodic broadcasts. |

Keep confidence `s` if `s >= max(score_th, best_score * relative_score_th)`, sort by
confidence, retain at most `max_instances`, and union their masks. No retained instances
produce an all-zero mask. `/sam3/score` can therefore be positive while the mask is empty.
The mask is resized back with nearest-neighbor interpolation and keeps the source header.

## Launch configuration and multiple instances

The launch file exposes topic names, initial prompt, device, model ID/revision,
offline loading, inference rate, namespace, and `params_file`. Unspecified arguments
retain YAML values. Tune the remaining parameters through a custom YAML file:

```bash
cp config/sam3.yaml /tmp/my-sam3.yaml
# Edit score_th, max_instances, use_amp, etc. in /tmp/my-sam3.yaml.
ros2 launch sam3_ros sam3.launch.py params_file:=/tmp/my-sam3.yaml device:=cuda
```

Default topics are absolute. A namespace changes the node's name scope but does not
isolate those topics; provide separate topic names (or relative names) for each instance:

```bash
ros2 launch sam3_ros sam3.launch.py namespace:=front device:=cuda \
  image_topic:=/front/image_raw mask_topic:=/front/sam3/mask \
  score_topic:=/front/sam3/score prompt_topic:=/front/sam3/prompt \
  active_prompt_topic:=/front/sam3/active_prompt
```

Changing the prompt increments a generation counter. Any inference from an earlier
generation is discarded, including an A → B → A change while inference is running.
Publication and prompt acceptance share a lock. Across separate DDS topics, delivery
order is not guaranteed and previously published messages may still be in transit.

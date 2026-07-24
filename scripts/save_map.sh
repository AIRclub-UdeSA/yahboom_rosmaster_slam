#!/usr/bin/env bash
# Save the currently built slam_toolbox map to disk via nav2_map_server.
#
# Usage: save_map.sh [output_path_without_extension]
# Default output_path is ./map (writes map.yaml and map.pgm).

set -euo pipefail

OUTPUT_PATH="${1:-./map}"

ros2 run nav2_map_server map_saver_cli -f "${OUTPUT_PATH}"
echo "Saved map to ${OUTPUT_PATH}.yaml and ${OUTPUT_PATH}.pgm"

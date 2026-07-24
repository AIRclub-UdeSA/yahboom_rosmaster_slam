#!/usr/bin/env bash
# Serialize slam_toolbox's in-memory pose-graph to disk, for later use with
# localization.launch.py's map_file_name argument.
#
# Unlike save_map.sh (which exports a static pgm/yaml raster via
# nav2_map_server), this writes slam_toolbox's own <path>.posegraph and
# <path>.data files. Run this against a mapping session started by
# slam.launch.py, once you're happy with the built map.
#
# CAVEAT (slam_toolbox behavior, not this script): the file is written
# relative to the *slam_toolbox node's* working directory -- i.e. wherever
# you ran `ros2 launch yahboom_rosmaster_slam slam.launch.py` from, not
# wherever you run this script from, and NOT as an absolute path (slam_toolbox
# concatenates its cwd onto whatever filename you give it, even an absolute
# one, so absolute paths silently resolve to the wrong place). Use a bare
# filename with no directory component, and re-use that same directory when
# launching localization.launch.py.
#
# Usage: serialize_map.sh [output_path_without_extension]
# Default output_path is ./map (writes map.posegraph and map.data).

set -euo pipefail

OUTPUT_PATH="${1:-./map}"

# `ros2 service call` itself exits 0 as long as it got *any* response -- it does not
# inspect the response payload. SerializePoseGraph's own result field is what actually
# says whether the write succeeded (RESULT_SUCCESS=0, RESULT_FAILED_TO_WRITE_FILE=255),
# so that has to be parsed out of the response text explicitly.
RESPONSE="$(ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
  "{filename: '${OUTPUT_PATH}'}")"
echo "${RESPONSE}"

if ! echo "${RESPONSE}" | grep -q 'result=0)'; then
  echo "Failed to serialize map to ${OUTPUT_PATH}.posegraph/${OUTPUT_PATH}.data" \
       "(see result code above; a common cause is no map data yet, or the cwd caveat" \
       "in this script's header)." >&2
  exit 1
fi
echo "Serialized map to ${OUTPUT_PATH}.posegraph and ${OUTPUT_PATH}.data"

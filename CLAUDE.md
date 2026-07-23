# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`yahboom_rosmaster_slam` is a ROS 2 (Humble) `ament_cmake` package providing basic 2D LiDAR SLAM
(`slam_toolbox`) for the Yahboom ROSMASTER X3 mecanum robot in the `yahboom_rosmaster` Gazebo
Fortress simulator. There is no compiled code — the package is entirely launch files, YAML config,
an RViz config, and one shell script, installed via CMake `install()` rules.

This repo is independent of `yahboom_rosmaster` (separate history/remote) but is built inside the
same ROS 2 workspace, linked in via a symlink at `~/rosmaster_ws/src/yahboom_rosmaster_slam` (it
does not need to be a real directory under the workspace). It does not modify `yahboom_rosmaster`.

## Build & workspace commands

This package cannot be built or run standalone — it must be symlinked into a ROS 2 workspace that
already has `yahboom_rosmaster` (the Gazebo simulator) built, alongside `ros-humble-slam-toolbox`
and `ros-humble-nav2-map-server`.

```bash
ln -s /path/to/yahboom_rosmaster_slam ~/rosmaster_ws/src/yahboom_rosmaster_slam
cd ~/rosmaster_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y --rosdistro humble
colcon build --symlink-install --packages-up-to yahboom_rosmaster_slam
source install/setup.bash
```

Every new terminal needs both overlays sourced (`/opt/ros/humble/setup.bash`, then
`~/rosmaster_ws/install/setup.bash`).

Run/launch:

```bash
ros2 launch yahboom_rosmaster_slam slam.launch.py                       # simulator + SLAM + RViz
ros2 launch yahboom_rosmaster_slam slam.launch.py start_simulator:=false  # SLAM only, simulator already running elsewhere
ros2 launch yahboom_rosmaster_slam slam.launch.py \
  world:="$(ros2 pkg prefix yahboom_rosmaster_gazebo)/share/yahboom_rosmaster_gazebo/worlds/cafe.world"
```

Verify SLAM is producing output:

```bash
ros2 topic hz /map
ros2 run tf2_ros tf2_echo map odom
```

Save the built map (writes `<path>.yaml` + `<path>.pgm`, consumable by `yahboom_rosmaster_navigation`):

```bash
ros2 run yahboom_rosmaster_slam save_map.sh ~/rosmaster_ws/my_map
```

Localize against a previously serialized map (see Architecture below for how mapping vs.
localization mode differ):

```bash
cd ~/rosmaster_ws   # map_file_name below is resolved relative to this directory
ros2 run yahboom_rosmaster_slam serialize_map.sh my_map   # while slam.launch.py is still mapping
ros2 launch yahboom_rosmaster_slam localization.launch.py \
  map_file_name:=my_map map_start_pose:="[0.0, 0.0, 0.0]"
```

There are no unit tests beyond `ament_lint_auto`/`ament_lint_common` (declared as `test_depend` in
`package.xml`, run via the standard `colcon test`). `.github/workflows/ci.yml` runs exactly that
(build + `colcon test`) on every push/PR, in a clean `ros:humble-ros-base` container, with
`yahboom_rosmaster_gazebo` skipped via `rosdep --skip-keys` (it's a separate, non-rosdep-indexed
sibling repo not needed to build or lint this package). Reproduce it locally with:

```bash
rosdep install --from-paths src --ignore-src -r -y --skip-keys yahboom_rosmaster_gazebo
colcon build --packages-select yahboom_rosmaster_slam
colcon test --packages-select yahboom_rosmaster_slam && colcon test-result --verbose
```

## Architecture

Everything is wired together by `launch/slam.launch.py`, which composes three pieces:

1. **Simulator** (optional, `start_simulator:=true` by default) — includes
   `yahboom_rosmaster_gazebo`'s `rosmaster_gazebo_fortress.launch.py` with its own RViz forced off,
   since this package supplies its own view.
2. **`slam_toolbox`** — `async_slam_toolbox_node`, parameterized from
   `config/slam_toolbox_params.yaml` plus `use_sim_time`. It consumes `/scan` and the
   `odom -> base_footprint` TF that the simulator already publishes (from `wheel_state_odometry.py`
   and the simulated LiDAR), and publishes `/map` plus the `map -> odom` TF. This package never
   touches `odom -> base_footprint` — that chain is owned entirely by the simulator.
3. **RViz** (optional, `open_rviz:=true` by default) — `rviz/slam_view.rviz`.

Frame/topic names in `config/slam_toolbox_params.yaml` (`odom_frame: odom`,
`base_frame: base_footprint`, `map_frame: map`, `scan_topic: /scan`) must match
`yahboom_rosmaster`'s published names exactly — this is the load-bearing contract between the two
repos, not something to change independently. `mode: mapping` is online async mapping only; for
Nav2-based navigation (path planning, `nav2_amcl`), combine a `save_map.sh` map with
`yahboom_rosmaster_navigation`'s Nav2 stack instead of this package.

Tuning notes baked into the params file, worth knowing before changing them:
- `minimum_travel_distance`/`minimum_travel_heading` (0.2/0.2) are lowered from stock (0.5/0.5)
  because the X3 is small and operates in tight indoor spaces.
- `max_laser_range: 12.0` is bounded well under the simulated LiDAR's 30 m range to keep rasterized
  maps a reasonable size for the empty/cafe worlds.

### Localization mode

`launch/localization.launch.py` mirrors `slam.launch.py` (same simulator/RViz composition) but runs
`slam_toolbox`'s `localization_slam_toolbox_node` against `config/slam_toolbox_localization_params.yaml`
instead of `async_slam_toolbox_node`. This is slam_toolbox's own native localization, not Nav2's
AMCL — no particle filter, no global relocalization. Two launch arguments are required (no
defaults, by design — see `map_file_name`/`map_start_pose` in the launch file): the serialized map
prefix and an initial `[x, y, yaw]` pose to seed scan-matching from.

Non-obvious things worth knowing before touching this:
- **`map_file_name` does not honor absolute paths.** slam_toolbox's serialization code
  concatenates the node's own working directory onto whatever filename you give it, even one that
  already starts with `/` — it never treats a leading `/` as "ignore cwd." Confirmed empirically
  (not just from docs) by launching with an absolute path and seeing slam_toolbox report a
  `<cwd>/<absolute path>` open failure. The practical implication: `cd` into the map's directory
  before running either `serialize_map.sh` or `localization.launch.py`, and always pass a bare
  filename. `scripts/serialize_map.sh` has the same constraint (it writes relative to the
  `slam_toolbox` **node's** cwd, i.e. wherever `slam.launch.py` was launched from — not wherever
  you happen to run the script from).
- **`localization_slam_toolbox_node` needs both `map_file_name` and `map_start_pose`** to load a
  map at startup; `map_file_name` alone throws `Map starting pose not specified` and never attempts
  to open the file. This is only documented via a commented-out example in slam_toolbox's stock
  `mapper_params_localization.yaml`, not spelled out in prose anywhere obvious.
- **Passing a launch argument as a `double_array` ROS parameter** (needed for `map_start_pose`)
  requires wrapping the `LaunchConfiguration` in
  `launch_ros.parameter_descriptions.ParameterValue(..., value_type=List[float])` — passing the
  substitution directly makes it a string parameter, which `slam_toolbox` will silently reject/misread.
- `scan_buffer_size` and `loop_match_minimum_chain_size` are lowered from the mapping params (10 →
  3, matching slam_toolbox's own stock localization defaults): localization correlates against a
  bounded local window of the already-loaded map rather than accumulating evidence to close loops
  across a whole new exploration session.
- `enable_interactive_mode` is dropped in the localization params (present in the mapping ones)
  since it only matters for the `SlamToolboxPlugin` RViz panel, which this repo's RViz view already
  excludes (see the RViz segfault note below).

`scripts/serialize_map.sh` wraps slam_toolbox's own `SerializePoseGraph` service (writes
`<name>.posegraph`/`<name>.data`) — a different artifact from `save_map.sh`'s `nav2_map_server`
pgm/yaml output, and not interchangeable with it. Only the serialized pose-graph works with
`localization.launch.py`.

`rviz/slam_view.rviz` intentionally **omits** the `RobotModel` display and slam_toolbox's
`SlamToolboxPlugin` panel — both reliably segfaulted RViz on Intel Iris Plus (Mesa/i915). Don't
re-add them without checking this still applies to the target GPU; TF axes + LaserScan already show
live pose without them.

## Repository layout

| Path | Contents |
|------|----------|
| `launch/slam.launch.py` | Mapping launch file: simulator (optional) + slam_toolbox mapping + RViz |
| `launch/localization.launch.py` | Localization launch file: simulator (optional) + slam_toolbox localization + RViz |
| `config/slam_toolbox_params.yaml` | slam_toolbox mapping-mode parameters tuned for the ROSMASTER X3 |
| `config/slam_toolbox_localization_params.yaml` | slam_toolbox localization-mode parameters tuned for the ROSMASTER X3 |
| `rviz/slam_view.rviz` | RViz view (Map, LaserScan, Odometry, TF — no RobotModel/SlamToolboxPlugin) |
| `scripts/save_map.sh` | Wrapper around `nav2_map_server`'s `map_saver_cli` (pgm/yaml) |
| `scripts/serialize_map.sh` | Wrapper around slam_toolbox's `SerializePoseGraph` service (posegraph/data) |
| `.github/workflows/ci.yml` | Build + `ament_lint_auto` on every push/PR |

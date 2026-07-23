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

There are no unit tests beyond `ament_lint_auto`/`ament_lint_common` (declared as `test_depend` in
`package.xml`, run via the standard `colcon test`).

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
repos, not something to change independently. `mode: mapping` is online async mapping only; this
package does not do localization-against-a-saved-map or exploration (that's
`yahboom_rosmaster_navigation`'s job with the maps this package produces).

Tuning notes baked into the params file, worth knowing before changing them:
- `minimum_travel_distance`/`minimum_travel_heading` (0.2/0.2) are lowered from stock (0.5/0.5)
  because the X3 is small and operates in tight indoor spaces.
- `max_laser_range: 12.0` is bounded well under the simulated LiDAR's 30 m range to keep rasterized
  maps a reasonable size for the empty/cafe worlds.

`rviz/slam_view.rviz` intentionally **omits** the `RobotModel` display and slam_toolbox's
`SlamToolboxPlugin` panel — both reliably segfaulted RViz on Intel Iris Plus (Mesa/i915). Don't
re-add them without checking this still applies to the target GPU; TF axes + LaserScan already show
live pose without them.

## Repository layout

| Path | Contents |
|------|----------|
| `launch/slam.launch.py` | Main launch file: simulator (optional) + slam_toolbox + RViz |
| `config/slam_toolbox_params.yaml` | slam_toolbox parameters tuned for the ROSMASTER X3 |
| `rviz/slam_view.rviz` | RViz view (Map, LaserScan, Odometry, TF — no RobotModel/SlamToolboxPlugin) |
| `scripts/save_map.sh` | Wrapper around `nav2_map_server`'s `map_saver_cli` |

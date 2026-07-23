#!/usr/bin/env python3
"""
Launch slam_toolbox localization against a previously serialized map.

Starts (optionally) the yahboom_rosmaster_gazebo simulator, slam_toolbox's
localization_slam_toolbox_node against a map produced by
scripts/serialize_map.sh (see slam.launch.py for building that map in the
first place), and an RViz view for monitoring the robot's localized pose.
slam_toolbox consumes /scan and the odom -> base_footprint TF that the
simulator already publishes, so no changes to yahboom_rosmaster are required.
"""

import os
from typing import List

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate the localization launch description."""
    package_name_slam = 'yahboom_rosmaster_slam'
    package_name_gazebo = 'yahboom_rosmaster_gazebo'

    gazebo_launch_file_path = 'launch/rosmaster_gazebo_fortress.launch.py'
    default_slam_params_path = 'config/slam_toolbox_localization_params.yaml'
    default_rviz_config_path = 'rviz/slam_view.rviz'

    pkg_share_slam = FindPackageShare(package=package_name_slam).find(package_name_slam)
    pkg_share_gazebo = FindPackageShare(package=package_name_gazebo).find(package_name_gazebo)

    default_gazebo_launch_path = os.path.join(pkg_share_gazebo, gazebo_launch_file_path)
    default_world_path = os.path.join(pkg_share_gazebo, 'worlds', 'empty.world')
    default_slam_params_file = os.path.join(pkg_share_slam, default_slam_params_path)
    default_rviz_config_file = os.path.join(pkg_share_slam, default_rviz_config_path)

    # Launch configuration variables
    start_simulator = LaunchConfiguration('start_simulator')
    world = LaunchConfiguration('world')
    headless = LaunchConfiguration('headless')
    use_sim_time = LaunchConfiguration('use_sim_time')
    slam_params_file = LaunchConfiguration('slam_params_file')
    map_file_name = LaunchConfiguration('map_file_name')
    map_start_pose = LaunchConfiguration('map_start_pose')
    open_rviz = LaunchConfiguration('open_rviz')
    rviz_config_file = LaunchConfiguration('rviz_config_file')

    # Declare the launch arguments
    declare_start_simulator_cmd = DeclareLaunchArgument(
        name='start_simulator',
        default_value='true',
        description=(
            'Whether to launch the yahboom_rosmaster_gazebo simulator. '
            'Set to false if the simulator is already running in another terminal.'
        ))

    declare_world_cmd = DeclareLaunchArgument(
        name='world',
        default_value=default_world_path,
        description='Full path to the Gazebo world file (only used when start_simulator:=true)')

    declare_headless_cmd = DeclareLaunchArgument(
        name='headless',
        default_value='false',
        choices=['true', 'false'],
        description=(
            'Run Gazebo server without the GUI client '
            '(only used when start_simulator:=true)'
        ))

    declare_use_sim_time_cmd = DeclareLaunchArgument(
        name='use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true')

    declare_slam_params_file_cmd = DeclareLaunchArgument(
        name='slam_params_file',
        default_value=default_slam_params_file,
        description='Full path to the slam_toolbox parameters YAML file')

    declare_map_file_name_cmd = DeclareLaunchArgument(
        name='map_file_name',
        description=(
            'Filename prefix (no extension) of the serialized map to localize against, '
            'e.g. my_map for my_map.posegraph/my_map.data produced by '
            'scripts/serialize_map.sh. slam_toolbox resolves this relative to the '
            'directory ros2 launch is run from (it does not honor absolute paths -- '
            'see README "Localization Mode"), so cd there first. '
            'Required: this argument has no default.'
        ))

    declare_map_start_pose_cmd = DeclareLaunchArgument(
        name='map_start_pose',
        description=(
            'Initial [x, y, yaw] pose (map frame, meters/radians) to seed '
            'localization from, e.g. [0.0, 0.0, 0.0]. slam_toolbox\'s '
            'localization_slam_toolbox_node needs this starting hypothesis; it '
            'does not do global (AMCL-style) relocalization. '
            'Required: this argument has no default.'
        ))

    declare_open_rviz_cmd = DeclareLaunchArgument(
        name='open_rviz',
        default_value='true',
        description='Whether to start RViz with the SLAM view')

    declare_rviz_config_file_cmd = DeclareLaunchArgument(
        name='rviz_config_file',
        default_value=default_rviz_config_file,
        description='Full path to the RViz configuration file')

    # Simulator (optional)
    start_gazebo_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([default_gazebo_launch_path]),
        launch_arguments={
            'world': world,
            'rviz': 'false',
            'headless': headless,
            'use_sim_time': use_sim_time,
        }.items(),
        condition=IfCondition(start_simulator)
    )

    # slam_toolbox localization node
    start_slam_toolbox_cmd = Node(
        package='slam_toolbox',
        executable='localization_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            slam_params_file,
            {
                'use_sim_time': use_sim_time,
                'map_file_name': map_file_name,
                'map_start_pose': ParameterValue(map_start_pose, value_type=List[float]),
            }
        ]
    )

    # RViz (optional)
    start_rviz_cmd = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config_file],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
        condition=IfCondition(open_rviz)
    )

    ld = LaunchDescription()

    ld.add_action(declare_start_simulator_cmd)
    ld.add_action(declare_world_cmd)
    ld.add_action(declare_headless_cmd)
    ld.add_action(declare_use_sim_time_cmd)
    ld.add_action(declare_slam_params_file_cmd)
    ld.add_action(declare_map_file_name_cmd)
    ld.add_action(declare_map_start_pose_cmd)
    ld.add_action(declare_open_rviz_cmd)
    ld.add_action(declare_rviz_config_file_cmd)

    ld.add_action(start_gazebo_cmd)
    ld.add_action(start_slam_toolbox_cmd)
    ld.add_action(start_rviz_cmd)

    return ld

import os
import yaml
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def load_yaml(package_path, file_path):
    full_path = os.path.join(package_path, file_path)
    with open(full_path, 'r') as f:
        return yaml.safe_load(f)


def generate_launch_description():
    scara_moveit_dir = get_package_share_directory('scara_moveit_config')
    scara_dir = get_package_share_directory('scara')

    # ── Include the full Gazebo launch (spawns robot + controllers) ──
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(scara_dir, 'launch', 'gazebo.launch.py')
        )
    )

    # ── MoveIt config ─────────────────────────────────────────────────
    urdf_path = os.path.join(scara_dir, 'urdf', 'urdf_to_sdf_gazebo.urdf')
    srdf_path = os.path.join(scara_moveit_dir, 'config', 'urdf_to_sdf_gazebo.srdf')

    robot_description = ParameterValue(Command(['xacro ', urdf_path]), value_type=str)
    with open(srdf_path, 'r') as f:
        robot_description_semantic = f.read()

    kinematics    = load_yaml(scara_moveit_dir, 'config/kinematics.yaml')
    joint_limits  = load_yaml(scara_moveit_dir, 'config/joint_limits.yaml')
    ompl_planning = load_yaml(scara_moveit_dir, 'config/ompl_planning.yaml')
    pilz          = load_yaml(scara_moveit_dir, 'config/pilz_cartesian_limits.yaml')

    planning_pipeline_config = {
        'default_planning_pipeline': 'ompl',
        'planning_pipelines': ['ompl'],
        'ompl': ompl_planning,
    }

    # ── move_group connects to ALREADY RUNNING controllers in Gazebo ──
    controllers_yaml_path = os.path.join(
    scara_moveit_dir, 'config', 'ros2_controllers.yaml'
)

    move_group = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        parameters=[
            {'robot_description': robot_description},
            {'robot_description_semantic': robot_description_semantic},
            {'robot_description_kinematics': kinematics},
            {'robot_description_planning': joint_limits},
            planning_pipeline_config,
            {'use_sim_time': True},
            pilz,
            controllers_yaml_path,   # ← pass the FILE PATH directly, not loaded dict
        ],
        output='screen'
    )


    rviz = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', os.path.join(scara_moveit_dir, 'config', 'moveit.rviz')],
        parameters=[
            {'robot_description': robot_description},
            {'robot_description_semantic': robot_description_semantic},
            {'robot_description_kinematics': kinematics},
            {'use_sim_time': True},
        ],
        output='screen'
    )

    # Delay MoveIt by 5 seconds to let Gazebo + controllers fully start
    moveit_delayed = TimerAction(period=5.0, actions=[move_group, rviz])

    return LaunchDescription([
        gazebo_launch,
        moveit_delayed,
    ])

import os
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    RegisterEventHandler,
    SetEnvironmentVariable,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


scara_dir = get_package_share_directory('scara')


def generate_launch_description():

    # --- Declare model path arg ---
    model_arg = DeclareLaunchArgument(
        name='model',
        default_value=os.path.join(scara_dir, 'urdf', 'urdf_to_sdf_gazebo.urdf'),
        description='Absolute path to robot URDF file'
    )

    # --- Set mesh resource path so Gazebo finds STL files ---
    gz_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=str(Path(scara_dir).parent.resolve())
    )

    # --- Robot description via xacro Command (same pattern as working project) ---
    robot_description = ParameterValue(
        Command(['xacro ', LaunchConfiguration('model')]),
        value_type=str
    )

    # --- Robot State Publisher ---
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True
        }],
        output='screen'
    )

    # --- Controller Manager with resolved controllers.yaml ---
    controllers_yaml = os.path.join(scara_dir, 'config', 'controllers.yaml')
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[
            {'robot_description': robot_description},
            controllers_yaml
        ],
        output='screen'
    )

    # --- Gazebo Harmonic ---
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(
                get_package_share_directory('ros_gz_sim'),
                'launch', 'gz_sim.launch.py'
            )
        ]),
        launch_arguments=[('gz_args', '-v 4 -r empty.sdf')]
    )

    # --- Spawn robot ---
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-topic', 'robot_description', '-name', 'scara_wafer_arm'],
        output='screen'
    )

    # --- Clock bridge ---
    gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen'
    )

    # --- Load controllers after spawn (chained) ---
    load_jsb = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller',
             '--set-state', 'active', 'joint_state_broadcaster'],
        output='screen'
    )
    load_arm = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller',
             '--set-state', 'active', 'scara_arm_controller'],
        output='screen'
    )
    load_gripper = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller',
             '--set-state', 'active', 'gripper_controller'],
        output='screen'
    )

    jsb_after_spawn = RegisterEventHandler(
        OnProcessExit(target_action=spawn_entity, on_exit=[load_jsb])
    )
    arm_after_jsb = RegisterEventHandler(
        OnProcessExit(target_action=load_jsb, on_exit=[load_arm, load_gripper])
    )

    return LaunchDescription([
        model_arg,
        gz_resource_path,
        robot_state_publisher,
        controller_manager,
        gazebo,
        spawn_entity,
        gz_bridge,
        jsb_after_spawn,
        arm_after_jsb,
    ])

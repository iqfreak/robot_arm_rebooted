#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from sensor_msgs.msg import JointState
from builtin_interfaces.msg import Duration


class ScaraBrain(Node):

    def __init__(self):
        super().__init__('scara_brain')

        # SENSE — subscribe to joint states
        self.joint_positions = {
            'joint1': 0.0, 'joint2': 0.0,
            'joint3': 0.0, 'joint4': 0.0,
            'joint_gripper_left': 0.0,
            'joint_gripper_right': 0.0
        }
        self.create_subscription(
            JointState, '/joint_states',
            self._cb_joint_states, 10
        )

        # ACT — action clients
        self._arm = ActionClient(
            self, FollowJointTrajectory,
            '/scara_arm_controller/follow_joint_trajectory'
        )
        self._gripper = ActionClient(
            self, FollowJointTrajectory,
            '/gripper_controller/follow_joint_trajectory'
        )

        self.get_logger().info('Waiting for controllers...')
        self._arm.wait_for_server()
        self._gripper.wait_for_server()
        self.get_logger().info('Brain online. Controllers ready.')

        # Run a test movement after 2 seconds
        self.create_timer(2.0, self._test_once)
        self._tested = False

    def _cb_joint_states(self, msg: JointState):
        for name, pos in zip(msg.name, msg.position):
            if name in self.joint_positions:
                self.joint_positions[name] = pos

    def move_arm(self, j1, j2, j3, j4, secs=3.0):
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = [
            'joint1', 'joint2', 'joint3', 'joint4'
        ]
        pt = JointTrajectoryPoint()
        pt.positions = [j1, j2, j3, j4]
        pt.velocities = [0.0] * 4
        pt.time_from_start = Duration(sec=int(secs))
        goal.trajectory.points = [pt]

        self.get_logger().info(f'Moving to [{j1:.2f}, {j2:.2f}, {j3:.2f}, {j4:.2f}]')
        fut = self._arm.send_goal_async(goal)
        fut.add_done_callback(self._on_goal_response)

    def _on_goal_response(self, future):
        handle = future.result()
        if not handle.accepted:
            self.get_logger().error('Goal REJECTED by controller')
            return
        self.get_logger().info('Goal accepted — arm moving')
        handle.get_result_async().add_done_callback(self._on_result)

    def _on_result(self, future):
        code = future.result().result.error_code
        if code == 0:
            self.get_logger().info('Movement complete ✓')
        else:
            self.get_logger().error(f'Movement failed. Error code: {code}')

    def _test_once(self):
        if self._tested:
            return
        self._tested = True
        self.get_logger().info('--- Running test movement ---')
        self.move_arm(0.5, -0.3, -0.05, 0.2, secs=3.0)


def main(args=None):
    rclpy.init(args=args)
    node = ScaraBrain()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

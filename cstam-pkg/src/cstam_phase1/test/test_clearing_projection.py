"""No-return rays clear space without entering obstacle or localization data."""
import math
from types import SimpleNamespace
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header
from cstam_phase1.pointcloud_navigation_filter import PointCloudNavigationFilter


def test_no_return_is_clearing_only():
    node = object.__new__(PointCloudNavigationFilter)
    for key, value in dict(samples=360, range_min=.1, range_max=15.,
                           vertical_angle_min=-1.04719755, vertical_angle_max=.34906585,
                           min_height=-.88, max_height=.35, scan_max_height=.26,
                           sensor_x=.24, sensor_z=.92,
                           self_x_min=-.29, self_x_max=.34,
                           self_y_min=-.26, self_y_max=.26,
                           self_z_min=0., self_z_max=1.27).items():
        setattr(node, key, value)
    clouds, clearing, scans = [], [], []
    node.cloud_publisher = SimpleNamespace(publish=clouds.append)
    node.clearing_publisher = SimpleNamespace(publish=clearing.append)
    node.scan_publisher = SimpleNamespace(publish=scans.append)
    message = point_cloud2.create_cloud_xyz32(Header(), [
        (float('inf'),)*3, (1., 0., 0.), (2., 0., -1.27), (float('nan'),)*3])
    message.height, message.width, message.row_step = 2, 2, 24
    node._callback(message)
    obstacles = list(point_cloud2.read_points(clouds[0]))
    rays = list(point_cloud2.read_points(clearing[0]))
    assert len(obstacles) == 1
    assert len(rays) == 3
    assert math.isclose(math.sqrt(sum(float(x)**2 for x in rays[0])), 15., abs_tol=1e-5)
    assert sum(math.isfinite(x) for x in scans[0].ranges) == 1
    assert min(scans[0].ranges) == 1.

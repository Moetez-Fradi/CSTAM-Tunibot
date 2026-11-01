#!/usr/bin/env python3
"""Draw the VIP's ID badge: ArUco DICT_4X4_50 marker 7 with a white quiet zone.

The pedestrian simulator puts this image on the VIP's badges and
vip_detector reads it back. Run from cstam_phase1/ to regenerate:
    python3 scripts/make_vip_badge.py
"""

import cv2
import numpy as np

MARKER_ID = 7
MARKER_PX, MARGIN_PX = 240, 40   # the marker fills 3/4 of the badge

marker = cv2.aruco.drawMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
                              MARKER_ID, MARKER_PX)
badge = np.full((MARKER_PX + 2 * MARGIN_PX,) * 2, 255, dtype=np.uint8)
badge[MARGIN_PX:-MARGIN_PX, MARGIN_PX:-MARGIN_PX] = marker
cv2.imwrite('config/vip_badge.png', cv2.cvtColor(badge, cv2.COLOR_GRAY2BGR))
print(f'config/vip_badge.png: ArUco 4x4 id {MARKER_ID}, {badge.shape[1]} px')

"""Summarise phase2_acceptance.sh runs from their trial.json and trace.jsonl.

Usage: ros2 run cstam_phase1 phase2_report RUN_DIR [RUN_DIR ...] [--json OUT]

Prints, per run: each delivery's outcome, ground-truth clearances, contacts
and collision-monitor time; people encountered within 1 m while navigating;
the longest navigation stall; and, for every contact, the trace around it in
the robot frame (who moved into whom, and what the monitor was doing).
"""

import json
import math
import os
import sys

from cstam_phase1.pedestrian_model import footprint_clearance

NAVIGATING = ('NAVIGATING_TO_PICKUP', 'NAVIGATING_TO_CUSTOMER', 'RETURNING_TO_DOCK')


def _local(robot, point):
    rx, ry, yaw = robot
    dx, dy = point[0] - rx, point[1] - ry
    return (math.cos(yaw) * dx + math.sin(yaw) * dy,
            -math.sin(yaw) * dx + math.cos(yaw) * dy)


def analyse(run_dir):
    with open(os.path.join(run_dir, 'trial.json'), encoding='utf-8') as stream:
        trial = json.load(stream)
    rows = []
    trace = os.path.join(run_dir, 'trace.jsonl')
    if os.path.exists(trace):
        with open(trace, encoding='utf-8') as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
    rows = [r for r in rows if r.get('robot')]

    encounters, near, contacts = {}, {}, []
    in_contact = {}
    longest, still_since = 0.0, None
    for i, row in enumerate(rows):
        for name, position in row['people'].items():
            clearance = footprint_clearance(row['robot'], position)
            navigating = row['state'] in NAVIGATING
            if navigating and clearance < 1.0 and not near.get(name):
                encounters[name] = encounters.get(name, 0) + 1
            near[name] = clearance < 1.0 or (near.get(name, False) and clearance < 1.2)
            if clearance <= 0.0 and not in_contact.get(name):
                window = []
                for r in rows[max(0, i - 6):i + 3]:
                    lx, ly = _local(r['robot'], r['people'][name])
                    window.append({
                        't': r['t'], 'local_xy': [round(lx, 2), round(ly, 2)],
                        'clearance': round(footprint_clearance(r['robot'], r['people'][name]), 3),
                        'monitor': r['monitor'], 'cmd_in': r['cmd_in'], 'cmd': r['cmd']})
                contacts.append({'pedestrian': name, 't': row['t'], 'trace': window})
            in_contact[name] = clearance <= 0.0 or (in_contact.get(name, False)
                                                    and clearance < 0.05)
        if row['state'] in NAVIGATING and i > 0:
            prev = rows[i - 1]
            moved = math.dist(row['robot'][:2], prev['robot'][:2])
            turned = abs(math.remainder(row['robot'][2] - prev['robot'][2], math.tau))
            if moved < 0.01 and turned < 0.01:
                still_since = still_since if still_since is not None else prev['t']
                longest = max(longest, row['t'] - still_since)
            else:
                still_since = None
        else:
            still_since = None

    return {
        'run': os.path.basename(os.path.normpath(run_dir)),
        'deliveries': [{
            'location': t['location'], 'result': t['result'],
            'wall_time_sec': t.get('wall_time_sec'),
            **{k: (t.get('pedestrians') or {}).get(k) for k in (
                'min_clearance_m', 'min_clearance_while_robot_moving_m',
                'contacts', 'robot_fault_contacts', 'close_passes')},
            'collision_monitor_seconds': t.get('collision_monitor_seconds'),
        } for t in trial['trials']],
        'encounters_within_1m_while_navigating': encounters,
        'longest_navigation_stall_sec': round(longest, 1),
        'contacts': contacts,
    }


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    out = None
    if '--json' in args:
        index = args.index('--json')
        out = args[index + 1]
        del args[index:index + 2]
    if not args:
        print(__doc__)
        return 2
    reports = [analyse(run) for run in args]
    for report in reports:
        print(f"== {report['run']}")
        for d in report['deliveries']:
            print(f"  {d['location']:8s} {d['result']:8s} {d['wall_time_sec']:>7}s "
                  f"min clr {d['min_clearance_m']} (moving {d['min_clearance_while_robot_moving_m']})"
                  f" contacts {d['contacts']} (robot fault {d['robot_fault_contacts']})"
                  f" monitor {d['collision_monitor_seconds']}")
        print(f"  encounters <1 m: {report['encounters_within_1m_while_navigating']}"
              f" | longest stall {report['longest_navigation_stall_sec']} s")
        for contact in report['contacts']:
            print(f"  contact with {contact['pedestrian']} at t={contact['t']}:")
            for step in contact['trace']:
                print(f"    t={step['t']:7.1f} person at robot-frame {step['local_xy']}"
                      f" clr {step['clearance']:+.2f} monitor={step['monitor']}"
                      f" cmd_in={step['cmd_in']} cmd={step['cmd']}")
    if out:
        with open(out, 'w', encoding='utf-8') as stream:
            json.dump(reports, stream, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())

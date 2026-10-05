"""Simple simulated GPS movement along predefined route coordinates."""

import math
import random
from datetime import datetime

from database import Bus, Route, route_coordinates, save_location


def update_buses(db) -> int:
    """Move each operating bus toward the next route point; return buses updated."""
    updated = 0

    for bus in db.query(Bus).all():
        if bus.status == "Inactive":
            continue

        route = db.get(Route, bus.route_id)
        points = route_coordinates(route) if route else []
        if not points:
            # No route coordinates available: make a tiny safe GPS movement.
            bus.latitude += random.uniform(-0.001, 0.001)
            bus.longitude += random.uniform(-0.001, 0.001)
        else:
            target = min(
                points,
                key=lambda point: math.hypot(
                    point[0] - bus.latitude, point[1] - bus.longitude
                ),
            )
            # Move part-way toward the nearest route point.
            bus.latitude += (target[0] - bus.latitude) * random.uniform(0.05, 0.20)
            bus.longitude += (target[1] - bus.longitude) * random.uniform(0.05, 0.20)

        if bus.status == "Stopped":
            bus.speed_kmh = 0
        else:
            bus.speed_kmh = round(random.uniform(18, 48), 1)
            if bus.status != "Delayed":
                bus.status = "Moving"

        bus.last_updated = datetime.utcnow()
        save_location(db, bus)
        updated += 1

    db.commit()
    return updated

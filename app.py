"""BusMind: AI-Based Smart Bus Tracking & Prediction System."""

from datetime import datetime, timedelta

import folium
import pandas as pd
import streamlit as st
from geopy.distance import geodesic
from sqlalchemy import func
from streamlit_folium import st_folium

from database import (
    Bus,
    LocationHistory,
    PredictionResult,
    Route,
    SessionLocal,
    initialize_database,
    route_coordinates,
    save_prediction,
)
from gps_simulator import update_buses
from prediction import predict_delay, predict_eta


st.set_page_config(page_title="BusMind", page_icon="🚌", layout="wide")
initialize_database()

STATUS_COLORS = {
    "Moving": "green",
    "Stopped": "orange",
    "Delayed": "red",
    "Inactive": "gray",
}


def load_data():
    with SessionLocal() as db:
        buses = db.query(Bus).all()
        routes = db.query(Route).all()
        return [
            {
                "number": b.number,
                "route": b.route.name if b.route else "Unknown",
                "route_id": b.route_id,
                "latitude": b.latitude,
                "longitude": b.longitude,
                "speed": b.speed_kmh,
                "status": b.status,
                "next_stop": b.next_stop,
                "delay": b.delay_minutes,
                "updated": b.last_updated,
            }
            for b in buses
        ], [
            {
                "id": r.id,
                "name": r.name,
                "source": r.source,
                "destination": r.destination,
                "distance": r.distance_km,
                "travel": r.travel_minutes,
                "stops": r.stops_text,
                "coordinates": route_coordinates(r),
            }
            for r in routes
        ]

def draw_map(buses, routes, selected_route=None):
    """Build a Folium map with route lines, stops, and bus popups."""

    if buses:
        center = [
            sum(b["latitude"] for b in buses) / len(buses),
            sum(b["longitude"] for b in buses) / len(buses),
        ]
    else:
        center = [17.385, 78.4867]

    map_view = folium.Map(
        location=center,
        zoom_start=12,
        control_scale=True
    )

    for route in routes:
        if selected_route and route["name"] != selected_route:
            continue

        points = route["coordinates"]

        if points:
            # Draw route line
            folium.PolyLine(
                points,
                color="blue",
                weight=4,
                opacity=0.65,
                tooltip=route["name"]
            ).add_to(map_view)

            # Add stops
            stops = [s.strip() for s in route["stops"].split(",")]

            for i, stop in enumerate(stops):
                if stop:
                    point_index = min(i, len(points) - 1)

                    folium.CircleMarker(
                        location=points[point_index],
                        radius=4,
                        color="blue",
                        fill=True,
                        popup=f"Stop: {stop}",
                    ).add_to(map_view)

    # Add bus markers
    for bus in buses:
        color = STATUS_COLORS.get(bus["status"], "blue")

        folium.Marker(
            [bus["latitude"], bus["longitude"]],
            tooltip=f"Bus {bus['number']} · {bus['status']}",
            popup=(
                f"<b>Bus {bus['number']}</b><br>"
                f"Route: {bus['route']}<br>"
                f"Speed: {bus['speed']} km/h<br>"
                f"Status: {bus['status']}<br>"
                f"Next stop: {bus['next_stop']}<br>"
                f"Delay: {bus['delay']} min"
            ),
            icon=folium.Icon(
                color=color,
                icon="bus",
                prefix="fa"
            ),
        ).add_to(map_view)

    return map_view

def bus_details(bus):
    route = next((r for r in routes if r["name"] == bus["route"]), None)
    remaining = route["distance"] if route else 5
    eta = predict_eta(remaining, bus["speed"], 5, bus["delay"])
    st.write(f"**Bus number:** {bus['number']}")
    st.write(f"**Route:** {bus['route']}")
    st.write(f"**Current location:** {bus['latitude']:.5f}, {bus['longitude']:.5f}")
    st.write(f"**Speed:** {bus['speed']} km/h · **Status:** {bus['status']}")
    st.write(f"**Next stop:** {bus['next_stop']}")
    st.write(f"**Estimated arrival:** {round(eta)} minutes")
    st.write(f"**Delay:** {bus['delay']} minutes")
    st.write(f"**Last updated:** {bus['updated'].strftime('%Y-%m-%d %H:%M:%S UTC')}")


st.title("🚌 BusMind")
st.caption("AI-Based Smart Bus Tracking & Prediction System · College project demo")

buses, routes = load_data()
route_names = [r["name"] for r in routes]
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Live Tracking", "Routes", "ETA Prediction",
     "Delay Prediction", "AI Assistant", "Analytics", "Admin"],
)
st.sidebar.caption("GPS data is simulated for this demo.")

if page == "Dashboard":
    active = sum(b["status"] != "Inactive" for b in buses)
    delayed = sum(b["status"] == "Delayed" for b in buses)
    speeds = [b["speed"] for b in buses if b["status"] != "Inactive"]
    average_speed = sum(speeds) / len(speeds) if speeds else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total buses", len(buses))
    c2.metric("Active buses", active)
    c3.metric("Delayed buses", delayed)
    c4.metric("Average speed", f"{average_speed:.1f} km/h")

    st.subheader("Buses currently operating")
    st.dataframe(pd.DataFrame(buses), use_container_width=True, hide_index=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Bus status")
        if buses:
            st.bar_chart(pd.Series([b["status"] for b in buses]).value_counts())
    with right:
        st.subheader("Speed by bus")
        if buses:
            st.bar_chart(pd.DataFrame(buses).set_index("number")[["speed"]])

elif page == "Live Tracking":
    st.subheader("Live bus tracking")
    with st.expander("GPS simulation controls", expanded=True):
        if st.button("▶ Start / advance simulation"):
            with SessionLocal() as db:
                count = update_buses(db)
            st.success(f"Updated {count} buses.")
            st.rerun()
        st.caption("Each click advances simulated locations by one step.")

    selected = st.selectbox("View bus details", [b["number"] for b in buses] or ["No buses"])
    if buses:
        chosen = next(b for b in buses if b["number"] == selected)
        left, right = st.columns([2, 1])
        with left:
            st_folium(draw_map(buses, routes), height=540, use_container_width=True)
        with right:
            st.subheader(f"Bus {selected}")
            bus_details(chosen)

    st.subheader("Search and filter buses")
    search = st.text_input("Search by bus number")
    route_filter = st.selectbox("Route", ["All"] + route_names)
    status_filter = st.selectbox("Status", ["All", "Moving", "Stopped", "Delayed", "Inactive"])
    filtered = [
        b for b in buses
        if search.lower() in b["number"].lower()
        and (route_filter == "All" or b["route"] == route_filter)
        and (status_filter == "All" or b["status"] == status_filter)
    ]
    st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)

elif page == "Routes":
    st.subheader("Route information")
    if not routes:
        st.info("No routes are available yet.")
    else:
        selected = st.selectbox("Select route", route_names)
        route = next(r for r in routes if r["name"] == selected)
        a, b, c = st.columns(3)
        a.metric("Distance", f"{route['distance']} km")
        b.metric("Estimated travel time", f"{route['travel']} min")
        c.metric("Stops", len([s for s in route["stops"].split(",") if s.strip()]))
        st.write(f"**From:** {route['source']}  →  **To:** {route['destination']}")
        st.write(f"**Stops:** {route['stops']}")
        st_folium(draw_map(buses, routes, selected_route=selected),
                  height=500, use_container_width=True)

elif page == "ETA Prediction":
    st.subheader("ETA prediction")
    if buses:
        selected = st.selectbox("Bus", [b["number"] for b in buses], key="eta_bus")
        bus = next(b for b in buses if b["number"] == selected)
        route = next((r for r in routes if r["name"] == bus["route"]), None)
        stops = route["stops"].split(",") if route else [bus["next_stop"]]
        stop = st.selectbox("Arrival stop", [s.strip() for s in stops if s.strip()])
        traffic = st.slider("Traffic / extra delay (minutes)", 0, 30, 5)
        remaining_km = st.number_input("Estimated distance to stop (km)", 0.1, 100.0, 5.0)
        if st.button("Predict ETA"):
            eta = predict_eta(remaining_km, bus["speed"], traffic, bus["delay"])
            arrival = datetime.now() + timedelta(minutes=eta)
            st.success(f"Estimated arrival at **{stop}** in **{eta:.0f} minutes**.")
            st.caption(f"Approximate arrival time: {arrival.strftime('%H:%M')}")
            with SessionLocal() as db:
                save_prediction(db, bus["number"], "ETA", f"{eta:.1f} min to {stop}", eta)
                db.commit()
    else:
        st.info("No buses available for prediction.")

elif page == "Delay Prediction":
    st.subheader("Delay prediction")
    if buses:
        selected = st.selectbox("Bus", [b["number"] for b in buses], key="delay_bus")
        bus = next(b for b in buses if b["number"] == selected)
        traffic = st.slider("Traffic impact (minutes)", 0, 30, 5, key="delay_traffic")
        distance = st.number_input("Distance remaining (km)", 0.1, 100.0, 5.0, key="delay_distance")
        if st.button("Predict delay"):
            category, minutes = predict_delay(distance, bus["speed"], traffic, bus["delay"])
            st.metric("Prediction", category, f"{minutes:.1f} estimated delay minutes")
            st.write("**Factors considered:** current speed, remaining distance, traffic estimate, and existing delay.")
            with SessionLocal() as db:
                save_prediction(db, bus["number"], "Delay", category, minutes)
                db.commit()
    else:
        st.info("No buses available for prediction.")

elif page == "AI Assistant":
    st.subheader("BusMind assistant")
    st.caption("Ask about buses, routes, arrival estimates, or current status.")
    question = st.text_input("Your question", placeholder="Where is Bus 101?")
    if question:
        text = question.lower()
        matched_bus = next(
            (b for b in buses if b["number"].lower() in text.replace("bus ", "")),
            None,
        )
        if "active" in text:
            active_buses = [b for b in buses if b["status"] != "Inactive"]
            st.write("Active buses: " + (", ".join(b["number"] for b in active_buses) or "None"))
        elif "airport" in text:
            airport_routes = [r for r in routes if "airport" in r["destination"].lower()]
            st.write("Routes to the airport: " + (", ".join(r["name"] for r in airport_routes) or "None"))
        elif matched_bus and ("when" in text or "arrive" in text or "eta" in text):
            eta = predict_eta(5, matched_bus["speed"], 5, matched_bus["delay"])
            st.write(f"Bus {matched_bus['number']} is estimated to arrive in about {eta:.0f} minutes.")
        elif matched_bus:
            st.write(
                f"Bus {matched_bus['number']} is on {matched_bus['route']}, "
                f"at {matched_bus['latitude']:.4f}, {matched_bus['longitude']:.4f}. "
                f"Status: {matched_bus['status']}; speed: {matched_bus['speed']} km/h."
            )
        elif "route" in text and "delayed" in text:
            delayed_routes = sorted({b["route"] for b in buses if b["status"] == "Delayed"})
            st.write("Delayed routes: " + (", ".join(delayed_routes) or "No routes are currently marked delayed."))
        else:
            st.write("Try asking “Where is Bus 101?”, “Show active buses”, or “Which bus goes to Hyderabad Airport?”")

elif page == "Analytics":
    st.subheader("Analytics")
    with SessionLocal() as db:
        history = db.query(LocationHistory).order_by(LocationHistory.recorded_at).all()
        predictions = db.query(PredictionResult).order_by(PredictionResult.recorded_at).all()

    if history:
        history_df = pd.DataFrame([
            {
                "time": row.recorded_at,
                "bus": row.bus_number,
                "speed": row.speed_kmh,
                "status": row.status,
                "latitude": row.latitude,
                "longitude": row.longitude,
            }
            for row in history
        ])
        st.write("Speed trends")
        st.line_chart(history_df.pivot_table(index="time", columns="bus", values="speed", aggfunc="mean"))
        st.write("Historical GPS data")
        st.dataframe(history_df.tail(100), use_container_width=True, hide_index=True)
    else:
        st.info("GPS history will appear after the simulation is advanced.")

    if buses:
        st.write("Route performance and bus usage")
        route_df = pd.DataFrame(buses).groupby("route").agg(
            buses=("number", "count"), average_speed=("speed", "mean"),
            delayed=("status", lambda values: sum(value == "Delayed" for value in values)),
        )
        st.dataframe(route_df, use_container_width=True)

    delays = [b["delay"] for b in buses if b["status"] == "Delayed"]
    st.metric("Delayed buses", len(delays))
    st.metric("Average delay", f"{sum(delays) / len(delays):.1f} min" if delays else "0 min")
    if predictions:
        st.write("Saved prediction results")
        st.dataframe(pd.DataFrame([
            {"bus": p.bus_number, "type": p.prediction_type, "result": p.result,
             "minutes": p.predicted_minutes, "time": p.recorded_at}
            for p in predictions
        ]), use_container_width=True, hide_index=True)
    else:
        st.caption("ETA and delay predictions appear here after you run predictions.")

elif page == "Admin":
    st.subheader("Admin")
    st.warning("Demo admin page: no authentication is configured. Do not expose it publicly.")
    with SessionLocal() as db:
        st.write("### All buses")
        st.dataframe(pd.DataFrame([
            {"Bus": b.number, "Route": b.route.name if b.route else "Unknown",
             "Status": b.status, "Speed": b.speed_kmh}
            for b in db.query(Bus).all()
        ]), use_container_width=True, hide_index=True)

        st.write("### Add a bus")
        with st.form("add_bus"):
            number = st.text_input("Bus number")
            route_choices = {r.name: r.id for r in db.query(Route).all()}
            route_name = st.selectbox("Route", list(route_choices) or ["No routes"])
            lat = st.number_input("Latitude", value=17.3850, format="%.6f")
            lon = st.number_input("Longitude", value=78.4867, format="%.6f")
            submitted = st.form_submit_button("Add bus")
            if submitted:
                if not number.strip():
                    st.error("Enter a bus number.")
                elif db.query(Bus).filter_by(number=number.strip()).first():
                    st.error("That bus number already exists.")
                elif route_name == "No routes":
                    st.error("Add a route before adding a bus.")
                else:
                    db.add(Bus(number=number.strip(), route_id=route_choices[route_name],
                               latitude=lat, longitude=lon, status="Moving"))
                    db.commit()
                    st.success("Bus added. Refresh the page to see it.")
                    st.rerun()

        st.write("### Update or remove a bus")
        all_buses = db.query(Bus).all()
        if all_buses:
            number = st.selectbox("Select bus to manage", [b.number for b in all_buses])
            bus = db.query(Bus).filter_by(number=number).first()
            status = st.selectbox("Set status", ["Moving", "Stopped", "Delayed", "Inactive"],
                                  index=["Moving", "Stopped", "Delayed", "Inactive"].index(bus.status))
            col1, col2 = st.columns(2)
            if col1.button("Save status"):
                bus.status = status
                db.commit()
                st.success("Status updated.")
                st.rerun()
            if col2.button("Remove bus"):
                db.delete(bus)
                db.commit()
                st.success("Bus removed.")
                st.rerun()

        st.write("### Add route")
        with st.form("add_route"):
            route_name = st.text_input("Route name")
            source = st.text_input("Source")
            destination = st.text_input("Destination")
            distance = st.number_input("Distance (km)", min_value=0.1, value=10.0)
            travel = st.number_input("Travel time (minutes)", min_value=1, value=30)
            stops = st.text_input("Stops, comma-separated")
            coords = st.text_input(
                "Coordinates, latitude:longitude pairs separated by |",
                placeholder="17.3850:78.4867|17.4000:78.4700",
            )
            if st.form_submit_button("Add route"):
                if not route_name.strip() or not source.strip() or not destination.strip():
                    st.error("Route name, source, and destination are required.")
                elif db.query(Route).filter_by(name=route_name.strip()).first():
                    st.error("That route name already exists.")
                else:
                    db.add(Route(name=route_name.strip(), source=source.strip(),
                                 destination=destination.strip(), distance_km=distance,
                                 travel_minutes=travel, stops_text=stops,
                                 coordinates_text=coords))
                    db.commit()
                    st.success("Route added.")
                    st.rerun()

        st.write("### System statistics")
        st.write(f"Routes: {db.query(Route).count()} · Buses: {db.query(Bus).count()} · "
                 f"GPS records: {db.query(LocationHistory).count()}")

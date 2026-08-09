import { useMemo, useState } from "react";
import { MapContainer, TileLayer, Circle, CircleMarker, Popup, useMap } from "react-leaflet";
import { useEffect } from "react";
import { SG_CENTER } from "../lib/heat";
import "leaflet/dist/leaflet.css";

const levelToColor = (level) => {
  const l = (level || "low").toLowerCase();
  if (l === "low") return "#10B981";
  if (l === "moderate") return "#F59E0B";
  if (l === "high") return "#EF4444";
  return "#991B1B";
};

function Recenter({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center?.lat != null && center?.lng != null) {
      map.setView([center.lat, center.lng], map.getZoom(), { animate: true });
    }
  }, [center?.lat, center?.lng, map]);
  return null;
}

export default function MapView({ userLocation, wbgtStations = [], coolingSpots = [], rainStations = [], showRain = false }) {
  const center = useMemo(() => {
    const c = userLocation || SG_CENTER;
    return [c.lat, c.lng];
  }, [userLocation]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setReady(true);
  }, []);

  if (!ready) {
    return <div className="w-full h-full bg-slate-100" data-testid="map-loading" />;
  }

  return (
    <div className="w-full h-full" data-testid="map-canvas">
      <MapContainer
        center={center}
        zoom={12}
        style={{ width: "100%", height: "100%" }}
        scrollWheelZoom
        zoomControl
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Recenter center={userLocation || SG_CENTER} />

        {wbgtStations.map((s) => (
          <Circle
            key={`w-${s.station_id}`}
            center={[s.lat, s.lng]}
            radius={2200}
            pathOptions={{
              color: levelToColor(s.level),
              weight: 1,
              fillColor: levelToColor(s.level),
              fillOpacity: 0.28,
            }}
          >
            <Popup>
              <p className="font-bold m-0">{s.name}</p>
              <p className="m-0 capitalize" style={{ color: levelToColor(s.level) }}>
                {s.level} heat stress
              </p>
            </Popup>
          </Circle>
        ))}

        {showRain &&
          rainStations
            .filter((r) => r.value > 0)
            .map((r) => (
              <Circle
                key={`r-${r.station_id}`}
                center={[r.lat, r.lng]}
                radius={1800}
                pathOptions={{ color: "#2563EB", weight: 1, fillColor: "#3B82F6", fillOpacity: 0.3 }}
              />
            ))}

        {coolingSpots.map((c) => (
          <CircleMarker
            key={c.id}
            center={[c.lat, c.lng]}
            radius={7}
            pathOptions={{ color: "#fff", weight: 2, fillColor: "#0A58CA", fillOpacity: 1 }}
          >
            <Popup>
              <p className="font-bold m-0">{c.name}</p>
              <p className="m-0 text-primary capitalize">Cool spot · {c.type}</p>
            </Popup>
          </CircleMarker>
        ))}

        {userLocation && (
          <CircleMarker
            center={[userLocation.lat, userLocation.lng]}
            radius={9}
            pathOptions={{ color: "#fff", weight: 3, fillColor: "#111827", fillOpacity: 1 }}
          >
            <Popup>You are here</Popup>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  );
}

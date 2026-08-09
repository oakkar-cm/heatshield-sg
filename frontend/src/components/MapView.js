import { useMemo } from "react";
import { GoogleMap, useJsApiLoader, Marker, Circle, InfoWindow } from "@react-google-maps/api";
import { useState, useEffect } from "react";
import { heatColor } from "../lib/heat";
import { Loader2, AlertTriangle, Snowflake } from "lucide-react";
import { SG_CENTER } from "../lib/heat";

const containerStyle = { width: "100%", height: "100%" };

const levelToColor = (level) => {
  const l = (level || "low").toLowerCase();
  if (l === "low") return "#10B981";
  if (l === "moderate") return "#F59E0B";
  if (l === "high") return "#EF4444";
  return "#991B1B";
};

function MapFallback({ wbgtStations = [], coolingSpots = [] }) {
  const sorted = [...wbgtStations].sort((a, b) => b.wbgt - a.wbgt);
  return (
    <div className="w-full h-full overflow-y-auto bg-slate-50 p-4 sm:p-6" data-testid="map-fallback">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-start gap-3 p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-semibold">Interactive map couldn't load</p>
            <p className="mt-1">The Google Maps key needs this site's domain whitelisted (HTTP referrers) in Google Cloud Console, and the "Maps JavaScript API" enabled. Live station data is shown below meanwhile.</p>
          </div>
        </div>

        <h3 className="font-heading font-semibold text-lg mt-6 mb-3">Live heat stations</h3>
        <div className="grid sm:grid-cols-2 gap-2">
          {sorted.map((s) => (
            <div key={s.station_id} className="flex items-center gap-3 p-3 rounded-xl bg-white border border-border">
              <span className="w-3.5 h-3.5 rounded-full shrink-0" style={{ backgroundColor: levelToColor(s.level) }} />
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{s.name}</p>
                <p className="text-xs text-slate-500 capitalize">{s.level} heat stress</p>
              </div>
            </div>
          ))}
        </div>

        <h3 className="font-heading font-semibold text-lg mt-6 mb-3 flex items-center gap-2"><Snowflake className="w-5 h-5 text-primary" /> Cool spots</h3>
        <div className="grid sm:grid-cols-2 gap-2">
          {coolingSpots.map((c) => (
            <div key={c.id} className="flex items-center gap-3 p-3 rounded-xl bg-white border border-border">
              <span className="w-3 h-3 rounded-full bg-primary shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{c.name}</p>
                <p className="text-xs text-slate-500 capitalize">{c.type}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function MapView({ userLocation, wbgtStations = [], coolingSpots = [], rainStations = [], showRain = false }) {
  const { isLoaded } = useJsApiLoader({
    id: "google-map-script",
    googleMapsApiKey: process.env.REACT_APP_GOOGLE_MAPS_API_KEY,
  });
  const [active, setActive] = useState(null);
  const [authFailed, setAuthFailed] = useState(false);

  useEffect(() => {
    window.gm_authFailure = () => setAuthFailed(true);
  }, []);

  const center = userLocation || SG_CENTER;

  const options = useMemo(
    () => ({
      disableDefaultUI: true,
      zoomControl: true,
      styles: [
        { featureType: "poi", elementType: "labels", stylers: [{ visibility: "off" }] },
        { featureType: "transit", elementType: "labels", stylers: [{ visibility: "off" }] },
      ],
    }),
    []
  );

  if (authFailed) return <MapFallback wbgtStations={wbgtStations} coolingSpots={coolingSpots} />;

  if (!isLoaded)
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-100">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );

  return (
    <GoogleMap mapContainerStyle={containerStyle} center={center} zoom={12} options={options}>
      {/* Heat overlay circles from WBGT stations */}
      {wbgtStations.map((s) => (
        <Circle
          key={`w-${s.station_id}`}
          center={{ lat: s.lat, lng: s.lng }}
          radius={2200}
          options={{
            strokeColor: levelToColor(s.level),
            strokeOpacity: 0.5,
            strokeWeight: 1,
            fillColor: levelToColor(s.level),
            fillOpacity: 0.28,
            clickable: true,
          }}
          onClick={() => setActive({ type: "wbgt", ...s })}
        />
      ))}

      {/* Rainfall overlay */}
      {showRain &&
        rainStations
          .filter((r) => r.value > 0)
          .map((r) => (
            <Circle
              key={`r-${r.station_id}`}
              center={{ lat: r.lat, lng: r.lng }}
              radius={1800}
              options={{ strokeColor: "#2563EB", strokeOpacity: 0.5, strokeWeight: 1, fillColor: "#3B82F6", fillOpacity: 0.3 }}
            />
          ))}

      {/* Cooling spots */}
      {coolingSpots.map((c) => (
        <Marker
          key={c.id}
          position={{ lat: c.lat, lng: c.lng }}
          onClick={() => setActive({ type: "cool", ...c })}
          icon={{
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: 7,
            fillColor: "#0A58CA",
            fillOpacity: 1,
            strokeColor: "#fff",
            strokeWeight: 2,
          }}
        />
      ))}

      {/* User location */}
      {userLocation && (
        <Marker
          position={userLocation}
          icon={{
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: 9,
            fillColor: "#111827",
            fillOpacity: 1,
            strokeColor: "#fff",
            strokeWeight: 3,
          }}
        />
      )}

      {active && (
        <InfoWindow position={{ lat: active.lat, lng: active.lng }} onCloseClick={() => setActive(null)}>
          <div style={{ minWidth: 140 }}>
            <p style={{ fontWeight: 700, margin: 0 }}>{active.name}</p>
            {active.type === "wbgt" ? (
              <p style={{ margin: "4px 0 0", color: levelToColor(active.level) }}>
                <span className="capitalize">{active.level}</span> heat stress
              </p>
            ) : (
              <p style={{ margin: "4px 0 0", color: "#0A58CA" }}>Cool spot · {active.type}</p>
            )}
          </div>
        </InfoWindow>
      )}
    </GoogleMap>
  );
}

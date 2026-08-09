import { useEffect, useState } from "react";
import api from "../lib/api";
import { useApp } from "../context/AppContext";
import MapView from "../components/MapView";
import { Button } from "../components/ui/button";
import { CloudRain, Flame, Droplets, Loader2 } from "lucide-react";

const LEGEND = [
  { label: "Low", color: "#10B981" },
  { label: "Moderate", color: "#F59E0B" },
  { label: "High", color: "#EF4444" },
  { label: "Very High", color: "#991B1B" },
];

export default function MapPage() {
  const { location } = useApp();
  const [wbgt, setWbgt] = useState([]);
  const [rain, setRain] = useState([]);
  const [spots, setSpots] = useState([]);
  const [showRain, setShowRain] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.get("/map/wbgt"), api.get("/map/rainfall"), api.get("/cooling/all")])
      .then(([w, r, c]) => {
        setWbgt(w.data.stations);
        setRain(r.data.stations);
        setSpots(c.data.spots);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="relative h-[calc(100vh-64px)] md:h-screen">
      <MapView userLocation={location} wbgtStations={wbgt} coolingSpots={spots} rainStations={rain} showRain={showRain} />

      {/* Title overlay */}
      <div className="absolute top-4 left-4 right-4 md:right-auto md:w-80 glass rounded-2xl p-4 z-10" data-testid="map-info-panel">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center">
            <Flame className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-heading font-bold text-lg leading-none">Heat-Risk Map</h1>
            <p className="text-xs text-muted-foreground">Live heat-stress stations across Singapore</p>
          </div>
          {loading && <Loader2 className="w-4 h-4 animate-spin text-primary ml-auto" />}
        </div>

        <div className="grid grid-cols-2 gap-2 mt-4">
          {LEGEND.map((l) => (
            <div key={l.label} className="flex items-center gap-2 text-sm">
              <span className="w-3.5 h-3.5 rounded-full" style={{ backgroundColor: l.color }} />
              {l.label}
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2 mt-4">
          <span className="flex items-center gap-1.5 text-sm"><Droplets className="w-4 h-4 text-primary" /> Cool spots</span>
          <span className="w-3 h-3 rounded-full bg-primary ml-1" />
        </div>

        <Button
          variant={showRain ? "default" : "outline"}
          size="sm"
          onClick={() => setShowRain((s) => !s)}
          className="w-full rounded-xl mt-4"
          data-testid="toggle-rain-btn"
        >
          <CloudRain className="w-4 h-4 mr-2" /> {showRain ? "Hide" : "Show"} rainfall overlay
        </Button>
      </div>
    </div>
  );
}

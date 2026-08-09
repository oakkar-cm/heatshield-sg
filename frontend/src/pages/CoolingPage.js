import { useEffect, useState } from "react";
import api from "../lib/api";
import { useApp } from "../context/AppContext";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Skeleton } from "../components/ui/skeleton";
import { Route, Navigation, Snowflake, Trees, Building2, Droplets, MapPin, ArrowRight, Wind } from "lucide-react";
import { toast } from "sonner";

const typeIcon = (type) => {
  if (type === "park") return Trees;
  if (type === "mall") return Building2;
  if (type === "community" || type === "public") return Building2;
  return Snowflake;
};

export default function CoolingPage() {
  const { location } = useApp();
  const [spots, setSpots] = useState(null);
  const [route, setRoute] = useState(null);
  const [routing, setRouting] = useState(null);

  useEffect(() => {
    api.get(`/cooling/spots?lat=${location.lat}&lng=${location.lng}&limit=8`)
      .then((r) => setSpots(r.data.spots))
      .catch(() => toast.error("Could not load cool spots"));
  }, [location.lat, location.lng]);

  const getRoute = async (spot) => {
    setRouting(spot.id);
    try {
      const { data } = await api.get(`/cooling/route?spot_id=${spot.id}&lat=${location.lat}&lng=${location.lng}`);
      setRoute(data);
    } catch (e) {
      toast.error("Could not build route");
    } finally {
      setRouting(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
      <div className="fade-up">
        <h1 className="font-heading font-bold text-3xl flex items-center gap-2">
          <Route className="w-7 h-7 text-primary" /> Cooling Routes
        </h1>
        <p className="text-muted-foreground mt-2">
          Real Singapore cool spots near you — open walking directions in Google Maps.
        </p>
      </div>

      {/* Nearest quick action */}
      {spots && spots[0] && (
        <Card className="p-5 rounded-3xl mt-6 bg-primary text-white border-0 flex items-center gap-4 fade-up" data-testid="nearest-quick-action">
          <div className="w-12 h-12 rounded-2xl bg-white/15 flex items-center justify-center shrink-0">
            <Snowflake className="w-6 h-6" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white/70 text-xs uppercase tracking-wider">Nearest cool spot</p>
            <p className="font-heading font-bold text-xl truncate">{spots[0].name}</p>
            <p className="text-white/80 text-sm">{spots[0].distance_km} km away</p>
          </div>
          <Button variant="secondary" className="rounded-xl shrink-0" onClick={() => getRoute(spots[0])} data-testid="quick-route-btn">
            <Navigation className="w-4 h-4 mr-2" /> Go
          </Button>
        </Card>
      )}

      {/* Route detail */}
      {route && (
        <Card className="p-6 rounded-3xl mt-6 border-2 border-primary/30 fade-up" data-testid="route-detail-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-widest font-semibold text-primary">Cooling route</p>
              <h3 className="font-heading font-bold text-xl mt-1">{route.destination.name}</h3>
              <p className="text-sm text-muted-foreground">{route.destination.distance_km} km · walking</p>
            </div>
            <a href={route.walking_url} target="_blank" rel="noreferrer">
              <Button className="rounded-xl" data-testid="open-in-maps-btn">Open in Maps <ArrowRight className="w-4 h-4 ml-2" /></Button>
            </a>
          </div>
          <div className="mt-4 space-y-2">
            {route.tips.map((t, i) => (
              <p key={i} className="flex gap-2 text-sm text-slate-700">
                <Wind className="w-4 h-4 text-primary shrink-0 mt-0.5" /> {t}
              </p>
            ))}
          </div>
        </Card>
      )}

      {/* Spot list */}
      <div className="grid sm:grid-cols-2 gap-4 mt-6">
        {!spots
          ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-3xl" />)
          : spots.map((s, i) => {
              const Icon = typeIcon(s.type);
              return (
                <Card key={s.id} className="p-5 rounded-3xl shadow-sm hover:-translate-y-0.5 transition-transform fade-up" style={{ animationDelay: `${i * 60}ms` }} data-testid={`cool-spot-${s.id}`}>
                  <div className="flex items-start gap-3">
                    <div className="w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                      <Icon className="w-6 h-6 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-heading font-semibold text-lg leading-tight">{s.name}</p>
                      <p className="text-sm text-muted-foreground flex items-center gap-1 capitalize">
                        <MapPin className="w-3.5 h-3.5" /> {s.distance_km} km · {s.type}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {s.amenities.map((a) => (
                      <span key={a} className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600 flex items-center gap-1">
                        {a === "water" && <Droplets className="w-3 h-3" />}{a}
                      </span>
                    ))}
                  </div>
                  <Button variant="outline" className="w-full rounded-xl mt-4" onClick={() => getRoute(s)} disabled={routing === s.id} data-testid={`route-btn-${s.id}`}>
                    <Navigation className="w-4 h-4 mr-2" /> {routing === s.id ? "Building…" : "Cooling route"}
                  </Button>
                </Card>
              );
            })}
      </div>
    </div>
  );
}

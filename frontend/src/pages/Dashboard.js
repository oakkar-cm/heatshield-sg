import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { useApp } from "../context/AppContext";
import { useAuth } from "../context/AuthContext";
import { heatClasses } from "../lib/heat";
import ForecastChart from "../components/ForecastChart";
import SavedPlaces from "../components/SavedPlaces";
import NotificationSettings from "../components/NotificationSettings";
import InstallAppCard from "../components/InstallAppCard";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Skeleton } from "../components/ui/skeleton";
import {
  Thermometer, Droplets, CloudRain, Wind, MapPin, Sparkles, Route, TrendingUp,
  AlertTriangle, Loader2, RefreshCw, Navigation,
} from "lucide-react";
import { toast } from "sonner";

const StatTile = ({ icon: Icon, label, value, unit }) => (
  <div className="bg-white rounded-2xl border border-border p-4 shadow-sm">
    <div className="flex items-center gap-2 text-slate-500">
      <Icon className="w-4 h-4" />
      <span className="text-xs uppercase tracking-wider font-semibold">{label}</span>
    </div>
    <p className="font-heading font-bold text-2xl mt-2">
      {value ?? "—"}
      {value != null && <span className="text-base text-slate-400 font-medium ml-1">{unit}</span>}
    </p>
  </div>
);

export default function Dashboard() {
  const { location, detectLocation, locating } = useApp();
  const { user } = useAuth();
  const [risk, setRisk] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [recs, setRecs] = useState(null);
  const [nearest, setNearest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recLoading, setRecLoading] = useState(true);

  const load = async () => {
    // Keep previous snapshot visible on refresh — only skeleton on first load
    if (!risk) setLoading(true);
    try {
      const [r, f, c] = await Promise.all([
        api.get(`/risk?lat=${location.lat}&lng=${location.lng}`),
        api.get(`/forecast?lat=${location.lat}&lng=${location.lng}`),
        api.get(`/cooling/spots?lat=${location.lat}&lng=${location.lng}&limit=1`),
      ]);
      setRisk(r.data);
      setForecast(f.data);
      setNearest(c.data.spots[0]);
    } catch (e) {
      toast.error("Could not load conditions");
    } finally {
      setLoading(false);
    }
  };

  const loadRecs = async () => {
    // AI tips are slower — don't blank the section if we already have tips
    if (!recs) setRecLoading(true);
    try {
      const { data } = await api.get(`/recommendations?lat=${location.lat}&lng=${location.lng}`);
      setRecs(data.recommendations);
    } catch (e) {
      setRecs(null);
    } finally {
      setRecLoading(false);
    }
  };

  useEffect(() => {
    load();
    loadRecs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.lat, location.lng]);

  const cond = risk?.conditions;
  const level = cond?.heat_level || "low";
  const hc = heatClasses(risk?.risk?.color || "low");
  const heatMeta = cond?.heat_meta;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 fade-up">
        <div>
          <p className="text-sm text-muted-foreground">Hello, {user?.name?.split(" ")[0] || "there"} 👋</p>
          <h1 className="font-heading font-bold text-3xl mt-1">Your heat snapshot</h1>
          <button onClick={detectLocation} className="flex items-center gap-1.5 text-sm text-primary mt-2" data-testid="dashboard-detect-location">
            {locating ? <Loader2 className="w-4 h-4 animate-spin" /> : <MapPin className="w-4 h-4" />}
            {location.label ? location.label : cond?.wbgt?.station ? `Near ${cond.wbgt.station}` : "Detect my location"}
          </button>
        </div>
        <Button variant="outline" size="icon" onClick={() => { load(); loadRecs(); }} className="rounded-xl" data-testid="refresh-btn">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Alert banner */}
      {risk?.risk?.score >= 60 && (
        <div className="flex items-center gap-3 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800 fade-up" data-testid="risk-alert-banner">
          <AlertTriangle className="w-6 h-6 shrink-0" />
          <p className="font-medium text-sm">
            {risk.risk.band} heat risk right now. {heatMeta?.message}
          </p>
        </div>
      )}

      {/* Hero: weather (iOS-style) + risk */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Current weather card */}
        <Card className={`lg:col-span-2 p-6 rounded-3xl border-0 text-white relative overflow-hidden ${hc.bg}`} data-testid="heat-level-card">
          {loading ? (
            <Skeleton className="h-40 w-full bg-white/20" />
          ) : (
            <div className="relative z-10">
              <p className="text-white/80 uppercase tracking-widest text-xs font-semibold">
                {location.label || "Current location"}
              </p>
              <div className="flex items-end gap-3 mt-2">
                <span className="font-heading font-extrabold text-6xl sm:text-7xl leading-none tracking-tight">
                  {cond?.air_temperature?.value != null ? Math.round(cond.air_temperature.value) : "—"}°
                </span>
                <div className="pb-2">
                  <p className="font-heading font-semibold text-xl sm:text-2xl">{cond?.condition || heatMeta?.label}</p>
                  <p className="text-white/80 text-sm mt-0.5">
                    Feels like {cond?.feels_like?.value != null ? Math.round(cond.feels_like.value) : "—"}°
                  </p>
                </div>
              </div>
              <p className="text-white/90 mt-4 max-w-md text-sm">
                Heat stress {heatMeta?.label?.toLowerCase() || "—"}. {heatMeta?.message}
              </p>
              <div className="flex flex-wrap gap-6 mt-6">
                <div>
                  <p className="text-white/70 text-xs uppercase tracking-wider">Humidity</p>
                  <p className="font-heading font-bold text-xl">{cond?.humidity?.value != null ? Math.round(cond.humidity.value) : "—"}%</p>
                </div>
                <div>
                  <p className="text-white/70 text-xs uppercase tracking-wider">Wind</p>
                  <p className="font-heading font-bold text-xl">{cond?.wind?.value != null ? Math.round(cond.wind.value) : "—"} km/h</p>
                </div>
                <div>
                  <p className="text-white/70 text-xs uppercase tracking-wider">Heat stress</p>
                  <p className="font-heading font-bold text-xl">{heatMeta?.label || "—"}</p>
                </div>
                <div>
                  <p className="text-white/70 text-xs uppercase tracking-wider">Rain</p>
                  <p className="font-heading font-bold text-xl">{cond?.rainfall?.value ?? "—"} mm</p>
                </div>
              </div>
              {cond?.area_forecast?.forecast && (
                <p className="text-white/75 text-xs mt-4">
                  NEA area forecast ({cond.area_forecast.area}): {cond.area_forecast.forecast}
                </p>
              )}
            </div>
          )}
          <div className="absolute -bottom-16 -right-16 w-64 h-64 rounded-full bg-white/10" />
        </Card>

        {/* Personal risk score */}
        <Card className="p-6 rounded-3xl shadow-sm" data-testid="risk-score-card">
          <p className="text-xs uppercase tracking-widest font-semibold text-slate-500">Your personal risk</p>
          {loading ? (
            <Skeleton className="h-32 w-full mt-4" />
          ) : (
            <>
              <div className="flex items-baseline gap-2 mt-3">
                <span className={`font-heading font-extrabold text-5xl ${hc.text}`}>{risk?.risk?.score}</span>
                <span className="text-slate-400 font-medium">/100</span>
              </div>
              <div className={`inline-block px-3 py-1 rounded-full text-sm font-semibold mt-2 ${hc.soft} ${hc.text}`}>
                {risk?.risk?.band} risk
              </div>
              <div className="mt-4 space-y-1.5">
                {risk?.risk?.factors?.slice(0, 3).map((f, i) => (
                  <p key={i} className="text-sm text-slate-600 flex gap-2">
                    <span className={`mt-1.5 w-1.5 h-1.5 rounded-full ${hc.bg} shrink-0`} /> {f}
                  </p>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile icon={Thermometer} label="Feels Like" value={cond?.feels_like?.value != null ? Math.round(cond.feels_like.value) : null} unit="°C" />
        <StatTile icon={Droplets} label="Humidity" value={cond?.humidity?.value != null ? Math.round(cond.humidity.value) : null} unit="%" />
        <StatTile icon={Wind} label="Wind" value={cond?.wind?.value != null ? Math.round(cond.wind.value) : null} unit="km/h" />
        <StatTile icon={CloudRain} label="Heat stress" value={heatMeta?.label} unit="" />
      </div>

      {/* AI recommendations + Nearest cool spot */}
      <div className="grid lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 p-6 rounded-3xl shadow-sm" data-testid="recommendations-card">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="font-heading font-semibold text-lg">AI recommendations for you</h3>
              <p className="text-xs text-muted-foreground">Tailored to your profile & current conditions</p>
            </div>
          </div>
          {recLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground mt-6"><Loader2 className="w-4 h-4 animate-spin" /> Thinking…</div>
          ) : recs ? (
            <ul className="mt-5 space-y-3">
              {recs.map((r, i) => (
                <li key={i} className="flex gap-3 fade-up" style={{ animationDelay: `${i * 80}ms` }}>
                  <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">{i + 1}</span>
                  <span className="text-slate-700">{r}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground mt-6">Recommendations unavailable right now.</p>
          )}
        </Card>

        <Card className="p-6 rounded-3xl shadow-sm flex flex-col" data-testid="nearest-cool-spot-card">
          <div className="flex items-center gap-2">
            <Route className="w-5 h-5 text-primary" />
            <h3 className="font-heading font-semibold text-lg">Nearest cool spot</h3>
          </div>
          {nearest ? (
            <div className="mt-4 flex-1">
              <p className="font-heading font-bold text-xl">{nearest.name}</p>
              <p className="text-sm text-muted-foreground capitalize">{nearest.type} · {nearest.distance_km} km away</p>
              <div className="flex flex-wrap gap-1.5 mt-3">
                {nearest.amenities?.slice(0, 4).map((a) => (
                  <span key={a} className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600">{a}</span>
                ))}
              </div>
            </div>
          ) : (
            <Skeleton className="h-24 w-full mt-4" />
          )}
          <Link to="/cooling" className="mt-4">
            <Button className="w-full rounded-xl" data-testid="find-cooling-route-btn">
              <Navigation className="w-4 h-4 mr-2" /> Find cooling route
            </Button>
          </Link>
        </Card>
      </div>

      {/* Install app prompt (PWA) */}
      <InstallAppCard />

      {/* Alerts + Saved places */}
      <div className="grid lg:grid-cols-2 gap-6">
        <NotificationSettings />
        <SavedPlaces />
      </div>

      {/* Forecast */}
      <Card className="p-6 rounded-3xl shadow-sm" data-testid="forecast-card">
        <div className="flex items-center gap-2 mb-1">
          <TrendingUp className="w-5 h-5 text-primary" />
          <h3 className="font-heading font-semibold text-lg">Next-hours forecast (live)</h3>
        </div>
        {forecast ? (
          <>
            <p className="text-sm text-muted-foreground mb-4">{forecast.summary}</p>
            <ForecastChart points={forecast.points} peak={forecast.peak} />
          </>
        ) : (
          <Skeleton className="h-48 w-full" />
        )}
      </Card>
    </div>
  );
}

import { useEffect, useState } from "react";
import api from "../lib/api";
import { useApp } from "../context/AppContext";
import { useNavigate } from "react-router-dom";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "./ui/dialog";
import { MapPin, Home, Briefcase, Plus, Trash2, Navigation, Loader2, Route } from "lucide-react";
import { toast } from "sonner";

const labelIcon = (label) => (label === "Home" ? Home : label === "Work" ? Briefcase : MapPin);

export default function SavedPlaces() {
  const { location, selectLocation, detectLocation } = useApp();
  const navigate = useNavigate();
  const [places, setPlaces] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ label: "Home" });
  const [saving, setSaving] = useState(false);

  const load = () => api.get("/locations").then((r) => setPlaces(r.data.locations)).catch(() => {});
  useEffect(() => { load(); }, []);

  const quickSave = async (label) => {
    if (!navigator.geolocation) return toast.error("Location not available");
    setSaving(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const { data } = await api.post("/locations", { label, lat: pos.coords.latitude, lng: pos.coords.longitude });
          setPlaces(data.locations);
          toast.success(`${label} saved from your current location`);
        } catch (e) { toast.error("Could not save"); }
        finally { setSaving(false); }
      },
      () => { setSaving(false); toast.error("Enable location to save this place"); },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  const saveCustom = async () => {
    if (!navigator.geolocation) return;
    setSaving(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const { data } = await api.post("/locations", { label: form.label || "Place", lat: pos.coords.latitude, lng: pos.coords.longitude });
          setPlaces(data.locations);
          setOpen(false);
          toast.success("Place saved");
        } finally { setSaving(false); }
      },
      () => { setSaving(false); toast.error("Enable location"); }
    );
  };

  const remove = async (id) => {
    const { data } = await api.delete(`/locations/${id}`);
    setPlaces(data.locations);
  };

  const isActive = (p) => Math.abs(p.lat - location.lat) < 1e-4 && Math.abs(p.lng - location.lng) < 1e-4;

  const routeFrom = (p) => {
    selectLocation({ lat: p.lat, lng: p.lng, label: p.label });
    toast.success(`Finding cooling routes from ${p.label}`);
    navigate("/cooling");
  };

  return (
    <Card className="p-6 rounded-3xl shadow-sm" data-testid="saved-places-card">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MapPin className="w-5 h-5 text-primary" />
          <h3 className="font-heading font-semibold text-lg">Saved places</h3>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" variant="outline" className="rounded-xl" data-testid="add-place-btn"><Plus className="w-4 h-4 mr-1" /> Add</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Save current location</DialogTitle></DialogHeader>
            <p className="text-sm text-muted-foreground">We'll save your current GPS position under this label.</p>
            <Input placeholder="Label (e.g. Mum's place)" value={form.label} onChange={(e) => setForm({ label: e.target.value })} data-testid="place-label-input" className="mt-2" />
            <DialogFooter><Button onClick={saveCustom} disabled={saving} className="rounded-xl" data-testid="save-place-btn">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save place"}</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <p className="text-sm text-muted-foreground mt-1">Tap a place to see its heat risk & cooling routes instantly.</p>

      {/* Quick add Home / Work */}
      {(!places.some((p) => p.label === "Home") || !places.some((p) => p.label === "Work")) && (
        <div className="flex gap-2 mt-4">
          {!places.some((p) => p.label === "Home") && (
            <Button variant="outline" size="sm" className="rounded-xl" onClick={() => quickSave("Home")} disabled={saving} data-testid="quick-save-home">
              <Home className="w-4 h-4 mr-1.5" /> Set Home here
            </Button>
          )}
          {!places.some((p) => p.label === "Work") && (
            <Button variant="outline" size="sm" className="rounded-xl" onClick={() => quickSave("Work")} disabled={saving} data-testid="quick-save-work">
              <Briefcase className="w-4 h-4 mr-1.5" /> Set Work here
            </Button>
          )}
        </div>
      )}

      <div className="mt-4 space-y-2">
        {places.length === 0 && <p className="text-sm text-slate-400">No saved places yet.</p>}
        {places.map((p) => {
          const Icon = labelIcon(p.label);
          const active = isActive(p);
          return (
            <div key={p.id} className={`flex items-center gap-3 p-3 rounded-xl border ${active ? "border-primary bg-primary/5" : "border-border"}`} data-testid={`place-${p.id}`}>
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${active ? "bg-primary text-white" : "bg-slate-100 text-slate-600"}`}>
                <Icon className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium">{p.label} {active && <span className="text-xs text-primary">· active</span>}</p>
                <p className="text-xs text-slate-500">{p.lat.toFixed(3)}, {p.lng.toFixed(3)}</p>
              </div>
              <Button size="sm" variant={active ? "default" : "outline"} className="rounded-lg" onClick={() => selectLocation({ lat: p.lat, lng: p.lng, label: p.label })} data-testid={`use-place-${p.id}`}>
                <Navigation className="w-4 h-4 mr-1" /> Use
              </Button>
              <Button size="sm" variant="outline" className="rounded-lg" onClick={() => routeFrom(p)} data-testid={`route-place-${p.id}`}>
                <Route className="w-4 h-4 mr-1" /> Route
              </Button>
              <button onClick={() => remove(p.id)} className="text-slate-400 hover:text-red-600" data-testid={`delete-place-${p.id}`}><Trash2 className="w-4 h-4" /></button>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

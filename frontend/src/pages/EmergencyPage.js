import { useEffect, useState } from "react";
import api from "../lib/api";
import { useApp } from "../context/AppContext";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Checkbox } from "../components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "../components/ui/dialog";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";
import {
  ShieldAlert, Phone, Plus, Trash2, Stethoscope, ClipboardCheck, HardHat, CheckCircle2,
  AlertTriangle, X, Loader2, MapPin, PhoneCall,
} from "lucide-react";
import { heatClasses } from "../lib/heat";
import { toast } from "sonner";

function SosButton() {
  const { location } = useApp();
  const [counting, setCounting] = useState(false);
  const [count, setCount] = useState(5);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!counting) return;
    if (count === 0) {
      trigger();
      return;
    }
    const t = setTimeout(() => setCount((c) => c - 1), 1000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [counting, count]);

  const trigger = async () => {
    setCounting(false);
    try {
      const { data } = await api.post("/emergency/sos", { lat: location.lat, lng: location.lng });
      setResult(data);
      toast.success(data.message);
    } catch (e) {
      toast.error("SOS failed. Call 995 directly.");
    }
  };

  const start = () => { setCount(5); setCounting(true); };
  const cancel = () => { setCounting(false); setCount(5); };

  return (
    <Card className="p-6 rounded-3xl border-2 border-red-200 bg-red-50" data-testid="sos-panel">
      <div className="flex flex-col items-center text-center">
        <h2 className="font-heading font-bold text-2xl text-red-700">Emergency SOS</h2>
        <p className="text-sm text-red-600/80 mt-1 max-w-sm">
          Logs your SOS, pushes an alert to your devices, and gives one-tap Call / SMS to caregivers with your live location.
        </p>

        {!counting ? (
          <button
            onClick={start}
            data-testid="sos-button"
            className="mt-6 w-40 h-40 rounded-full bg-red-600 text-white font-heading font-extrabold text-2xl flex items-center justify-center sos-pulse active:scale-95 transition-transform"
          >
            <div className="flex flex-col items-center">
              <ShieldAlert className="w-10 h-10 mb-1" />
              SOS
            </div>
          </button>
        ) : (
          <div className="mt-6 flex flex-col items-center">
            <button
              onClick={cancel}
              data-testid="sos-cancel-button"
              className="w-40 h-40 rounded-full bg-red-700 text-white font-heading font-extrabold flex flex-col items-center justify-center"
            >
              <span className="text-5xl">{count}</span>
              <span className="text-sm flex items-center gap-1 mt-1"><X className="w-4 h-4" /> Tap to cancel</span>
            </button>
            <p className="text-sm text-red-600 mt-3">Sending SOS in {count}s…</p>
          </div>
        )}

        <div className="flex gap-3 mt-6">
          <a href="tel:995"><Button variant="destructive" className="rounded-xl" data-testid="call-995-btn"><PhoneCall className="w-4 h-4 mr-2" /> Call 995</Button></a>
          <a href="tel:999"><Button variant="outline" className="rounded-xl border-red-300 text-red-700"><PhoneCall className="w-4 h-4 mr-2" /> Police 999</Button></a>
        </div>
      </div>

      {result && (
        <div className="mt-6 p-4 rounded-2xl bg-white border border-red-200 text-left" data-testid="sos-result">
          <p className="font-semibold text-red-700 flex items-center gap-2"><CheckCircle2 className="w-5 h-5" /> {result.message}</p>
          {result.location_link && (
            <a href={result.location_link} target="_blank" rel="noreferrer" className="text-sm text-primary flex items-center gap-1 mt-2">
              <MapPin className="w-4 h-4" /> Open your live location
            </a>
          )}
          {result.contacts?.length > 0 && (
            <div className="mt-3 space-y-2">
              <p className="text-sm font-medium text-slate-700">Contact caregivers now</p>
              {result.contacts.map((c) => (
                <div key={c.id || c.phone} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-slate-600 min-w-[7rem]">{c.name}</span>
                  {c.tel_url && (
                    <a href={c.tel_url}>
                      <Button size="sm" variant="destructive" className="rounded-lg h-8">Call</Button>
                    </a>
                  )}
                  {c.sms_url && (
                    <a href={c.sms_url}>
                      <Button size="sm" variant="outline" className="rounded-lg h-8 border-red-300 text-red-700">SMS location</Button>
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function Contacts() {
  const [contacts, setContacts] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", relation: "" });

  const load = () => api.get("/emergency/contacts").then((r) => setContacts(r.data.contacts));
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.name || !form.phone) return toast.error("Name and phone required");
    const { data } = await api.post("/emergency/contacts", form);
    setContacts(data.contacts);
    setForm({ name: "", phone: "", relation: "" });
    setOpen(false);
    toast.success("Caregiver added");
  };

  const remove = async (id) => {
    const { data } = await api.delete(`/emergency/contacts/${id}`);
    setContacts(data.contacts);
  };

  return (
    <Card className="p-6 rounded-3xl shadow-sm" data-testid="contacts-panel">
      <div className="flex items-center justify-between">
        <h3 className="font-heading font-semibold text-lg flex items-center gap-2"><Phone className="w-5 h-5 text-primary" /> Caregivers & contacts</h3>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="rounded-xl" data-testid="add-contact-btn"><Plus className="w-4 h-4 mr-1" /> Add</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Add caregiver contact</DialogTitle></DialogHeader>
            <div className="space-y-3 py-2">
              <Input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="contact-name-input" />
              <Input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid="contact-phone-input" />
              <Input placeholder="Relation (e.g. Son)" value={form.relation} onChange={(e) => setForm({ ...form, relation: e.target.value })} data-testid="contact-relation-input" />
            </div>
            <DialogFooter><Button onClick={add} data-testid="save-contact-btn" className="rounded-xl">Save contact</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {contacts.length === 0 ? (
        <p className="text-sm text-muted-foreground mt-4">No contacts yet. Add a caregiver to alert during an SOS.</p>
      ) : (
        <div className="mt-4 space-y-2">
          {contacts.map((c) => (
            <div key={c.id} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50" data-testid={`contact-${c.id}`}>
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold">
                {c.name[0]?.toUpperCase()}
              </div>
              <div className="flex-1">
                <p className="font-medium">{c.name} <span className="text-xs text-muted-foreground">{c.relation}</span></p>
                <a href={`tel:${c.phone}`} className="text-sm text-primary">{c.phone}</a>
              </div>
              <button onClick={() => remove(c.id)} className="text-slate-400 hover:text-red-600" data-testid={`delete-contact-${c.id}`}><Trash2 className="w-4 h-4" /></button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function SymptomChecker() {
  const [symptoms, setSymptoms] = useState([]);
  const [selected, setSelected] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.get("/emergency/symptoms").then((r) => setSymptoms(r.data.symptoms)); }, []);

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const check = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/emergency/symptom-check", { symptoms: selected });
      setResult(data);
    } finally { setLoading(false); }
  };

  const hc = result ? heatClasses(result.color) : null;

  return (
    <Card className="p-6 rounded-3xl shadow-sm" data-testid="symptom-checker">
      <h3 className="font-heading font-semibold text-lg flex items-center gap-2"><Stethoscope className="w-5 h-5 text-primary" /> Heat-illness symptom checker</h3>
      <p className="text-sm text-muted-foreground mt-1">Select any symptoms you or someone nearby is experiencing.</p>
      <div className="grid sm:grid-cols-2 gap-2 mt-4">
        {symptoms.map((s) => (
          <label key={s.id} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer ${selected.includes(s.id) ? "border-primary bg-primary/5" : "border-border"}`} data-testid={`symptom-${s.id}`}>
            <Checkbox checked={selected.includes(s.id)} onCheckedChange={() => toggle(s.id)} />
            <span className="text-sm">{s.label}</span>
          </label>
        ))}
      </div>
      <Button onClick={check} disabled={loading} className="rounded-xl mt-4" data-testid="check-symptoms-btn">
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Check symptoms"}
      </Button>

      {result && (
        <div className={`mt-5 p-5 rounded-2xl border ${hc.soft} ${hc.border}`} data-testid="symptom-result">
          <div className="flex items-center gap-2">
            {result.severity === "emergency" ? <AlertTriangle className={`w-6 h-6 ${hc.text}`} /> : <CheckCircle2 className={`w-6 h-6 ${hc.text}`} />}
            <div>
              <p className={`font-heading font-bold text-lg ${hc.text}`}>{result.condition}</p>
              <p className="text-xs uppercase tracking-wider text-slate-500">{result.severity}</p>
            </div>
          </div>
          <ul className="mt-3 space-y-1.5">
            {result.advice.map((a, i) => (
              <li key={i} className="text-sm text-slate-700 flex gap-2"><span className={`mt-1.5 w-1.5 h-1.5 rounded-full ${hc.bg} shrink-0`} /> {a}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function Checklists() {
  const [data, setData] = useState(null);
  const [checked, setChecked] = useState({});

  useEffect(() => { api.get("/emergency/checklists").then((r) => setData(r.data)); }, []);
  if (!data) return <Loader2 className="w-5 h-5 animate-spin text-primary" />;

  return (
    <div className="space-y-6">
      <Card className="p-6 rounded-3xl shadow-sm" data-testid="work-rest-guidance">
        <h3 className="font-heading font-semibold text-lg flex items-center gap-2"><HardHat className="w-5 h-5 text-primary" /> Outdoor work / rest guidance</h3>
        <p className="text-sm text-muted-foreground mt-1">Aligned to Singapore's heat-stress advisory for outdoor work.</p>
        <div className="mt-4 space-y-2">
          {data.work_rest.map((w) => {
            const hc = heatClasses(w.color);
            return (
              <div key={w.level} className={`flex items-center gap-3 p-3 rounded-xl border ${hc.border} ${hc.soft}`}>
                <span className={`w-3 h-3 rounded-full ${hc.bg} shrink-0`} />
                <div className="flex-1">
                  <p className={`font-semibold ${hc.text} capitalize`}>{w.level} heat stress</p>
                  <p className="text-sm text-slate-600">{w.work} · {w.rest}</p>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Card className="p-6 rounded-3xl shadow-sm" data-testid="checklists-panel">
        <h3 className="font-heading font-semibold text-lg flex items-center gap-2"><ClipboardCheck className="w-5 h-5 text-primary" /> Preparedness checklists</h3>
        <Accordion type="single" collapsible className="mt-3">
          {Object.entries(data.checklists).map(([key, cl]) => (
            <AccordionItem key={key} value={key} data-testid={`checklist-${key}`}>
              <AccordionTrigger className="font-heading">{cl.title}</AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  {cl.items.map((item, i) => {
                    const id = `${key}-${i}`;
                    return (
                      <label key={id} className="flex items-center gap-3 cursor-pointer">
                        <Checkbox checked={!!checked[id]} onCheckedChange={() => setChecked((c) => ({ ...c, [id]: !c[id] }))} />
                        <span className={`text-sm ${checked[id] ? "line-through text-slate-400" : "text-slate-700"}`}>{item}</span>
                      </label>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </Card>
    </div>
  );
}

export default function EmergencyPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
      <h1 className="font-heading font-bold text-3xl flex items-center gap-2 fade-up">
        <ShieldAlert className="w-7 h-7 text-red-600" /> Emergency & Preparedness
      </h1>
      <p className="text-muted-foreground mt-2">SOS, symptom checker, caregivers and heat-safety checklists.</p>

      <Tabs defaultValue="sos" className="mt-6">
        <TabsList className="grid grid-cols-3 rounded-xl h-auto p-1">
          <TabsTrigger value="sos" className="rounded-lg py-2" data-testid="tab-sos">SOS</TabsTrigger>
          <TabsTrigger value="symptoms" className="rounded-lg py-2" data-testid="tab-symptoms">Symptoms</TabsTrigger>
          <TabsTrigger value="prepare" className="rounded-lg py-2" data-testid="tab-prepare">Prepare</TabsTrigger>
        </TabsList>
        <TabsContent value="sos" className="mt-6 space-y-6">
          <SosButton />
          <Contacts />
        </TabsContent>
        <TabsContent value="symptoms" className="mt-6">
          <SymptomChecker />
        </TabsContent>
        <TabsContent value="prepare" className="mt-6">
          <Checklists />
        </TabsContent>
      </Tabs>
    </div>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Checkbox } from "../components/ui/checkbox";
import { Users, HeartPulse, HardHat, Check, Loader2 } from "lucide-react";
import { toast } from "sonner";

const TYPES = [
  { id: "citizen", label: "Citizen", desc: "Daily heat awareness, alerts & safe routes", icon: Users, age: "adult", exposure: "medium" },
  { id: "elderly", label: "Elderly / Vulnerable", desc: "Caregiver alerts, SOS & higher heat-risk weighting", icon: HeartPulse, age: "elderly", exposure: "low" },
  { id: "outdoor_worker", label: "Outdoor Worker", desc: "Simple work/rest guidance for outdoor work", icon: HardHat, age: "adult", exposure: "high" },
];

const HEALTH = [
  "Heart condition", "Respiratory illness", "Diabetes", "Pregnancy", "On medication (heat-sensitive)", "Previous heat illness",
];

export default function Onboarding() {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [userType, setUserType] = useState(null);
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(false);

  const toggleFlag = (f) => setFlags((cur) => (cur.includes(f) ? cur.filter((x) => x !== f) : [...cur, f]));

  const finish = async () => {
    setLoading(true);
    const t = TYPES.find((x) => x.id === userType);
    try {
      await api.put("/profile", {
        user_type: userType,
        age_group: t.age,
        outdoor_exposure: t.exposure,
        health_flags: flags,
        onboarded: true,
      });
      await refreshUser();
      toast.success("Profile ready!");
      navigate("/");
    } catch (e) {
      toast.error("Could not save profile");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <div className="w-full max-w-2xl fade-up">
        <div className="flex items-center gap-2 mb-8">
          <span className={`h-1.5 flex-1 rounded-full ${step >= 1 ? "bg-primary" : "bg-slate-200"}`} />
          <span className={`h-1.5 flex-1 rounded-full ${step >= 2 ? "bg-primary" : "bg-slate-200"}`} />
        </div>

        {step === 1 && (
          <div>
            <h1 className="font-heading font-bold text-3xl">Who are you?</h1>
            <p className="text-muted-foreground mt-2">We'll tailor alerts, thresholds and the interface for you.</p>
            <div className="grid gap-4 mt-8">
              {TYPES.map((t) => (
                <button
                  key={t.id}
                  data-testid={`usertype-${t.id}`}
                  onClick={() => setUserType(t.id)}
                  className={`flex items-center gap-4 p-5 rounded-2xl border-2 text-left transition-all hover:-translate-y-0.5 ${
                    userType === t.id ? "border-primary bg-primary/5" : "border-border bg-white"
                  }`}
                >
                  <div className={`w-14 h-14 rounded-xl flex items-center justify-center shrink-0 ${userType === t.id ? "bg-primary text-white" : "bg-slate-100 text-slate-600"}`}>
                    <t.icon className="w-7 h-7" />
                  </div>
                  <div className="flex-1">
                    <p className="font-heading font-semibold text-lg">{t.label}</p>
                    <p className="text-sm text-muted-foreground">{t.desc}</p>
                  </div>
                  {userType === t.id && <Check className="w-6 h-6 text-primary" />}
                </button>
              ))}
            </div>
            <Button disabled={!userType} onClick={() => setStep(2)} data-testid="onboarding-next" className="w-full h-12 rounded-xl mt-8 text-base font-semibold">
              Continue
            </Button>
          </div>
        )}

        {step === 2 && (
          <div>
            <h1 className="font-heading font-bold text-3xl">Any health conditions?</h1>
            <p className="text-muted-foreground mt-2">These raise your personal heat-risk score. Optional — you can skip.</p>
            <div className="grid sm:grid-cols-2 gap-3 mt-8">
              {HEALTH.map((h) => (
                <label
                  key={h}
                  data-testid={`health-${h}`}
                  className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-colors ${
                    flags.includes(h) ? "border-primary bg-primary/5" : "border-border bg-white"
                  }`}
                >
                  <Checkbox checked={flags.includes(h)} onCheckedChange={() => toggleFlag(h)} />
                  <span className="font-medium">{h}</span>
                </label>
              ))}
            </div>
            <div className="flex gap-3 mt-8">
              <Button variant="outline" onClick={() => setStep(1)} className="h-12 rounded-xl px-6">Back</Button>
              <Button onClick={finish} disabled={loading} data-testid="onboarding-finish" className="flex-1 h-12 rounded-xl text-base font-semibold">
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Finish setup"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Flame, Loader2, ShieldCheck, Droplets, Map } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const { login, register, formatApiErrorDetail } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "login") {
        await login(form.email, form.password);
        navigate("/");
      } else {
        const user = await register({ name: form.name, email: form.email, password: form.password, user_type: "citizen" });
        navigate(user.onboarded ? "/" : "/onboarding");
      }
      toast.success(mode === "login" ? "Welcome back" : "Account created");
    } catch (err) {
      const msg = formatApiErrorDetail(err.response?.data?.detail) || err.message;
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left brand panel */}
      <div className="hidden lg:flex flex-col justify-between p-12 bg-primary text-white relative overflow-hidden">
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-white/15 flex items-center justify-center backdrop-blur">
              <Flame className="w-6 h-6" />
            </div>
            <div>
              <p className="font-heading font-extrabold text-2xl leading-none">HeatShield SG</p>
              <p className="text-sm text-white/70 tracking-widest uppercase mt-1">Climate Resilience</p>
            </div>
          </div>
          <h1 className="font-heading font-extrabold text-4xl xl:text-5xl mt-16 leading-tight">
            Stay ahead of the heat.
          </h1>
          <p className="text-white/80 text-lg mt-4 max-w-md leading-relaxed">
            Live heat alerts, personalised risk scores, cool-spot walking directions and AI advice —
            grounded in NEA and live location weather for Singapore.
          </p>
          <div className="mt-12 space-y-4 max-w-sm">
            {[
              { icon: ShieldCheck, t: "Personalised heat-risk warnings" },
              { icon: Droplets, t: "Nearest real cool spots & Maps walking routes" },
              { icon: Map, t: "Live heat map & hourly forecast" },
            ].map((f, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-white/15 flex items-center justify-center">
                  <f.icon className="w-5 h-5" />
                </div>
                <span className="text-white/90">{f.t}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="text-white/50 text-sm relative z-10">Live data: NEA · Open-Meteo · Groq AI</p>
        <div className="absolute -bottom-24 -right-24 w-96 h-96 rounded-full bg-white/5" />
        <div className="absolute top-1/3 -left-12 w-48 h-48 rounded-full bg-white/5" />
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md fade-up">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <Flame className="w-5 h-5 text-white" />
            </div>
            <span className="font-heading font-bold text-xl">HeatShield SG</span>
          </div>
          <h2 className="font-heading font-bold text-3xl">{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="text-muted-foreground mt-2">
            {mode === "login" ? "Log in to see your personal heat risk." : "Set up your profile for tailored heat alerts."}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            {mode === "register" && (
              <div>
                <Label htmlFor="name">Full name</Label>
                <Input id="name" data-testid="register-name-input" required value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5 h-12 rounded-xl" placeholder="Tan Ah Kow" />
              </div>
            )}
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" data-testid="login-email-input" required value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-1.5 h-12 rounded-xl" placeholder="you@example.sg" />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" data-testid="login-password-input" required value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-1.5 h-12 rounded-xl" placeholder="••••••••" />
            </div>

            {error && <p className="text-sm text-red-600" data-testid="auth-error">{error}</p>}

            <Button type="submit" disabled={loading} data-testid="auth-submit-btn" className="w-full h-12 rounded-xl text-base font-semibold">
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : mode === "login" ? "Log in" : "Create account"}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground mt-6">
            {mode === "login" ? "New to HeatShield?" : "Already have an account?"}{" "}
            <button
              data-testid="toggle-auth-mode"
              className="text-primary font-semibold"
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            >
              {mode === "login" ? "Create an account" : "Log in"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}

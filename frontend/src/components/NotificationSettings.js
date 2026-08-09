import { useEffect, useState } from "react";
import api from "../lib/api";
import { pushSupported, getSubscriptionState, enablePush, disablePush, sendTestPush } from "../lib/push";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Switch } from "./ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Bell, BellRing, Send, Loader2, Smartphone, AlertCircle, Moon } from "lucide-react";
import { toast } from "sonner";

const THRESHOLDS = ["Moderate", "High", "Very High"];
const HOURS = Array.from({ length: 24 }, (_, h) => h);
const fmtHour = (h) => `${String(h).padStart(2, "0")}:00`;

export default function NotificationSettings() {
  const [state, setState] = useState({ supported: true, subscribed: false, permission: "default" });
  const [busy, setBusy] = useState(false);
  const [threshold, setThreshold] = useState("High");
  const [quiet, setQuiet] = useState({ enabled: false, start: 22, end: 7 });

  useEffect(() => {
    if (pushSupported()) getSubscriptionState().then(setState);
    else setState({ supported: false, subscribed: false, permission: "denied" });
    api.get("/auth/me").then((r) => {
      setThreshold(r.data.notify_threshold || "High");
      if (r.data.quiet_hours) setQuiet(r.data.quiet_hours);
    }).catch(() => {});
  }, []);

  const toggle = async (on) => {
    setBusy(true);
    try {
      if (on) {
        await enablePush();
        toast.success("Heat alerts enabled — even when the app is closed");
      } else {
        await disablePush();
        toast.success("Heat alerts turned off");
      }
      setState(await getSubscriptionState());
    } catch (e) {
      toast.error(e.message || "Could not update notifications");
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    try {
      await sendTestPush();
      toast.success("Test alert sent! Lock your phone — it should still buzz.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Enable notifications first");
    } finally {
      setBusy(false);
    }
  };

  const changeThreshold = async (v) => {
    setThreshold(v);
    await api.put("/push/threshold", { threshold: v }).catch(() => {});
    toast.success(`You'll be alerted at ${v} risk and above`);
  };

  const saveQuiet = async (next) => {
    setQuiet(next);
    await api.put("/push/quiet-hours", next).catch(() => {});
  };

  return (
    <Card className="p-6 rounded-3xl shadow-sm" data-testid="notification-settings-card">
      <div className="flex items-center gap-2">
        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
          <BellRing className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h3 className="font-heading font-semibold text-lg">Heat alerts on your phone</h3>
          <p className="text-xs text-muted-foreground">Push alerts even when the app is closed or your screen is locked</p>
        </div>
      </div>

      {!state.supported ? (
        <div className="flex items-start gap-2 mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>Push notifications aren't supported in this browser. On iPhone, add HeatShield to your Home Screen (Share → Add to Home Screen) first.</span>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mt-5 p-4 rounded-2xl bg-slate-50" data-testid="push-toggle-row">
            <span className="flex items-center gap-2 font-medium">
              <Bell className="w-5 h-5 text-slate-500" /> Enable heat alerts
            </span>
            {busy ? <Loader2 className="w-5 h-5 animate-spin text-primary" /> : (
              <Switch checked={state.subscribed} onCheckedChange={toggle} data-testid="push-enable-toggle" />
            )}
          </div>

          <div className="mt-4">
            <p className="text-sm font-medium mb-1.5">Alert me at this risk level</p>
            <Select value={threshold} onValueChange={changeThreshold}>
              <SelectTrigger className="rounded-xl h-11" data-testid="threshold-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {THRESHOLDS.map((t) => <SelectItem key={t} value={t}>{t} and above</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <Button variant="outline" className="w-full rounded-xl mt-4" onClick={test} disabled={busy || !state.subscribed} data-testid="test-push-btn">
            <Send className="w-4 h-4 mr-2" /> Send me a test alert
          </Button>

          {/* Quiet hours */}
          <div className="mt-5 p-4 rounded-2xl bg-slate-50" data-testid="quiet-hours-row">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-medium">
                <Moon className="w-5 h-5 text-slate-500" /> Quiet hours (mute overnight)
              </span>
              <Switch checked={quiet.enabled} onCheckedChange={(v) => saveQuiet({ ...quiet, enabled: v })} data-testid="quiet-hours-toggle" />
            </div>
            {quiet.enabled && (
              <div className="flex items-center gap-2 mt-3">
                <div className="flex-1">
                  <p className="text-xs text-slate-500 mb-1">From</p>
                  <Select value={String(quiet.start)} onValueChange={(v) => saveQuiet({ ...quiet, start: Number(v) })}>
                    <SelectTrigger className="rounded-xl h-10" data-testid="quiet-start-select"><SelectValue /></SelectTrigger>
                    <SelectContent className="max-h-60">{HOURS.map((h) => <SelectItem key={h} value={String(h)}>{fmtHour(h)}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="flex-1">
                  <p className="text-xs text-slate-500 mb-1">Until</p>
                  <Select value={String(quiet.end)} onValueChange={(v) => saveQuiet({ ...quiet, end: Number(v) })}>
                    <SelectTrigger className="rounded-xl h-10" data-testid="quiet-end-select"><SelectValue /></SelectTrigger>
                    <SelectContent className="max-h-60">{HOURS.map((h) => <SelectItem key={h} value={String(h)}>{fmtHour(h)}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </div>

          <p className="flex items-center gap-1.5 text-xs text-muted-foreground mt-3">
            <Smartphone className="w-3.5 h-3.5" /> Tip: enable, then lock your phone and tap "test" to see it work in the background.
          </p>
        </>
      )}
    </Card>
  );
}

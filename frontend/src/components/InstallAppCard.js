import { useEffect, useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Download, Share, Plus, X, Smartphone } from "lucide-react";

const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

const isIOS = () => /iphone|ipad|ipod/i.test(window.navigator.userAgent);

export default function InstallAppCard() {
  const [deferred, setDeferred] = useState(null);
  const [dismissed, setDismissed] = useState(() => localStorage.getItem("hs_install_dismissed") === "1");
  const [installed, setInstalled] = useState(isStandalone());

  useEffect(() => {
    const onPrompt = (e) => { e.preventDefault(); setDeferred(e); };
    const onInstalled = () => setInstalled(true);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed || dismissed) return null;
  const ios = isIOS();
  // Only show if we can prompt (Android/desktop) or it's iOS Safari (manual add)
  if (!deferred && !ios) return null;

  const install = async () => {
    if (!deferred) return;
    deferred.prompt();
    await deferred.userChoice;
    setDeferred(null);
  };

  const close = () => { setDismissed(true); localStorage.setItem("hs_install_dismissed", "1"); };

  return (
    <Card className="p-5 rounded-3xl border-0 bg-primary text-white relative overflow-hidden" data-testid="install-app-card">
      <button onClick={close} className="absolute top-3 right-3 text-white/70 hover:text-white" data-testid="dismiss-install-btn"><X className="w-5 h-5" /></button>
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-2xl bg-white/15 flex items-center justify-center shrink-0">
          <Smartphone className="w-6 h-6" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-heading font-bold text-lg">Install HeatShield</h3>
          {ios ? (
            <p className="text-white/85 text-sm mt-1">
              Add to your Home Screen to get lock-screen heat alerts: tap <Share className="inline w-4 h-4 mx-0.5" /> <b>Share</b>, then <b>“Add to Home Screen”</b> <Plus className="inline w-4 h-4 mx-0.5" />.
            </p>
          ) : (
            <>
              <p className="text-white/85 text-sm mt-1">Install the app for instant access and background heat alerts.</p>
              <Button onClick={install} variant="secondary" className="rounded-xl mt-3" data-testid="install-app-btn">
                <Download className="w-4 h-4 mr-2" /> Install app
              </Button>
            </>
          )}
        </div>
      </div>
    </Card>
  );
}

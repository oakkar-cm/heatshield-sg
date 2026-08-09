import { NavLink, useNavigate } from "react-router-dom";
import { Home, Map, Route, MessageCircle, ShieldAlert, LogOut, MapPin, Loader2, Flame } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useApp } from "../context/AppContext";
import { Button } from "./ui/button";

const NAV = [
  { to: "/", label: "Home", icon: Home, testid: "nav-home" },
  { to: "/map", label: "Map", icon: Map, testid: "nav-map" },
  { to: "/cooling", label: "Cooling", icon: Route, testid: "nav-cooling" },
  { to: "/chat", label: "Ask AI", icon: MessageCircle, testid: "nav-chat" },
  { to: "/emergency", label: "SOS", icon: ShieldAlert, testid: "nav-emergency" },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const { detectLocation, locating } = useApp();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-64 border-r border-border bg-white shrink-0 fixed h-screen">
        <div className="px-6 py-6 flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center">
            <Flame className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="font-heading font-bold text-lg leading-none">HeatShield</p>
            <p className="text-xs text-muted-foreground tracking-widest uppercase">SG</p>
          </div>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              data-testid={`${n.testid}-desktop`}
              className={({ isActive }) =>
                `app-nav-item flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-colors ${
                  isActive ? "bg-primary text-white" : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              <n.icon className="w-5 h-5" />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-border space-y-3">
          <div className="text-xs text-muted-foreground truncate">{user?.email}</div>
          <Button variant="outline" size="sm" className="w-full rounded-lg" onClick={onLogout} data-testid="logout-btn">
            <LogOut className="w-4 h-4 mr-2" /> Log out
          </Button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 md:ml-64 flex flex-col min-w-0">
        {/* Top bar (mobile) */}
        <header className="md:hidden sticky top-0 z-30 glass px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Flame className="w-4 h-4 text-white" />
            </div>
            <span className="font-heading font-bold">HeatShield SG</span>
          </div>
          <button onClick={detectLocation} data-testid="detect-location-btn" className="text-primary" aria-label="Detect location">
            {locating ? <Loader2 className="w-5 h-5 animate-spin" /> : <MapPin className="w-5 h-5" />}
          </button>
        </header>

        <main className="flex-1 pb-24 md:pb-8">{children}</main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 glass border-t border-white/40 flex justify-around px-2 py-2">
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            data-testid={`${n.testid}-mobile`}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg text-xs font-medium ${
                isActive ? "text-primary" : "text-slate-500"
              }`
            }
          >
            <n.icon className={`w-6 h-6 ${n.to === "/emergency" ? "text-red-600" : ""}`} />
            {n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

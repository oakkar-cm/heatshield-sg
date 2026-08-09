import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { AppProvider } from "@/context/AppContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import MapPage from "@/pages/MapPage";
import CoolingPage from "@/pages/CoolingPage";
import ChatPage from "@/pages/ChatPage";
import EmergencyPage from "@/pages/EmergencyPage";

function FullLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-primary" />
    </div>
  );
}

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null) return <FullLoader />;
  if (user === false) return <Navigate to="/login" replace />;
  if (!user.onboarded) return <Navigate to="/onboarding" replace />;
  return <Layout>{children}</Layout>;
}

function PublicOnly({ children }) {
  const { user } = useAuth();
  if (user === null) return <FullLoader />;
  if (user && user.onboarded) return <Navigate to="/" replace />;
  if (user && !user.onboarded) return <Navigate to="/onboarding" replace />;
  return children;
}

function OnboardingRoute() {
  const { user } = useAuth();
  if (user === null) return <FullLoader />;
  if (user === false) return <Navigate to="/login" replace />;
  if (user.onboarded) return <Navigate to="/" replace />;
  return <Onboarding />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
      <Route path="/onboarding" element={<OnboardingRoute />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/map" element={<Protected><MapPage /></Protected>} />
      <Route path="/cooling" element={<Protected><CoolingPage /></Protected>} />
      <Route path="/chat" element={<Protected><ChatPage /></Protected>} />
      <Route path="/emergency" element={<Protected><EmergencyPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppProvider>
          <AppRoutes />
          <Toaster position="top-center" richColors />
        </AppProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

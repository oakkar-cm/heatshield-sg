import { createContext, useContext, useEffect, useState } from "react";
import { SG_CENTER } from "../lib/heat";
import { registerServiceWorker } from "../lib/push";

const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

export function AppProvider({ children }) {
  const [location, setLocationState] = useState(() => {
    const saved = localStorage.getItem("hs_location");
    return saved ? JSON.parse(saved) : { ...SG_CENTER, label: "Singapore" };
  });
  const [locating, setLocating] = useState(false);

  const persistLocation = (loc) => {
    setLocationState(loc);
    localStorage.setItem("hs_location", JSON.stringify(loc));
  };

  // pick a saved place / explicit location (one tap)
  const selectLocation = (loc) => persistLocation(loc);

  const detectLocation = () => {
    setLocating(true);
    if (!navigator.geolocation) {
      setLocating(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        persistLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude, label: "Current location" });
        setLocating(false);
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  useEffect(() => {
    registerServiceWorker();
    // Only auto-detect GPS on first ever visit; otherwise keep the user's chosen/saved location.
    if (!localStorage.getItem("hs_location")) detectLocation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Clear any leftover simplified-mode class from older sessions
    document.body.classList.remove("simplified");
    localStorage.removeItem("hs_simplified");
  }, []);

  return (
    <AppContext.Provider value={{ location, setLocation: persistLocation, selectLocation, locating, detectLocation }}>
      {children}
    </AppContext.Provider>
  );
}

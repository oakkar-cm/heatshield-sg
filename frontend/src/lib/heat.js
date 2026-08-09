// Heat-level colour + label helpers. Colour is always paired with text/icon (accessibility).
export const HEAT_COLORS = {
  low: "#10B981",
  moderate: "#F59E0B",
  high: "#EF4444",
  "very high": "#991B1B",
  extreme: "#991B1B",
};

export function heatColor(colorKey) {
  return HEAT_COLORS[colorKey] || HEAT_COLORS.low;
}

export function heatClasses(colorKey) {
  const map = {
    low: { bg: "bg-emerald-500", soft: "bg-emerald-50", text: "text-emerald-600", border: "border-emerald-200" },
    moderate: { bg: "bg-amber-500", soft: "bg-amber-50", text: "text-amber-600", border: "border-amber-200" },
    high: { bg: "bg-red-500", soft: "bg-red-50", text: "text-red-600", border: "border-red-200" },
    extreme: { bg: "bg-red-900", soft: "bg-red-100", text: "text-red-800", border: "border-red-300" },
    "very high": { bg: "bg-red-900", soft: "bg-red-100", text: "text-red-800", border: "border-red-300" },
  };
  return map[colorKey] || map.low;
}

export const SG_CENTER = { lat: 1.3521, lng: 103.8198 };

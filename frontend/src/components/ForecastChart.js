import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceDot } from "recharts";

export default function ForecastChart({ points = [], peak }) {
  const data = points.map((p) => ({
    ...p,
    value: p.feels_like ?? p.wbgt ?? p.temp,
  }));
  const peakY = peak?.feels_like ?? peak?.wbgt;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="heatGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#F59E0B" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#F59E0B" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#64748b" }} interval={1} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: "#64748b" }} domain={["dataMin - 1", "dataMax + 1"]} axisLine={false} tickLine={false} unit="°" />
        <Tooltip
          formatter={(v, _n, item) => {
            const row = item?.payload || {};
            const temp = row.temp != null ? ` · air ${row.temp}°C` : "";
            return [`Feels like ${v}°C${temp}`, "Forecast"];
          }}
          contentStyle={{ borderRadius: 12, border: "1px solid #E2E8F0", fontSize: 13 }}
        />
        <Area type="monotone" dataKey="value" stroke="#D97706" strokeWidth={2.5} fill="url(#heatGrad)" />
        {peak?.label != null && peakY != null && (
          <ReferenceDot x={peak.label} y={peakY} r={5} fill="#EF4444" stroke="#fff" strokeWidth={2} />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}

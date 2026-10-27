import { useEffect, useState } from "react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer } from "recharts";

const j = (u) => fetch(u).then((r) => r.json());
const fmt = (v) => (v == null ? "–" : Math.round(v).toLocaleString());
const card = { background: "#fff", borderRadius: 8, padding: 16, margin: "12px 0", boxShadow: "0 1px 3px #0002" };
const Stat = ({ k, v, unit = "MW" }) => (<div style={{ minWidth: 110 }}><div style={{ fontSize: 12, color: "#666" }}>{k}</div><div style={{ fontSize: 22, fontWeight: 600 }}>{fmt(v)} <small>{unit}</small></div></div>);
const Chart = ({ title, children, h = 260 }) => (<div style={card}><h3 style={{ margin: 0 }}>{title}</h3><ResponsiveContainer width="100%" height={h}>{children}</ResponsiveContainer></div>);

export default function App() {
  const [date, setDate] = useState("2026-01-15");
  const [cutoff, setCutoff] = useState(9);
  const [day, setDay] = useState(null), [acc, setAcc] = useState(null), [hor, setHor] = useState([]);
  useEffect(() => { j(`/api/forecast?date=${date}&cutoff_hour=${cutoff}`).then(setDay); }, [date, cutoff]);
  useEffect(() => { j(`/api/accuracy?cutoff_hour=${cutoff}`).then(setAcc); }, [cutoff]);
  useEffect(() => { j("/api/horizon").then(setHor); }, []);
  const o = acc?.overall || {};
  const pub = day?.rows?.[0]?.publishTime;
  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h2>UK Wind Generation: Day-Ahead Forecast Monitor</h2>
      <div style={card}>
        Delivery day <input type="date" min="2026-01-01" max="2026-01-31" value={date} onChange={(e) => setDate(e.target.value)} />{" "}
        Decision cutoff on D-1 (UTC hour) <input type="number" min="0" max="23" value={cutoff} onChange={(e) => setCutoff(+e.target.value)} style={{ width: 60 }} />
        <div style={{ fontSize: 12, color: "#666", marginTop: 6 }}>Uses the latest WINDFOR forecast published at or before the cutoff. Latest publish used: {pub || "–"}</div>
      </div>
      <Chart title={`Forecast known at decision time vs actual – ${date} (MW)`} h={320}>
        <LineChart data={day?.rows || []}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="startTime" tickFormatter={(t) => t.slice(11, 16)} /><YAxis /><Tooltip /><Legend />
          <Line dataKey="forecast" name="Forecast" stroke="#2563eb" dot={false} /><Line dataKey="actual" name="Actual" stroke="#16a34a" dot={false} /></LineChart>
      </Chart>
      <div style={{ ...card, display: "flex", gap: 24, flexWrap: "wrap" }}>
        <b style={{ width: "100%" }}>January 2026 day-ahead forecast error (forecast – actual)</b>
        <Stat k="MAE" v={o.mae} /><Stat k="RMSE" v={o.rmse} /><Stat k="Bias" v={o.bias} /><Stat k="MAPE" v={o.mape} unit="%" />
        <Stat k="P90 abs error" v={o.p90_abs} /><Stat k="P95 abs error" v={o.p95_abs} /><Stat k="Max abs error" v={o.max_abs} />
        <div style={{ width: "100%", fontSize: 13 }}>Planning buffer: keep ~{fmt(o.p90_abs)} MW of extra cover to be right 9 times in 10 (empirical P90 of absolute error). Positive bias = forecast over-states wind (risk of under-buying).</div>
      </div>
      <Chart title="Daily MAE (MW)"><BarChart data={acc?.daily || []}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="day" tickFormatter={(t) => t.slice(8)} /><YAxis /><Tooltip /><Bar dataKey="mae" fill="#2563eb" /></BarChart></Chart>
      <Chart title="Error distribution (MW, forecast – actual)"><BarChart data={acc?.error_hist || []}><XAxis dataKey="bin" tickFormatter={fmt} /><YAxis /><Tooltip /><Bar dataKey="count" fill="#f59e0b" /></BarChart></Chart>
      <Chart title="MAE by hour of delivery day (MW)"><BarChart data={acc?.by_hour || []}><XAxis dataKey="hour" /><YAxis /><Tooltip /><Bar dataKey="mae" fill="#7c3aed" /></BarChart></Chart>
      <Chart title="MAE by forecast lead time (hours before target, 4h bins)"><LineChart data={hor}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="lead_h" /><YAxis /><Tooltip /><Line dataKey="mae" stroke="#dc2626" /></LineChart></Chart>
    </div>
  );
}

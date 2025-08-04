import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const WINDOW_COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7300"];
const WINDOW_LABELS = ["Q1-Feb", "Q2-May", "Q3-Aug", "Q4-Nov"];

const YearlyLineCharts = ({ perYearData }) => {
  const years = Object.keys(perYearData).sort();
  const [yearIdx, setYearIdx] = useState(years.length - 1); // Show most recent year by default

  if (years.length === 0) return <div>No yearly data available.</div>;
  const year = years[yearIdx];
  const windowData = perYearData[year];

  return (
    <div className="yearly-line-charts">
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', margin: 16 }}>
        <button onClick={() => setYearIdx((prev) => Math.max(0, prev - 1))} disabled={yearIdx === 0}>Previous Year</button>
        <h2 style={{ margin: '0 24px' }}>{year}</h2>
        <button onClick={() => setYearIdx((prev) => Math.min(years.length - 1, prev + 1))} disabled={yearIdx === years.length - 1}>Next Year</button>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 32 }}>
        {WINDOW_LABELS.map((label, i) => (
          windowData[label] && (
            <div key={label} style={{ minWidth: 320, maxWidth: 380, background: '#f9f9fc', borderRadius: 8, padding: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}>
              <h4 style={{ textAlign: 'center', marginBottom: 8 }}>{label}</h4>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={windowData[label]} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="close" stroke={WINDOW_COLORS[i]} dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )
        ))}
      </div>
    </div>
  );
};

export default YearlyLineCharts;

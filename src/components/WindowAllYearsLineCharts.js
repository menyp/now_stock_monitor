import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const WINDOW_COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7300", "#d88484", "#84b6d8", "#a684d8", "#d8c684", "#84d8a6", "#d884b6"];
const WINDOW_LABELS = ["Q1-Feb", "Q2-May", "Q3-Aug", "Q4-Nov"];

const WindowAllYearsLineCharts = ({ perWindowAllYears }) => {
  return (
    <div className="window-all-years-line-charts">
      <h2 style={{marginTop:32, marginBottom:8}}>Window Line Charts (All Years)</h2>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 32 }}>
        {WINDOW_LABELS.map((label) => {
          const yearsObj = perWindowAllYears[label] || {};
          const years = Object.keys(yearsObj).sort();
          if (years.length === 0) return null;
          return (
            <div key={label} style={{ minWidth: 350, maxWidth: 420, background: '#f9f9fc', borderRadius: 8, padding: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}>
              <h4 style={{ textAlign: 'center', marginBottom: 8 }}>{label}</h4>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  {years.map((year, i) => (
                    <Line
                      key={year}
                      type="monotone"
                      dataKey="close"
                      data={yearsObj[year]}
                      name={year}
                      stroke={WINDOW_COLORS[i % WINDOW_COLORS.length]}
                      dot={false}
                      strokeWidth={2}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default WindowAllYearsLineCharts;

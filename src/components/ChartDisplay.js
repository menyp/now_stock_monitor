import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar } from 'recharts';

// Dummy data generator for demonstration
const generateData = (years) => {
  const data = [];
  const baseYear = new Date().getFullYear();
  for (let i = 0; i < years; i++) {
    data.push({
      year: baseYear - i,
      value: Math.floor(Math.random() * 100) + 50,
      barValue: Math.floor(Math.random() * 80) + 20
    });
  }
  return data.reverse();
};

const chartTypes = [
  { type: 'line', label: 'Line Chart' },
  { type: 'bar', label: 'Bar Chart' }
];

const ChartDisplay = ({ years, onBack }) => {
  const [chartIndex, setChartIndex] = useState(0);
  const data = generateData(years);

  const handlePrev = () => {
    setChartIndex((prev) => (prev === 0 ? chartTypes.length - 1 : prev - 1));
  };

  const handleNext = () => {
    setChartIndex((prev) => (prev === chartTypes.length - 1 ? 0 : prev + 1));
  };

  return (
    <div className="chart-display-container">
      <div className="chart-nav">
        <button onClick={handlePrev}>Previous</button>
        <span>{chartTypes[chartIndex].label}</span>
        <button onClick={handleNext}>Next</button>
      </div>
      <div className="chart-area">
        {chartTypes[chartIndex].type === 'line' ? (
          <LineChart width={600} height={300} data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" stroke="#8884d8" activeDot={{ r: 8 }} />
          </LineChart>
        ) : (
          <BarChart width={600} height={300} data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="year" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="barValue" fill="#82ca9d" />
          </BarChart>
        )}
      </div>
      <button className="back-btn" onClick={onBack}>Back</button>
    </div>
  );
};

export default ChartDisplay;

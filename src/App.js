import React, { useState } from 'react';
import './App.css';
import AnalysisResult from './components/AnalysisResult';
import YearlyLineCharts from './components/YearlyLineCharts';

function App() {
  const [years, setYears] = useState(10);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleYearsChange = (value) => {
    setYears(value);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await fetch(`/analyze?years=${years}`);
      if (!resp.ok) throw new Error('Analysis failed.');
      const data = await resp.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  return (
    <div className="app-container">
      <h1>ServiceNow Stock Window Analysis</h1>
      <form className="year-input-form" onSubmit={handleSubmit}>
        <label htmlFor="years">Number of Years to Analyze:</label>
        <input
          type="number"
          id="years"
          min="1"
          max="50"
          value={years}
          onChange={(e) => handleYearsChange(Number(e.target.value))}
          required
        />
        <button type="submit" disabled={loading}>Analyze</button>
      </form>
      {loading && <div style={{marginTop:16}}>Analyzing... Please wait.</div>}
      {error && <div className="error-message">{error}</div>}
      <AnalysisResult result={result} />
      {result && result.per_year_window_data && (
        <>
          <h2 style={{marginTop:32, marginBottom:8}}>Yearly Window Line Charts</h2>
          <YearlyLineCharts perYearData={result.per_year_window_data} />
        </>
      )}
      {result && result.per_window_all_years && (
        <WindowAllYearsLineCharts perWindowAllYears={result.per_window_all_years} />
      )}
    </div>
  );
}

export default App;

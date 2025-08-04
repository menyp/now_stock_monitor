import React from 'react';

const AnalysisResult = ({ result }) => {
  if (!result) return null;

  const { recommendation, summary, composite_chart, window_charts } = result;

  return (
    <div className="analysis-result">
      <h2>Recommendation</h2>
      <div className="recommendation-box">{recommendation}</div>

      <h2>Composite Chart</h2>
      {composite_chart && (
        <img
          src={`data:image/png;base64,${composite_chart}`}
          alt="Composite Chart"
          style={{ maxWidth: '100%', border: '1px solid #ccc', borderRadius: 8 }}
        />
      )}

      <h2>Quarterly Bar Charts</h2>
      <div className="window-charts">
        {window_charts &&
          Object.entries(window_charts).map(([label, b64]) => (
            <div key={label} style={{ display: 'inline-block', margin: 16, textAlign: 'center' }}>
              <h4>{label}</h4>
              <img
                src={`data:image/png;base64,${b64}`}
                alt={label}
                style={{ maxWidth: 300, border: '1px solid #ccc', borderRadius: 8 }}
              />
            </div>
          ))}
      </div>

      <h2>Summary Table</h2>
      <div style={{ overflowX: 'auto' }}>
        <table className="summary-table">
          <thead>
            <tr>
              {summary && summary.length > 0 &&
                Object.keys(summary[0]).map((key) => <th key={key}>{key}</th>)}
            </tr>
          </thead>
          <tbody>
            {summary &&
              summary.map((row, idx) => (
                <tr key={idx}>
                  {Object.values(row).map((val, i) => (
                    <td key={i}>{val}</td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AnalysisResult;

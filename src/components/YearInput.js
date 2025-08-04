import React, { useState } from 'react';

const YearInput = ({ years, onYearsChange, onSubmit }) => {
  const [inputValue, setInputValue] = useState(years);

  const handleChange = (e) => {
    const value = parseInt(e.target.value, 10) || 1;
    setInputValue(value);
    onYearsChange(value);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <form className="year-input-form" onSubmit={handleSubmit}>
      <label htmlFor="years">Number of Years to Analyze:</label>
      <input
        type="number"
        id="years"
        min="1"
        max="50"
        value={inputValue}
        onChange={handleChange}
        required
      />
      <button type="submit">Analyze</button>
    </form>
  );
};

export default YearInput;

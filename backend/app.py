import os
import io
import base64
import sys
from flask import Flask, request, jsonify

# Add parent directory to sys.path so we can import analyze_windows
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from analyze_windows import run_analysis_for_years

app = Flask(__name__)

@app.route('/analyze', methods=['GET'])
def analyze():
    years = int(request.args.get('years', 10))
    result = run_analysis_for_years(years)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)

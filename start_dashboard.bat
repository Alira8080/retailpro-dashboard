@echo off
cd /d "%~dp0"
echo === RetailPro Dashboard ===
pip install -r requirements.txt -q
if not exist sales.csv python generate_sample_data.py
start http://localhost:8501
streamlit run dashboard.py

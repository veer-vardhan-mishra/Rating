Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "Starting School Teacher Feedback & Evaluation System" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# Install dependencies if needed
python -m pip install -r requirements.txt

# Run Streamlit
Write-Host "Launching Streamlit server on 0.0.0.0:8501..." -ForegroundColor Green
python -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0

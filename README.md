# 🤖 AI Fake News Detector & Explainability Platform

A machine learning web application and developer REST API for classifying news articles as **REAL** or **FAKE** with **Explainable AI (XAI)** word-level decision signals.

Powered by TF-IDF n-gram vectorization and Logistic Regression, featuring MongoDB persistence for prediction history and telemetry, and full fallback support when database storage is offline.

---

## ✨ Features

- **Dual Input Modes**: Analyze raw pasted text or scrape public article URLs (with Server-Side Request Forgery / SSRF protection).
- **Explainable AI (XAI)**: Displays top positive and negative word weights showing why the model arrived at its verdict.
- **Visual Analytics Dashboard**: Live metrics for Total Checks, Real vs Fake counts, Avg. Confidence, interactive Doughnut Chart, and Confusion Matrix.
- **User Feedback Loop**: Users can vote on prediction accuracy (`👍 Accurate` / `👎 Inaccurate`) to capture false positives/negatives for retraining.
- **Export History**: Download full prediction logs to CSV directly from the dashboard.
- **Developer REST API**: Programmatic JSON endpoints (`/api/predict` and `/api/health`) for integration with mobile apps, browser extensions, or bots.
- **Production-Ready**: Supports Gunicorn (Linux/Containers), Waitress (Windows), and Docker Compose.

---

## 🛠️ Tech Stack

- **Machine Learning**: `scikit-learn`, `pandas`, `numpy`, `matplotlib`, `seaborn`
- **Backend**: `Flask 3.x`, `pymongo`, `requests`, `beautifulsoup4`, `python-dotenv`
- **WSGI Servers**: `gunicorn` (Linux/Docker), `waitress` (Windows)
- **Frontend**: Vanilla CSS with glassmorphism, responsive Inter typography, Chart.js
- **Database**: MongoDB (Local or MongoDB Atlas) with graceful offline fallback

---

## 🚀 Getting Started

### 1. Environment Setup

```powershell
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt
```

### 2. Configure MongoDB (Optional)

Copy `.env.example` to `.env` and set your connection URI:

```env
MONGO_URI=mongodb://localhost:27017/
FLASK_DEBUG=false
```

*Note: The app runs with full classification capability even if MongoDB is not installed or configured.*

### 3. Run the Application

**Development Server:**
```powershell
python app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

**Windows Production (Waitress):**
```powershell
waitress-serve --port=5000 app:app
```

**Docker & Docker Compose:**
```bash
docker compose up --build
```

---

## 🔌 Developer REST API

### Health Check

```bash
curl http://127.0.0.1:5000/api/health
```

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "vectorizer_loaded": true,
  "database_connected": true,
  "accuracy": "98.7"
}
```

### Classify News via API

**Raw Text Analysis:**
```bash
curl -X POST http://127.0.0.1:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"news": "The White House announced a formal diplomatic agreement during the summit today."}'
```

**URL Analysis:**
```bash
curl -X POST http://127.0.0.1:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"url": "https://en.wikipedia.org/wiki/News"}'
```

**Response Payload:**
```json
{
  "status": "success",
  "prediction": "REAL",
  "confidence": 99.4,
  "explainability": {
    "real_signals": [
      {"word": "summit", "weight": 1.45},
      {"word": "formal", "weight": 0.88}
    ],
    "fake_signals": []
  }
}
```

---

## 📊 Retraining the Model

To retrain the model with dateline leakage filtering:

```powershell
# Combine Fake.csv and True.csv
python training/prepare_dataset.py

# Train model, save metrics, and generate confusion matrix
python training/train.py

# Generate standalone confusion matrix plot
python confusion_matrix.py
```

The evaluation outputs `model/model.pkl`, `model/vectorizer.pkl`, `model/evaluation_metrics.pkl`, and synchronizes `static/confusion_matrix.png` for the web dashboard.

---

## 🧪 Testing

Run the automated integration and regression test suite:

```powershell
python -m pytest
```

Check model inference or test MongoDB connectivity interactively:

```powershell
python test_model.py
python test_mongodb.py
```

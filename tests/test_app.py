import app as news_app


def test_home_renders_without_mongodb(monkeypatch):
    monkeypatch.setattr(news_app, "collection", None)
    response = news_app.app.test_client().get("/")

    assert response.status_code == 200
    assert b"AI Fake News Detector" in response.data
    assert b"Prediction history is unavailable" in response.data


def test_predict_rejects_blank_article(monkeypatch):
    monkeypatch.setattr(news_app, "collection", None)
    response = news_app.app.test_client().post("/predict", data={"news": "  "})

    assert response.status_code == 400
    assert b"Enter an article before checking it." in response.data


def test_predict_returns_model_result_without_database(monkeypatch):
    monkeypatch.setattr(news_app, "collection", None)
    response = news_app.app.test_client().post(
        "/predict", data={"news": "A report describes a public event and its verified details."}
    )

    assert response.status_code == 200
    assert b"AI confidence" in response.data
    assert b"Prediction history is unavailable" in response.data


def test_url_prediction_fetches_once_and_keeps_url(monkeypatch):
    monkeypatch.setattr(news_app, "collection", None)
    calls = []

    def extract(url):
        calls.append(url)
        return "Sample headline", "A sufficiently detailed article about a public event."

    monkeypatch.setattr(news_app, "extract_news_from_url", extract)
    response = news_app.app.test_client().post(
        "/predict-url", data={"url": "https://news.example/article"}
    )

    assert response.status_code == 200
    assert calls == ["https://news.example/article"]
    assert b"Sample headline" in response.data
    assert b"https://news.example/article" in response.data


def test_url_extraction_error_keeps_unavailable_history_notice(monkeypatch):
    monkeypatch.setattr(news_app, "collection", None)
    monkeypatch.setattr(news_app, "extract_news_from_url", lambda _url: (None, None))
    response = news_app.app.test_client().post(
        "/predict-url", data={"url": "https://news.example/broken"}
    )

    assert response.status_code == 400
    assert b"Could not extract article text" in response.data
    assert b"Prediction history is unavailable" in response.data


def test_clear_history_reports_unconfigured_database(monkeypatch):
    monkeypatch.setattr(news_app, "collection", None)
    response = news_app.app.test_client().post("/clear-history")

    assert response.status_code == 503
    assert b"MongoDB is not configured" in response.data


# =====================================================================
# Tests for New Features (Explainability, REST API, SSRF, Feedback, Export)
# =====================================================================

def test_explain_prediction_produces_signals():
    text = "The White House released a formal statement regarding the international summit."
    signals = news_app.explain_prediction(text, top_k=3)

    assert "real_signals" in signals
    assert "fake_signals" in signals
    assert isinstance(signals["real_signals"], list)
    assert isinstance(signals["fake_signals"], list)


def test_api_health_endpoint():
    client = news_app.app.test_client()
    response = client.get("/api/health")

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "healthy"
    assert json_data["model_loaded"] is True
    assert json_data["vectorizer_loaded"] is True


def test_api_predict_json(monkeypatch):
    monkeypatch.setattr(news_app, "collection", None)
    client = news_app.app.test_client()
    response = client.post(
        "/api/predict",
        json={"news": "Breaking secret conspiracy revealed in shocking leaked documents."}
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert json_data["prediction"] in ("FAKE", "REAL")
    assert isinstance(json_data["confidence"], (int, float))
    assert "explainability" in json_data


def test_api_predict_rejects_missing_content():
    client = news_app.app.test_client()
    response = client.post("/api/predict", json={})

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["status"] == "error"


def test_feedback_endpoint_records(monkeypatch):
    monkeypatch.setattr(news_app, "feedback_collection", None)
    client = news_app.app.test_client()
    response = client.post(
        "/feedback",
        json={"prediction": "REAL", "is_correct": True, "news": "Sample text"}
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] in ("success", "received")


def test_export_history_without_database(monkeypatch):
    monkeypatch.setattr(news_app, "collection", None)
    client = news_app.app.test_client()
    response = client.get("/export-history")

    assert response.status_code == 503


def test_ssrf_protection_blocks_internal_addresses():
    assert news_app.is_safe_url("http://127.0.0.1:5000/admin") is False
    assert news_app.is_safe_url("http://localhost:8080/secret") is False
    assert news_app.is_safe_url("http://192.168.1.1/router") is False
    assert news_app.is_safe_url("http://10.0.0.1/internal") is False
    assert news_app.is_safe_url("ftp://example.com/file") is False

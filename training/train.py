from pathlib import Path
import os
import re
import pickle
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    ConfusionMatrixDisplay
)

BASE_DIR = Path(__file__).resolve().parent.parent

# 1. Load dataset
data_path = BASE_DIR / "dataset" / "news.csv"
if not data_path.exists():
    raise FileNotFoundError(f"Combined dataset not found at {data_path}. Run training/prepare_dataset.py first.")

data = pd.read_csv(data_path)

print("=" * 50)
print("AI FAKE NEWS DETECTION - MODEL TRAINING")
print("=" * 50)

print("\nDataset loaded successfully!")
print("Total news:", len(data))


# 2. Check required columns
required_columns = ["title", "text", "label"]

for column in required_columns:
    if column not in data.columns:
        raise ValueError(f"Required column missing: {column}")


# 3. Clean dataset & remove publisher dateline leakage
data["title"] = data["title"].fillna("")
data["text"] = data["text"].fillna("")
data = data.dropna(subset=["label"])

def clean_news_text(text: str) -> str:
    """Strip datelines and agency watermarks to reduce publisher bias."""
    text = re.sub(r'^[A-Z\s,]+(?:\([A-Za-z\s]+\))?\s*-\s*', '', text)
    text = re.sub(r'\(Reuters\)', '', text, flags=re.IGNORECASE)
    return text.strip()

data["cleaned_text"] = data["text"].astype(str).apply(clean_news_text)
data["content"] = (
    data["title"].astype(str) + " " + data["cleaned_text"]
).str.strip()

data = data[data["content"] != ""]

# Remove duplicate news to reduce data leakage
data = data.drop_duplicates(subset=["content"])

X = data["content"]
y = data["label"]

print("\nDataset after cleaning:", len(data))
print("\nClass distribution:")
print(y.value_counts())


# 4. Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

print("\nTraining samples:", len(X_train))
print("Testing samples:", len(X_test))


# 5. TF-IDF vectorization
vectorizer = TfidfVectorizer(
    stop_words="english",
    max_df=0.7,
    ngram_range=(1, 2),
    max_features=50000
)

X_train_tfidf = vectorizer.fit_transform(X_train)
X_test_tfidf = vectorizer.transform(X_test)

print("\nTF-IDF conversion completed!")


# 6. Create and train model
model = LogisticRegression(max_iter=1000, C=1.0, random_state=42)

model.fit(X_train_tfidf, y_train)

print("Model training completed!")


# 7. Predictions
y_pred = model.predict(X_test_tfidf)


# 8. Calculate evaluation metrics
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(
    y_test, y_pred, average="weighted", zero_division=0
)
recall = recall_score(
    y_test, y_pred, average="weighted", zero_division=0
)
f1 = f1_score(
    y_test, y_pred, average="weighted", zero_division=0
)


# 9. Display results
print("\n" + "=" * 50)
print("MODEL EVALUATION RESULTS")
print("=" * 50)

print(f"\nAccuracy  : {accuracy * 100:.2f}%")
print(f"Precision : {precision * 100:.2f}%")
print(f"Recall    : {recall * 100:.2f}%")
print(f"F1-Score  : {f1 * 100:.2f}%")


# 10. Detailed classification report
print("\nCLASSIFICATION REPORT")
print("-" * 50)

print(
    classification_report(
        y_test,
        y_pred,
        zero_division=0
    )
)


# 11. Confusion matrix
labels = model.classes_

cm = confusion_matrix(
    y_test,
    y_pred,
    labels=labels
)

print("CONFUSION MATRIX")
print("-" * 50)

print("Class order:", list(labels))
print(cm)


# 12. Save evaluation metrics and plot
model_dir = BASE_DIR / "model"
static_dir = BASE_DIR / "static"
model_dir.mkdir(parents=True, exist_ok=True)
static_dir.mkdir(parents=True, exist_ok=True)

with open(model_dir / "accuracy.txt", "w", encoding="utf-8") as file:
    file.write(f"{accuracy * 100:.2f}")

metrics = {
    "accuracy": round(accuracy * 100, 2),
    "precision": round(precision * 100, 2),
    "recall": round(recall * 100, 2),
    "f1_score": round(f1 * 100, 2),
    "class_labels": [str(label) for label in labels],
    "confusion_matrix": cm.tolist()
}

with open(model_dir / "evaluation_metrics.pkl", "wb") as file:
    pickle.dump(metrics, file)


# 13. Save trained model
with open(model_dir / "model.pkl", "wb") as file:
    pickle.dump(model, file)


# 14. Save TF-IDF vectorizer
with open(model_dir / "vectorizer.pkl", "wb") as file:
    pickle.dump(vectorizer, file)


# 15. Save Confusion Matrix plots
fig, ax = plt.subplots(figsize=(6, 5))
display = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
display.plot(values_format="d", cmap="Blues", ax=ax)
plt.title("AI Fake News Detection - Confusion Matrix")
plt.tight_layout()
plt.savefig(static_dir / "confusion_matrix.png", dpi=300, bbox_inches="tight")
plt.savefig(model_dir / "confusion_matrix.png", dpi=300, bbox_inches="tight")
plt.close(fig)

print("\n" + "=" * 50)
print("MODEL, VECTORIZER, METRICS AND PLOTS SAVED!")
print("=" * 50)
print(f"Model file      : {model_dir / 'model.pkl'}")
print(f"Vectorizer file : {model_dir / 'vectorizer.pkl'}")
print(f"Accuracy file   : {model_dir / 'accuracy.txt'}")
print(f"Metrics file    : {model_dir / 'evaluation_metrics.pkl'}")
print(f"Confusion Matrix: {static_dir / 'confusion_matrix.png'}")

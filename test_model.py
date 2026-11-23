import pickle
from pathlib import Path


def main():
    model_dir = Path(__file__).resolve().parent / "model"
    with (model_dir / "model.pkl").open("rb") as file:
        model = pickle.load(file)
    with (model_dir / "vectorizer.pkl").open("rb") as file:
        vectorizer = pickle.load(file)

    news = input("Enter news article: ").strip()
    if not news:
        print("Please enter some article text.")
        return

    news_tfidf = vectorizer.transform([news])
    prediction = model.predict(news_tfidf)[0]
    probability = model.predict_proba(news_tfidf)[0]
    print("\nPrediction:", prediction)
    print("Confidence:", round(float(max(probability)) * 100, 2), "%")


if __name__ == "__main__":
    main()

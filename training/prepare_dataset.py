import pandas as pd

# Load fake news
fake = pd.read_csv("dataset/Fake.csv")

# Load real news
true = pd.read_csv("dataset/True.csv")

# Add labels
fake["label"] = "FAKE"
true["label"] = "REAL"

# Combine both datasets
news = pd.concat([fake, true], ignore_index=True)

# Keep required columns
news = news[["title", "text", "subject", "date", "label"]]

# Shuffle the dataset
news = news.sample(frac=1, random_state=42).reset_index(drop=True)

# Save the combined dataset
news.to_csv("dataset/news.csv", index=False)

print("Dataset created successfully!")
print("Total rows:", len(news))
print(news.head())
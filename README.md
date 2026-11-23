# 📰 AI-Based Fake News Detection System

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Flask](https://img.shields.io/badge/Flask-Web_Framework-black)
![Machine Learning](https://img.shields.io/badge/Machine-Learning-orange)
![MongoDB](https://img.shields.io/badge/Database-MongoDB-green)

An intelligent **AI-Based Fake News Detection System** developed using Machine Learning, Natural Language Processing, Python, Flask, and MongoDB. The application analyzes news content and predicts whether the given information is REAL or FAKE.

---

## 🚀 About The Project

Fake news has become a major problem in the digital world. This project aims to identify potentially misleading news articles using Machine Learning techniques.

Users can enter news content or provide a news article URL. The system processes the information and generates a prediction along with a confidence score.

## ✨ Features

- Fake and Real News Classification
- Machine Learning-based Prediction
- Natural Language Processing
- News URL Detection
- Prediction Confidence Score
- MongoDB Database Integration
- Prediction History
- User Authentication
- Admin Dashboard
- Responsive Web Interface

## 🛠️ Technologies Used

| Technology    | Purpose              |
| ------------- | -------------------- |
| Python        | Core Programming     |
| Flask         | Backend Framework    |
| Scikit-learn  | Machine Learning     |
| Pandas        | Data Processing      |
| NumPy         | Numerical Operations |
| BeautifulSoup | Web Scraping         |
| MongoDB       | Database             |
| HTML5         | Frontend             |
| CSS3          | Styling              |
| JavaScript    | Interactivity        |

## 🧠 Machine Learning Model

The system uses a trained Machine Learning classification model to distinguish between real and fake news.

Dataset attributes include:

- Title
- Text
- Subject
- Date

**Reported Model Accuracy: 98.56%**

_Accuracy is based on the project's test split. Results may vary on new, unseen news._

## 📂 Project Structure

```text
AI-BASED-FAKE-NEWS-DETECTION-SYSTEM/
│
├── app.py
├── dataset/
├── model/
│   ├── model.pkl
│   ├── vectorizer.pkl
│   └── accuracy.txt
│
├── static/
├── templates/
├── training/
│   ├── prepare_dataset.py
│   └── train.py
│
├── tests/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## ⚙️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Rudranshtomar/AI-BASED-FAKE-NEWS-DETECTION-SYSTEM.git
```

### 2. Navigate to Project Directory

```bash
cd AI-BASED-FAKE-NEWS-DETECTION-SYSTEM
```

### 3. Create Virtual Environment

```bash
python -m venv venv
```

### 4. Activate Virtual Environment

Windows:

```bash
venv\Scripts\activate
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Configure Environment Variables

Create a `.env` file using `.env.example`.

Add your MongoDB connection string and other required configuration values.

Never upload your `.env` file to GitHub.

### 7. Run Application

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000
```

## 📊 Model Evaluation

The model should be evaluated using:

- Accuracy
- Precision
- Recall
- F1-Score
- Confusion Matrix

These metrics help evaluate the classification performance beyond accuracy alone.

## 🔮 Future Improvements

- Improve model generalization.
- Integrate more diverse news datasets.
- Improve prediction explainability.
- Deploy the application online.
- Enhance the user interface.
- Add more advanced NLP techniques.

## 👨‍💻 Developer

**Rudransh Tomar**

B.Tech Computer Science and Engineering Student

Pranveer Singh Institute of Technology (PSIT), Kanpur

GitHub: [@Rudranshtomar](https://github.com/Rudranshtomar)

LinkedIn: [Rudransh Tomar](https://www.linkedin.com/in/rudransh-tomar-51a452392/)

---

⭐ If you find this project useful, consider giving it a star!

import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# -------------------------------
# CONFIG
# -------------------------------
TRAINING_FILE = "transactions_training.csv"
MODEL_OUTPUT = "category_model.pkl"
VECTORIZER_OUTPUT = "tfidf_vectorizer.pkl"

# -------------------------------
# LOAD AND PREPARE DATA
# -------------------------------
df = pd.read_csv(TRAINING_FILE)

# Fill empty fields
df["description"] = df["description"].astype(str).fillna("")
df["merchant"] = df["merchant"].astype(str).fillna("")
df["amount"] = df["amount"].astype(str).fillna("")

# Combine description + merchant + amount
df["text"] = (
    df["description"] + " " +
    df["merchant"] + " " +
    df["amount"]
)

# Features + labels
X = df["text"]
y = df["category"]

# -------------------------------
# TF-IDF VECTORIZER (IMPROVED)
# -------------------------------
vectorizer = TfidfVectorizer(
    stop_words="english",
    ngram_range=(1, 3),    # include trigrams → more context
    min_df=1,              # keep rare words (small categories need this)
    max_features=5000      # richer vocabulary
)

X_vectors = vectorizer.fit_transform(X)

# -------------------------------
# SPLIT TRAIN & TEST
# -------------------------------
# -------------------------------
# SPLIT TRAIN & TEST (NO STRATIFY)
# -------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X_vectors, y, test_size=0.2, random_state=42
)


# -------------------------------
# LOGISTIC REGRESSION with CLASS WEIGHT BALANCING
# -------------------------------
model = LogisticRegression(
    class_weight="balanced",   # boosts small categories
    max_iter=3000,             # allow full convergence
    n_jobs=-1,
    verbose=1
)

model.fit(X_train, y_train)

# -------------------------------
# EVALUATE MODEL
# -------------------------------
y_pred = model.predict(X_test)
print("\n-------------------------")
print("IMPROVED MODEL ACCURACY REPORT")
print("-------------------------")
print(classification_report(y_test, y_pred))

# -------------------------------
# SAVE MODEL + VECTORIZER
# -------------------------------
with open(MODEL_OUTPUT, "wb") as f:
    pickle.dump(model, f)

with open(VECTORIZER_OUTPUT, "wb") as f:
    pickle.dump(vectorizer, f)

print("\n✔ Improved model saved as:", MODEL_OUTPUT)
print("✔ Updated vectorizer saved as:", VECTORIZER_OUTPUT)

from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
import joblib

X, y = make_classification(n_samples=50, n_features=2, n_informative=2, n_redundant=0, random_state=42)

model = LogisticRegression()
model.fit(X, y)

joblib.dump(model, "model.joblib")

print("Model trained and saved to 'model.joblib'")
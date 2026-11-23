import sys
from pathlib import Path
import numpy as np
import pickle
import matplotlib
# Use non-interactive Agg backend by default so saving works headless
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay

BASE_DIR = Path(__file__).resolve().parent

# Load saved evaluation metrics
metrics_path = BASE_DIR / "model" / "evaluation_metrics.pkl"
with open(metrics_path, "rb") as file:
    metrics = pickle.load(file)

# Get confusion matrix and class labels
cm = np.array(metrics["confusion_matrix"])
labels = metrics["class_labels"]

# Create confusion matrix graph
fig, ax = plt.subplots(figsize=(6, 5))
display = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=labels
)

display.plot(values_format="d", cmap="Blues", ax=ax)
plt.title("AI Fake News Detection - Confusion Matrix")
plt.tight_layout()

# Save graph to both static/ (for web UI) and model/ (for records)
static_out = BASE_DIR / "static" / "confusion_matrix.png"
model_out = BASE_DIR / "model" / "confusion_matrix.png"

plt.savefig(static_out, dpi=300, bbox_inches="tight")
plt.savefig(model_out, dpi=300, bbox_inches="tight")
plt.close(fig)

print("Confusion Matrix graphs saved successfully!")
print(f"Web Static: {static_out}")
print(f"Model Dir : {model_out}")

if "--show" in sys.argv:
    # If explicitly requested with --show, switch backend or show
    import matplotlib.pyplot as interactive_plt
    interactive_plt.switch_backend("TkAgg")
    display.plot(values_format="d", cmap="Blues")
    interactive_plt.show()

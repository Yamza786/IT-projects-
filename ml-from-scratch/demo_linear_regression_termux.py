#!/usr/bin/env python3
import numpy as np

from ml.linear_regression import LinearRegressionGD


def make_linear_data(n=100, noise=1.0, seed=0):
    rng = np.random.RandomState(seed)
    X = rng.randn(n, 1) * 5
    y = 2.5 * X[:, 0] + 1.0 + rng.randn(n) * noise
    return X, y


def main():
    X, y = make_linear_data(n=100, noise=2.0)
    model = LinearRegressionGD(lr=0.01, epochs=2000)
    model.fit(X, y)
    print("Learned weight(s):", model.w)
    print("Learned bias:", model.b)

    # Optional: save plot to file (Agg backend used automatically).
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        y_pred = model.predict(X)
        order = np.argsort(X[:, 0])
        plt.scatter(X[:, 0], y, label="data")
        plt.plot(X[order, 0], y_pred[order], color="red", label="pred")
        plt.legend()
        out = "ml-from-scratch/lr_demo.png"
        plt.savefig(out, dpi=150)
        print(f"Plot saved to {out}")
    except Exception as e:
        print("Plot skipped (matplotlib not installed or failed):", e)


if __name__ == "__main__":
    main()

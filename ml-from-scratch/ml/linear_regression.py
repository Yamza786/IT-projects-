import numpy as np

class LinearRegressionGD:
    """Simple linear regression using batch gradient descent"""
    def __init__(self, lr=0.01, epochs=1000):
        self.lr = lr
        self.epochs = epochs
        self.w = None
        self.b = None

    def fit(self, X, y):
        X = np.array(X)
        y = np.array(y)
        n_samples, n_features = X.shape
        self.w = np.zeros(n_features)
        self.b = 0.0
        for _ in range(self.epochs):
            y_pred = X.dot(self.w) + self.b
            dw = (1/n_samples) * X.T.dot(y_pred - y)
            db = (1/n_samples) * np.sum(y_pred - y)
            self.w -= self.lr * dw
            self.b -= self.lr * db

    def predict(self, X):
        X = np.array(X)
        return X.dot(self.w) + self.b

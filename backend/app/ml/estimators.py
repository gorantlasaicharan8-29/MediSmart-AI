"""
Reusable ML Estimators, Preprocessors, and Pipeline Wrappers for MediSmart.
"""
from typing import Any
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin


class NonNegativeRegressor(BaseEstimator, RegressorMixin):
    """
    Wrapper regressor that enforces non-negative predictions.
    Waiting time cannot physically be negative (>= 0.0 minutes).
    """

    def __init__(self, regressor: Any = None):
        self.regressor = regressor

    def fit(self, X: Any, y: Any) -> "NonNegativeRegressor":
        if self.regressor is None:
            raise ValueError("An underlying regressor must be provided.")
        self.regressor_ = self.regressor.fit(X, y)
        if hasattr(self.regressor_, "feature_names_in_"):
            self.feature_names_in_ = self.regressor_.feature_names_in_
        return self

    def predict(self, X: Any) -> np.ndarray:
        raw_preds = self.regressor_.predict(X)
        return np.clip(raw_preds, 0.0, None)


class MeanBaselineRegressor(BaseEstimator, RegressorMixin):
    """Simple baseline predicting the training sample mean."""

    def __init__(self):
        self.mean_ = 0.0

    def fit(self, X: Any, y: Any) -> "MeanBaselineRegressor":
        self.mean_ = float(np.mean(y))
        return self

    def predict(self, X: Any) -> np.ndarray:
        n_samples = len(X) if hasattr(X, "__len__") else X.shape[0]
        return np.full(n_samples, self.mean_, dtype=float)


class ThresholdClassifier(BaseEstimator, ClassifierMixin):
    """
    Classifier wrapper that enforces a decision threshold calibrated on validation data.
    Provides predict_proba() and predict() according to the specified threshold.
    """

    def __init__(self, classifier: Any = None, threshold: float = 0.5):
        self.classifier = classifier
        self.threshold = threshold

    def fit(self, X: Any, y: Any) -> "ThresholdClassifier":
        if self.classifier is None:
            raise ValueError("An underlying classifier must be provided.")
        self.classifier_ = self.classifier.fit(X, y)
        self.classes_ = getattr(self.classifier_, "classes_", np.array([0, 1]))
        if hasattr(self.classifier_, "feature_names_in_"):
            self.feature_names_in_ = self.classifier_.feature_names_in_
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        return self.classifier_.predict_proba(X)

    def predict(self, X: Any) -> np.ndarray:
        probs = self.predict_proba(X)
        pos_probs = probs[:, 1] if probs.ndim == 2 else probs
        return (pos_probs >= self.threshold).astype(int)

# Defines an OnlineModel wrapper containing a HashingVectorizer and an SGDClassifier for partial_fit.
# Provides functions to compute feature matrices and score candidates.

from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from scipy import sparse
import numpy as np

class OnlineModel:
    def __init__(self):
        self.vectorizer = HashingVectorizer(n_features=2 ** 18, alternate_sign=False, norm=None)
        self.model = SGDClassifier(loss='log_loss', penalty='l2', max_iter=1, warm_start=True)
        # initialize model classes
        dummy = self.vectorizer.transform(["init"])
        dummy = sparse.hstack([dummy, sparse.csr_matrix([[0.0]])])
        self.model.partial_fit(dummy, np.array([0]), classes=np.array([0, 1]))

    def compute_feature_matrix(self, query: str, candidates: list, store):
        texts = [f"{query} {cand}" for cand in candidates]
        X_text = self.vectorizer.transform(texts)
        pops = []
        for cand in candidates:
            score = store.get_popularity(cand) or 0.0
            pops.append([np.log1p(score)])
        pops_sparse = sparse.csr_matrix(np.array(pops, dtype=np.float32))
        X = sparse.hstack([X_text, pops_sparse], format='csr')
        return X

    def score_candidates(self, query: str, candidates: list, store):
        if not candidates:
            return []
        X = self.compute_feature_matrix(query, candidates, store)
        try:
            scores = self.model.decision_function(X)
        except Exception:
            scores = np.zeros(len(candidates))
        pairs = list(zip(candidates, scores))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs

    def partial_fit(self, X, y):
        self.model.partial_fit(X, y, classes=np.array([0, 1]))

    def save(self, path):
        # lightweight saving using joblib can be added if desired
        pass
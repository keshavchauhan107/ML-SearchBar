# Simple in-memory store that keeps a popularity counter and a sorted list of queries for prefix lookup.
# This is NOT persistent and intended only for dev/testing.

from bisect import bisect_left, bisect_right, insort
from collections import Counter

class InMemoryStore:
    def __init__(self):
        self.pop = Counter()           # query -> score
        self.sorted_queries = []       # sorted unique queries for lexicographic prefix search

    def add_query(self, query: str, increment: int = 1):
        # normalize minimally
        q = query.strip().lower()
        if q not in self.pop:
            # insert into sorted list
            insort(self.sorted_queries, q)
        if increment:
            self.pop[q] += increment

    def get_top_n(self, limit=10):
        return [q for q, _ in self.pop.most_common(limit)]

    def get_prefix_candidates(self, prefix: str, limit=50):
        if not prefix:
            return self.get_top_n(limit)
        p = prefix.strip().lower()
        # lexicographic range via bisect
        lo = bisect_left(self.sorted_queries, p)
        hi = bisect_right(self.sorted_queries, p + chr(0xff))
        results = self.sorted_queries[lo:hi]
        # sort results by popularity descending while keeping a deterministic order
        results.sort(key=lambda x: (-self.pop.get(x, 0), x))
        return results[:limit]

    def get_popularity(self, query: str):
        return float(self.pop.get(query.strip().lower(), 0.0))
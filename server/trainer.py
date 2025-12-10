# Background trainer using an in-memory deque as an event queue.
# Provides enqueue_event and start_trainer(store, model).

import threading
import time
from collections import deque
from scipy import sparse
import numpy as np

EVENT_QUEUE = deque()
_stop = False

def enqueue_event(ev: dict):
    EVENT_QUEUE.append(ev)

def start_trainer(store, model, batch_size=256, save_every=60):
    def _loop():
        nonlocal store, model
        last_saved = time.time()
        batch = []
        print('Trainer started (in-memory)')
        while not _stop:
            try:
                # gather events up to batch_size or wait briefly
                while EVENT_QUEUE and len(batch) < batch_size:
                    batch.append(EVENT_QUEUE.popleft())
                if batch:
                    X_texts = []
                    labels = []
                    for ev in batch:
                        if ev.get('type') == 'impression':
                            q = ev.get('query', '')
                            cand_list = ev.get('candidates', [])
                            clicked = ev.get('clicked')
                            for cand in cand_list:
                                X_texts.append(f"{q} {cand}")
                                labels.append(1 if clicked and cand == clicked else 0)
                        elif ev.get('type') == 'click':
                            q = ev.get('query', '')
                            cand = ev.get('candidate')
                            X_texts.append(f"{q} {cand}")
                            labels.append(1)
                    if X_texts:
                        X_text = model.vectorizer.transform(X_texts)
                        pops = []
                        for txt in X_texts:
                            cand = txt.split(' ', 1)[1] if ' ' in txt else txt
                            score = store.get_popularity(cand) or 0.0
                            pops.append([np.log1p(score)])
                        pops_arr = np.array(pops, dtype=np.float32)
                        pops_sparse = sparse.csr_matrix(pops_arr)
                        X = sparse.hstack([X_text, pops_sparse], format='csr')
                        y = np.array(labels)
                        try:
                            model.partial_fit(X, y)
                        except Exception as e:
                            print('partial_fit error:', e)
                    batch = []
                else:
                    time.sleep(0.5)
                # simple periodic save hook (no-op)
                if time.time() - last_saved >= save_every:
                    last_saved = time.time()
            except Exception as e:
                print('Trainer loop exception:', e)
        print('Trainer stopped')

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
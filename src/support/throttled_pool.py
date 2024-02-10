import time
from concurrent.futures import ThreadPoolExecutor
import threading


class ThrottledThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers=None, requests=100, interval=1):
        super().__init__(max_workers)
        self.rate = requests / interval
        self.capacity = requests
        self.tokens = self.capacity
        self.last_refill_time = time.monotonic()
        self._lock = threading.Lock()
        self._wait_event = threading.Event()

    def _try_refill_tokens(self):
        now = time.monotonic()
        with self._lock:
            elapsed = now - self.last_refill_time
            refill_amount = elapsed * self.rate
            if refill_amount > 0:
                self.tokens = min(self.capacity, self.tokens + refill_amount)
                self.last_refill_time = now
                return True
        return False

    def submit(self, fn, *args, **kwargs):
        while True:
            with self._lock:
                if self.tokens > 0:
                    self.tokens -= 1
                    break  # Token is available, proceed to submit the task
            # Attempt to refill tokens without holding the lock the entire time
            if not self._try_refill_tokens():
                self._wait_event.wait(0.1)  # Wait briefly and then try again
                self._wait_event.clear()  # Clear the event to reset its state
            else:
                self._wait_event.set()  # Signal that tokens may have been refilled

        return super().submit(fn, *args, **kwargs)

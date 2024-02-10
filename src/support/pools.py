import time
from concurrent.futures import ThreadPoolExecutor

import asyncio


class Pools:
    def __init__(
            self,
            qase_pool: ThreadPoolExecutor,
            tr_pool: ThreadPoolExecutor,
    ):
        self.qase_pool = qase_pool
        self.tr_pool = tr_pool

    def tr(self, fn, *args, **kwargs):
        return asyncio.wrap_future(self.tr_pool.submit(fn, *args, **kwargs))

    def qs(self, fn, *args, **kwargs):
        return asyncio.wrap_future(self.qase_pool.submit(fn, *args, **kwargs))

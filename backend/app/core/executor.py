import atexit
from concurrent.futures import ThreadPoolExecutor

# Central bounded ThreadPoolExecutor for background non-blocking I/O tasks
# (e.g. Webhook dispatching, Active Learning remote forwarding, Background model syncing)
io_executor = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="HandClapIO"
)

def shutdown_executor():
    try:
        io_executor.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass

atexit.register(shutdown_executor)

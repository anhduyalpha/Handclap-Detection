import time
import random
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger("handclap.network")

def post_with_retry(
    url: str,
    json_data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    base_delay: float = 0.5,
    timeout: float = 3.5,
    auth_token: Optional[str] = None
) -> bool:
    """
    Gửi HTTP POST request với chiến lược Exponential Backoff kèm Jitter.
    Bảo đảm khả năng phục hồi khi mạng LAN / Wi-Fi chập chờn hoặc node đích đang khởi động.
    """
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if auth_token:
        req_headers["X-Studio-Token"] = auth_token

    for attempt in range(1, max_retries + 1):
        try:
            res = requests.post(url, json=json_data, headers=req_headers, timeout=timeout)
            if res.status_code in (200, 201, 204):
                logger.info(f"POST {url} succeeded on attempt {attempt}")
                return True
            logger.warning(f"POST {url} attempt {attempt} returned HTTP {res.status_code}")
        except requests.RequestException as err:
            logger.warning(f"POST {url} attempt {attempt} failed: {err}")

        if attempt < max_retries:
            # Full Jitter Exponential Backoff: delay = (base_delay * 2^(attempt-1)) + jitter
            sleep_sec = (base_delay * (2 ** (attempt - 1))) + random.uniform(0.05, 0.15)
            time.sleep(sleep_sec)

    logger.error(f"POST {url} failed permanently after {max_retries} attempts.")
    return False

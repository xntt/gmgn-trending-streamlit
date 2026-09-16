import random
import json
from typing import Optional, Dict, Any, List

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

import requests
from fake_useragent import UserAgent


class gmgn:
    """GMGN 非官方接口客户端（优先 curl_cffi，失败则用 requests）"""

    BASE_URL = "https://gmgn.ai/defi/quotation"

    def __init__(self, chain: str = "sol"):
        self.chain = chain
        try:
            self.ua = UserAgent()
        except Exception:
            self.ua = None

    def _headers(self) -> Dict[str, str]:
        if self.ua:
            try:
                user_agent = self.ua.random
            except Exception:
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        else:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

        return {
            "Host": "gmgn.ai",
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "referer": f"https://gmgn.ai/?chain={self.chain}",
            "user-agent": user_agent,
            "origin": "https://gmgn.ai",
        }

    def _get(self, url: str) -> Any:
        headers = self._headers()
        last_error = None

        # 1) 优先 curl_cffi（更易过 Cloudflare）
        if HAS_CURL_CFFI:
            for impersonate in ["chrome120", "chrome110", "safari17_0"]:
                try:
                    r = cffi_requests.get(
                        url,
                        headers=headers,
                        impersonate=impersonate,
                        timeout=25,
                    )
                    if r.status_code == 200:
                        return r.json()
                    last_error = f"curl_cffi status={r.status_code}"
                except Exception as e:
                    last_error = str(e)
                    continue

        # 2) 兜底 requests
        try:
            r = requests.get(url, headers=headers, timeout=25)
            if r.status_code == 200:
                return r.json()
            last_error = f"requests status={r.status_code}, body={r.text[:200]}"
        except Exception as e:
            last_error = str(e)

        raise RuntimeError(f"请求失败: {last_error}")

    def getTrendingTokens(self, timeframe: str = "1h") -> dict:
        """
        获取热门代币
        timeframe: 1m / 5m / 1h / 6h / 24h
        """
        valid = ["1m", "5m", "1h", "6h", "24h"]
        if timeframe not in valid:
            raise ValueError(f"无效 timeframe，可选: {valid}")

        if timeframe == "1m":
            url = (
                f"{self.BASE_URL}/v1/rank/{self.chain}/swaps/{timeframe}"
                f"?orderby=swaps&direction=desc&limit=50"
            )
        else:
            url = (
                f"{self.BASE_URL}/v1/rank/{self.chain}/swaps/{timeframe}"
                f"?orderby=swaps&direction=desc"
            )

        data = self._get(url)
        # 兼容不同返回结构
        if isinstance(data, dict):
            if "data" in data:
                return data["data"]
            return data
        return data

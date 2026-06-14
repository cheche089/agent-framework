"""Web search and HTTP client module — 增强版（多搜索引擎 + 天气 API）

搜索引擎（自动回退）：
1. wttr.in — 免费天气 API，无需 Key
2. DuckDuckGo HTML — 无需 API Key 的网页搜索
3. Bing HTML — 备用搜索引擎
"""

from __future__ import annotations
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse

logger = logging.getLogger(__name__)


# ── Security: domain allow/block list ───────────────────────────

DEFAULT_ALLOWED_DOMAINS: List[str] = []
DEFAULT_BLOCKED_DOMAINS: List[str] = [
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.",
]
MAX_RESPONSE_SIZE: int = 5 * 1024 * 1024  # 5MB
DEFAULT_TIMEOUT: int = 30
MAX_RESULTS: int = 10


class WebClient:
    """Web client with security restrictions, rate limiting, and error handling."""

    def __init__(
        self,
        allowed_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: Optional[str] = None,
    ):
        self._allowed = allowed_domains or DEFAULT_ALLOWED_DOMAINS
        self._blocked = blocked_domains or DEFAULT_BLOCKED_DOMAINS
        self._timeout = timeout
        self._user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self._rate_limit: Dict[str, float] = {}
        self._rate_limit_interval: float = 0.5

    def _check_url(self, url: str) -> None:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        for blocked in self._blocked:
            if hostname.startswith(blocked) or hostname == blocked:
                raise PermissionError(f"Domain '{hostname}' is blocked")
        if self._allowed:
            allowed = any(
                hostname.endswith(allowed) or hostname == allowed
                for allowed in self._allowed
            )
            if not allowed:
                raise PermissionError(f"Domain '{hostname}' is not in allowed list")

    def _check_rate_limit(self, url: str) -> None:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        last = self._rate_limit.get(hostname, 0)
        elapsed = time.time() - last
        if elapsed < self._rate_limit_interval:
            time.sleep(self._rate_limit_interval - elapsed)
        self._rate_limit[hostname] = time.time()

    async def request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Any = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._check_url(url)
        self._check_rate_limit(url)

        import httpx

        req_headers = {"User-Agent": self._user_agent}
        if headers:
            req_headers.update(headers)

        try:
            # ── Auto-convert GitHub URLs to raw content URLs ──
            actual_url = self._convert_github_url(url)

            async with httpx.AsyncClient(
                timeout=timeout or self._timeout,
                follow_redirects=True,
                verify=False,
            ) as client:
                if method.upper() == "GET":
                    resp = await client.get(actual_url, headers=req_headers)
                elif method.upper() == "POST":
                    resp = await client.post(actual_url, headers=req_headers, json=data)
                else:
                    resp = await client.request(method, actual_url, headers=req_headers, json=data)

                content = resp.text[:MAX_RESPONSE_SIZE]
                result = {
                    "success": resp.status_code < 400,
                    "status_code": resp.status_code,
                    "content": content,
                    "content_type": resp.headers.get("content-type", ""),
                    "url": str(resp.url),
                    "size": len(content),
                    "original_url": url,
                    "actual_url": actual_url,
                }

                # ── If it's a GitHub raw markdown, add helpful metadata ──
                if "raw.githubusercontent.com" in actual_url:
                    result["_from_github"] = True

                return result
        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    # ── GitHub URL 自动转 raw 链接 ────────────────────────────

    @staticmethod
    def _convert_github_url(url: str) -> str:
        """自动将 GitHub 页面 URL 转换为 raw.githubusercontent.com 原始文件链接。

        支持的格式：
        - https://github.com/user/repo → raw/.../main/README.md
        - https://github.com/user/repo/blob/main/README.md → raw/.../main/README.md
        - https://github.com/user/repo/tree/main/docs → raw/.../main/docs
        - https://raw.githubusercontent.com/... → 不变
        """
        # 已经是 raw 链接
        if "raw.githubusercontent.com" in url:
            return url

        # 不是 github.com 的不处理
        if "github.com" not in url:
            return url

        # 解析路径
        parsed = urlparse(url)
        path = parsed.path.strip("/")

        parts = path.split("/")
        if len(parts) < 2:
            return url

        user = parts[0]
        repo = parts[1]
        branch = "main"

        # 确定剩余路径
        remaining = ""
        if len(parts) >= 3:
            # github.com/user/repo
            # github.com/user/repo/blob/branch/path
            # github.com/user/repo/tree/branch/path
            rest = parts[2:]
            if rest[0] in ("blob", "tree"):
                # blob/main/README.md or tree/main/docs
                if len(rest) >= 2:
                    branch = rest[1]
                    remaining = "/".join(rest[2:]) if len(rest) > 2 else ""
            else:
                # github.com/user/repo/some/path — 假定路径
                remaining = "/".join(rest)

        # 如果没有特定文件路径，尝试获取 README.md
        if not remaining:
            return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/README.md"

        return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{remaining}"


_default_client = WebClient()


async def http_request(
    url: str, method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Any = None, timeout: Optional[int] = None,
) -> Dict[str, Any]:
    return await _default_client.request(url, method, headers, data, timeout)


async def fetch_page(url: str) -> str:
    result = await _default_client.request(url)
    if result.get("success"):
        return result["content"]
    raise RuntimeError(f"Failed to fetch {url}: {result.get('error', 'unknown')}")


# ═══════════════════════════════════════════════════════════════
# 天气查询（wttr.in — 免费，无需 API Key）
# ═══════════════════════════════════════════════════════════════

async def weather_query(location: str) -> Dict[str, Any]:
    """查询指定地点的天气 — 使用 wttr.in 免费天气服务。

    Args:
        location: 城市名或坐标（如 "衡水"、"Beijing"、"39.9,116.4"）

    Returns:
        包含天气信息的字典
    """
    from urllib.parse import quote

    encoded = quote(location)

    # 方式1：获取 JSON 格式（结构化数据）
    json_url = f"https://wttr.in/{encoded}?format=j1"
    resp = await _default_client.request(json_url, timeout=15)

    if resp.get("success"):
        try:
            data = json.loads(resp["content"])
            return _parse_wttr_json(data, location)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"wttr.in JSON parse error: {e}")

    # 方式2：获取文本格式（更可靠）
    text_url = f"https://wttr.in/{encoded}?format=%l:+%c+%t,+%w,+%h+湿度,+%p+降水概率"
    resp2 = await _default_client.request(text_url, timeout=15)
    if resp2.get("success"):
        return {
            "success": True,
            "location": location,
            "summary": resp2["content"].strip(),
            "source": "wttr.in_text",
        }

    # 方式3：尝试中文版
    cn_url = f"https://wttr.in/{encoded}?lang=zh&format=%l:+%c+%t,+%w,+%h+湿度,+%p+降水概率"
    resp3 = await _default_client.request(cn_url, timeout=15)
    if resp3.get("success"):
        return {
            "success": True,
            "location": location,
            "summary": resp3["content"].strip(),
            "source": "wttr.in_cn",
        }

    return {"success": False, "location": location, "error": "无法获取天气信息"}


def _parse_wttr_json(data: dict, location: str) -> Dict[str, Any]:
    """解析 wttr.in 的 JSON 返回为结构化天气数据。"""
    cc = data.get("current_condition", [{}])[0]
    weather = data.get("weather", [{}])

    result = {
        "success": True,
        "location": data.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", location),
        "country": data.get("nearest_area", [{}])[0].get("country", [{}])[0].get("value", ""),
        "source": "wttr.in",
        "current": {
            "temp_c": cc.get("temp_C", ""),
            "temp_f": cc.get("temp_F", ""),
            "feels_like_c": cc.get("FeelsLikeC", ""),
            "humidity": cc.get("humidity", ""),
            "weather_desc": cc.get("weatherDesc", [{}])[0].get("value", ""),
            "wind_speed_kmh": cc.get("windspeedKmph", ""),
            "wind_dir": cc.get("winddir16Point", ""),
            "pressure": cc.get("pressure", ""),
            "visibility": cc.get("visibility", ""),
            "cloud_cover": cc.get("cloudcover", ""),
            "uv_index": cc.get("uvIndex", ""),
        },
        "forecast": [],
    }

    for day in weather[:5]:
        date = day.get("date", "")
        astronomy = day.get("astronomy", [{}])[0]
        hourly = day.get("hourly", [])

        result["forecast"].append({
            "date": date,
            "max_c": day.get("maxtempC", ""),
            "min_c": day.get("mintempC", ""),
            "sunrise": astronomy.get("sunrise", ""),
            "sunset": astronomy.get("sunset", ""),
            "hourly": [
                {
                    "time": h.get("time", ""),
                    "temp_c": h.get("tempC", ""),
                    "weather": h.get("weatherDesc", [{}])[0].get("value", ""),
                    "wind_speed": h.get("windspeedKmph", ""),
                    "humidity": h.get("humidity", ""),
                    "chance_of_rain": h.get("chanceofrain", ""),
                }
                for h in hourly[:8]
            ],
        })

    return result


def format_weather_display(w: Dict[str, Any]) -> str:
    """将天气数据格式化为用户友好的文本。"""
    if not w.get("success"):
        return f"❌ 无法获取 {w.get('location', '指定地点')} 的天气信息。"

    loc = w.get("location", "未知地点")
    cc = w.get("current", {})

    lines = [
        f"━━━ {loc} 天气 ━━━",
        f"🌡️  当前温度：{cc.get('temp_c', '?')}°C",
    ]

    if cc.get("feels_like_c"):
        lines.append(f"🤗 体感温度：{cc['feels_like_c']}°C")
    if cc.get("weather_desc"):
        lines.append(f"🌤️  天气状况：{cc['weather_desc']}")
    if cc.get("humidity"):
        lines.append(f"💧 湿度：{cc['humidity']}%")
    if cc.get("wind_speed_kmh"):
        lines.append(f"💨 风速：{cc['wind_speed_kmh']} km/h ({cc.get('wind_dir', '')})")
    if cc.get("uv_index"):
        lines.append(f"☀️  UV 指数：{cc['uv_index']}")
    if cc.get("visibility"):
        lines.append(f"👁️  能见度：{cc['visibility']} km")
    if cc.get("pressure"):
        lines.append(f"🔵 气压：{cc['pressure']} hPa")

    # 预报
    forecast = w.get("forecast", [])
    if forecast:
        lines.append(f"\n━━━ 未来预报 ━━━")
        for day in forecast[:5]:
            date_str = day.get("date", "?")
            max_c = day.get("max_c", "?")
            min_c = day.get("min_c", "?")
            sunrise = day.get("sunrise", "")
            sunset = day.get("sunset", "")
            lines.append(f"\n📅 {date_str}: {min_c}°C ~ {max_c}°C")
            if sunrise:
                lines.append(f"   🌅 {sunrise}  🌇 {sunset}")

            # 逐时预报（取有代表性的）
            hourly = day.get("hourly", [])
            if hourly:
                # 显示白天几个时段
                hour_samples = [h for h in hourly if h.get("time", "0") in ["600", "900", "1200", "1500", "1800", "2100"]]
                for h in hour_samples:
                    t = h.get("time", "")
                    t_show = f"{t[:2]}:00" if len(t) >= 2 else t
                    temp = h.get("temp_c", "?")
                    desc = h.get("weather", "")
                    rain = h.get("chance_of_rain", "")
                    rain_str = f" ☔{rain}%" if rain and rain != "0" else ""
                    lines.append(f"   {t_show}  {temp}°C  {desc}{rain_str}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 网页搜索引擎（多后端自动回退）
# ═══════════════════════════════════════════════════════════════

async def search_duckduckgo(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """使用 DuckDuckGo HTML 搜索。"""
    results: List[Dict[str, str]] = []
    try:
        ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        result = await _default_client.request(ddg_url)
        if not result.get("success"):
            return results

        html = result["content"]

        # 多个 HTML 解析模式
        patterns = [
            # 标准模式
            r'<a rel="nofollow" class="result__a" href="(.*?)">.*?</a>.*?<a class="result__snippet" href=".*?">(.*?)</a>',
            # 备选模式
            r'class="result__title"[^>]*>.*?<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            # 通用链接提取
            r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</a>',
        ]

        for pattern in patterns:
            blocks = re.findall(pattern, html, re.DOTALL)
            seen = set()
            for match in blocks:
                if isinstance(match, tuple):
                    href, title = match[0], match[1]
                else:
                    href, title = match, ""
                if href not in seen and "duckduckgo.com" not in href:
                    seen.add(href)
                    snippet = ""
                    # 尝试提取摘要
                    snip_match = re.search(
                        rf'<a[^>]+href="{re.escape(href)}"[^>]*>.*?</a>.*?class="result__snippet"[^>]*>(.*?)</a>',
                        html, re.DOTALL,
                    )
                    if snip_match:
                        snippet = re.sub(r"<.*?>", "", snip_match.group(1)).strip()
                    results.append({
                        "title": re.sub(r"<.*?>", "", title).strip()[:80] or href[:80],
                        "url": href,
                        "snippet": snippet,
                    })
                    if len(results) >= num_results:
                        break
            if results:
                break

    except Exception as e:
        logger.warning(f"DuckDuckGo search error: {e}")

    return results


async def search_bing(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """使用 Bing HTML 搜索。"""
    results: List[Dict[str, str]] = []
    try:
        bing_url = f"https://www.bing.com/search?q={quote_plus(query)}"
        result = await _default_client.request(bing_url)
        if not result.get("success"):
            return results

        html = result["content"]
        # 提取搜索结果
        li_pattern = r'<li class="b_algo">.*?<h2>.*?<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>.*?</h2>.*?<p[^>]*>(.*?)</p>'
        for href, title, snippet in re.findall(li_pattern, html, re.DOTALL):
            results.append({
                "title": re.sub(r"<.*?>", "", title).strip()[:80],
                "url": href,
                "snippet": re.sub(r"<.*?>", "", snippet).strip()[:200],
            })
            if len(results) >= num_results:
                break

    except Exception as e:
        logger.warning(f"Bing search error: {e}")

    return results


# ── 主要搜索入口 ───────────────────────────────────────────────

async def web_search(
    query: str,
    num_results: int = 5,
    source: str = "auto",
) -> List[Dict[str, str]]:
    """搜索互联网，自动回退到可用引擎。

    Args:
        query: 搜索关键词
        num_results: 返回结果数（最多 10）
        source: 搜索引擎 - "auto" | "duckduckgo" | "bing"

    Returns:
        结果列表，每个含 title/url/snippet
    """
    num_results = min(num_results, MAX_RESULTS)

    # ── 工具函数：检查是否是天气查询 ──
    weather_keywords = ["天气", "weather", "气温", "温度", "°C", "°F",
                        "下雨", "下雪", "台风", "暴风", "降雨"]
    is_weather = any(kw in query.lower() for kw in weather_keywords)

    # ── 如果是天气查询，先用 wttr.in ──
    if is_weather:
        # 提取城市名
        city = query
        for prefix in ["天气", "weather", "今天", "明天", "后天", "一周", "气温", "温度"]:
            city = city.replace(prefix, "")
        # 清理
        import re as _re
        city = _re.sub(r"[？?，,。.！!]", "", city).strip()
        if not city:
            city = query  # fallback

        weather_data = await weather_query(city)
        if weather_data.get("success") and weather_data.get("source") == "wttr.in":
            formatted = format_weather_display(weather_data)
            # 作为搜索结果返回
            return [{
                "title": f"{weather_data.get('location', city)} 天气",
                "url": f"https://wttr.in/{quote_plus(city)}",
                "snippet": formatted,
                "_weather": True,
            }]
        elif weather_data.get("success"):
            return [{
                "title": f"{city} 天气",
                "url": "",
                "snippet": weather_data.get("summary", f"{city} 天气查询结果"),
                "_weather": True,
            }]

    # ── 普通网页搜索 ──
    # 引擎顺序（含回退）
    engines = []
    if source == "auto":
        engines = [
            ("duckduckgo", search_duckduckgo),
            ("bing", search_bing),
        ]
    elif source == "duckduckgo":
        engines = [("duckduckgo", search_duckduckgo)]
    elif source == "bing":
        engines = [("bing", search_bing)]

    all_results: List[Dict[str, str]] = []
    seen_urls: set = set()

    for engine_name, engine_fn in engines:
        try:
            engine_results = await engine_fn(query, num_results)
            for r in engine_results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    r["_engine"] = engine_name
                    all_results.append(r)
                    if len(all_results) >= num_results:
                        break
        except Exception as e:
            logger.warning(f"Search engine '{engine_name}' failed: {e}")
            continue

        if len(all_results) >= num_results:
            break

    return all_results[:num_results]

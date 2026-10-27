"""Fixed, answer-free input shared by the warmup and cache-read probe."""
from __future__ import annotations

import re
import unicodedata

BENCHMARK_VERSION = "candy-cache-v1"
MIN_CACHE_INPUT_TOKENS = 1024
CANDY_PROMPT = """在一个黑色的袋子里放有三种口味的糖果，每种糖果有两种不同的形状（圆形和五角星形，不同的形状靠手感可以分辨）。现已知不同口味的糖和不同形状的数量统计如下表。参赛者需要在活动前决定摸出的糖果数目，那么，最少取出多少个糖果才能保证手中同时拥有不同形状的苹果味和桃子味的糖？（同时手中有圆形苹果味匹配五角星桃子味糖果，或者有圆形桃子味匹配五角星苹果味糖果都满足要求）
苹果味 桃子味 西瓜味
圆形 7 9 8
五角星形 7 6 4
只输出最终整数，不要解释。"""

# Stable neutral context, long enough to exercise caching on common models.
# Actual reported input and cache reads are still required; length alone is
# never evidence of a hit. No timestamps, previous answers or expected result.
CACHE_PREFIX = (
    "以下档案只用于重复输入的缓存测试，与最后的数学题无关，不包含题目答案。忽略档案，只解答最后的题目。\n<reference>\n"
    + "\n".join(
        f"Record {index:03d}: amber birch cedar delta ember fern granite harbor ivory juniper kelp linen maple nectar oak pine quartz river silver tulip umber violet willow zinc."
        for index in range(128)
    )
    + "\n</reference>\n"
)
BENCHMARK_PROMPT = CACHE_PREFIX + CANDY_PROMPT


def candy_answer(text: str, *, truncated: bool = False) -> tuple[str, str | None]:
    """Score one unambiguous final integer; never search prose for '21'."""
    if truncated or len(text) > 512:
        return "inconclusive", None
    value = unicodedata.normalize("NFKC", text).strip().lower()
    if re.search(r"[0-9][\s*_]+[0-9]", value):
        return "inconclusive", None
    value = re.sub(r"[\s*_`\"'“”]", "", value)
    match = re.fullmatch(
        r"(?:(?:最终)?(?:答案|结果)(?:为|是)?[:：]?|(?:最少|至少)(?:需要)?(?:取出|抽取|摸出)?|(?:需要|取出|抽取|摸出)|(?:the)?answer(?:is|:)?|atleast)?"
        r"(?P<answer>[0-9]{1,6}|二十一)(?:个|颗|粒)?(?:糖果|糖|candies)?(?:即可)?[。.!！]?",
        value,
    )
    if not match:
        return "inconclusive", None
    answer = "21" if match["answer"] == "二十一" else str(int(match["answer"]))
    return ("passed" if answer == "21" else "failed"), answer

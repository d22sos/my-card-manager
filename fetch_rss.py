#!/usr/bin/env python3
"""
信用卡+酒店活动RSS抓取器 v3-final
= v2稳健修复（换行清理、HTML注入）+ v3港卡优先级逻辑合并版
"""

import json, re, sys, os
from datetime import datetime

try:
    import feedparser
    import requests
except ImportError:
    print("请先运行: pip install feedparser requests", file=sys.stderr)
    sys.exit(1)

FEEDS = [
    {"name": "X-Infinite 机酒卡",   "url": "https://www.xinfinite.net/c/airlinehotelcard/6.rss"},
    {"name": "什么值得买·信用卡",    "url": "https://www.smzdm.com/tag/%E4%BF%A1%E7%94%A8%E5%8D%A1/feed/"},
    {"name": "什么值得买·银行活动",  "url": "https://www.smzdm.com/tag/%E9%93%B6%E8%A1%8C/feed/"},
    {"name": "什么值得买·酒店",      "url": "https://www.smzdm.com/tag/%E9%85%92%E5%BA%97/feed/"},
    {"name": "飞客茶馆·信用卡",      "url": "https://www.feeyo.com/rss/creditcard.xml"},
    {"name": "飞客茶馆·酒店",        "url": "https://www.feeyo.com/rss/hotel.xml"},
    {"name": "我爱卡·资讯",          "url": "https://news.51credit.com/rss.xml"},
    {"name": "卡宝宝",               "url": "https://www.kababao.com/rss.xml"},
]

FILTER_KEYWORDS = [
    "报名","返现","立减","满减","折扣","优惠","积分","酒店",
    "锦江","如家","IHG","优悦","雅高","心悦界","Accor","ALL",
    "云闪付","美团","拼多多","淘宝","飞猪","通兑","日历房","里程",
    "汇丰","Pulse","中信国际","GBA","大湾区","港卡",
    "外卡","境外消费","境外返现","境外刷卡","HK版",
]

BANK_TAGS = {
    "汇丰": "汇丰银行", "Pulse": "汇丰Pulse",
    "中信国际": "中信国际", "GBA": "大湾区卡",
    "广发": "广发", "招商": "招行", "招行": "招行",
    "建行": "建行", "交行": "交行", "工行": "工行",
    "中信": "中信", "光大": "光大", "浦发": "浦发",
    "平安": "平安", "民生": "民生", "中行": "中行",
}

CHANNEL_TAGS = {
    "云闪付": "云闪付", "支付宝": "支付宝", "微信": "微信支付",
    "滴滴": "滴滴", "美团": "美团", "拼多多": "拼多多",
    "淘宝": "淘宝", "天猫": "淘宝", "飞猪": "飞猪",
    "锦江": "锦江汇", "如家": "如家", "华住": "华住",
    "IHG": "IHG优悦会", "优悦": "IHG优悦会", "洲际": "IHG优悦会",
    "雅高": "雅高ALL", "Accor": "雅高ALL", "心悦界": "雅高ALL",
    "万豪": "万豪", "Marriott": "万豪",
    "希尔顿": "希尔顿", "Hilton": "希尔顿",
    "亚朵": "亚朵",
}

HK_PRIORITY_KEYWORDS = [
    "汇丰", "Pulse", "中信国际", "GBA", "大湾区", "港卡",
    "外卡", "境外返现", "境外消费", "境外刷卡", "HK版",
    "港元", "港币", "HKD",
]

CHEAP_HOTEL_THRESHOLD = 150
RISKY_LOCATION_KEYWORDS = ["城中村", "郊区", "偏远", "工业区", "外环", "远郊"]
SAFE_AREA_KEYWORDS = [
    "福田", "南山", "深圳湾", "科技园",
    "香港", "九龙", "尖沙咀", "铜锣湾", "湾仔", "西九龙",
    "广州南", "天河", "珠江新城",
]


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"[\r\n\t]+", " ", text)
    return re.sub(r" {2,}", " ", text).strip()


def extract_price_hint(text: str):
    for pat in [r"(\d+)\s*元[/]?晚", r"仅需\s*(\d+)", r"低至\s*(\d+)", r"[¥]\s*(\d+)"]:
        for m in re.finditer(pat, text):
            v = int(m.group(1))
            if 50 <= v <= 2000:
                return v
    return None


def extract_tags(text: str) -> list:
    tags = []
    for kw, tag in {**BANK_TAGS, **CHANNEL_TAGS}.items():
        if kw in text and tag not in tags:
            tags.append(tag)
    return tags


def detect_priority(text: str) -> int:
    tl = text.lower()
    if any(kw.lower() in tl for kw in HK_PRIORITY_KEYWORDS):
        return 2
    return 0


def categorize(text: str) -> str:
    hotel_kw = ["酒店","锦江","如家","IHG","雅高","万豪","希尔顿","华住","亚朵","入住","房晚","日历房","通兑"]
    daily_kw = ["美团","拼多多","淘宝","天猫","滴滴","外卖","超市","加油","餐饮","飞猪","云闪付","返现","满减","立减","境外消费","境外返现"]
    for kw in hotel_kw:
        if kw in text:
            return "hotel"
    for kw in daily_kw:
        if kw in text:
            return "daily"
    return "card"


def build_warnings(text: str, price) -> list:
    warnings = []
    if price and price < CHEAP_HOTEL_THRESHOLD:
        warnings.append(f"低价{price}元 注意地点偏远或治安")
    for kw in RISKY_LOCATION_KEYWORDS:
        if kw in text:
            warnings.append(f"含[{kw}]地点 建议核查环境")
            break
    return warnings


def main():
    all_items = []
    for feed in FEEDS:
        try:
            resp = requests.get(feed["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            resp.encoding = resp.apparent_encoding
            d = feedparser.parse(resp.text)
            for entry in d.entries[:30]:
                title   = clean_text(entry.get("title", ""))[:120]
                summary = clean_text(entry.get("summary", entry.get("description", "")))[:300]
                text    = title + " " + summary
                if not any(kw in text for kw in FILTER_KEYWORDS):
                    continue
                pub   = entry.get("published_parsed") or entry.get("updated_parsed")
                price = extract_price_hint(text)
                all_items.append({
                    "title":    title,
                    "summary":  summary,
                    "link":     entry.get("link", ""),
                    "date":     datetime(*pub[:6]).strftime("%Y-%m-%d") if pub else "",
                    "source":   feed["name"],
                    "tags":     extract_tags(text),
                    "category": categorize(text),
                    "price":    price,
                    "warnings": build_warnings(text, price),
                    "safeArea": any(kw in text for kw in SAFE_AREA_KEYWORDS),
                    "priority": detect_priority(text),
                })
        except Exception as e:
            print(f"[警告] {feed['name']} 失败: {e}", file=sys.stderr)

    seen = set()
    unique = []
    for item in sorted(all_items, key=lambda x: x["date"], reverse=True):
        key = item["title"][:40]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    data = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "items": unique}

    with open("rss_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 注入 HTML（关键：json.dumps 自动转义所有特殊字符，包括换行）
    if os.path.exists("card-tracker.html"):
        with open("card-tracker.html", "r", encoding="utf-8") as f:
            html = f.read()
        payload = json.dumps(data, ensure_ascii=False)
        script  = f'<script id="rss-inject">window.RSS_DATA={payload};</script>'
        if '<script id="rss-inject">' in html:
            html = re.sub(r'<script id="rss-inject">.*?</script>', script, html, flags=re.DOTALL)
        else:
            html = html.replace("</body>", script + "\n</body>")
        with open("card-tracker.html", "w", encoding="utf-8") as f:
            f.write(html)

    hk_n = sum(1 for i in unique if i["priority"] == 2)
    print(f"完成：{len(unique)} 条（港卡/境外优先 {hk_n} 条），已注入 HTML")


if __name__ == "__main__":
    main()

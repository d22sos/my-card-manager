#!/usr/bin/env python3
"""
隐私支付管家 - RSS抓取器 V4 (突破信息茧房版)
新增：RSSHub定向关键词追踪港卡/返利信息
"""

import json, re, sys, os
from datetime import datetime

try:
    import feedparser
    import requests
except ImportError:
    print("请先运行: pip install feedparser requests", file=sys.stderr)
    sys.exit(1)

# 突破茧房：加入 RSSHub 对“什么值得买”的全局关键词定向监控
FEEDS = [
    {"name": "机酒卡资讯",     "url": "https://www.xinfinite.net/c/airlinehotelcard/6.rss"},
    {"name": "全网监控·港卡",   "url": "https://rsshub.app/smzdm/keyword/港卡"},
    {"name": "全网监控·汇丰",   "url": "https://rsshub.app/smzdm/keyword/汇丰Pulse"},
    {"name": "全网监控·中信外卡", "url": "https://rsshub.app/smzdm/keyword/中信国际"},
    {"name": "飞客茶馆·信用卡", "url": "https://www.feeyo.com/rss/creditcard.xml"},
    {"name": "飞客茶馆·酒店",   "url": "https://www.feeyo.com/rss/hotel.xml"},
    {"name": "什么值得买·好价", "url": "https://www.smzdm.com/tag/%E4%BF%A1%E7%94%A8%E5%8D%A1/feed/"},
]

# 扩充了 ShopBack、万事达等高级别返利通道关键词
FILTER_KEYWORDS = [
    "返现","立减","满减","优惠","积分","酒店","通兑","日历房",
    "锦江","如家","IHG","优悦","雅高","心悦界","万豪","希尔顿",
    "云闪付","飞猪","汇丰","Pulse","中信国际","GBA","大湾区","港卡",
    "外卡","境外消费","境外返现","HK版","ShopBack","万事达环球赏","Visa"
]

BANK_TAGS = {
    "汇丰": "汇丰银行", "Pulse": "汇丰Pulse", "中信国际": "中信国际", "GBA": "大湾区卡",
    "广发": "广发", "招商": "招行", "建行": "建行", "交行": "交行",
    "工行": "工行", "中信": "中信", "浦发": "浦发", "平安": "平安",
}

CHANNEL_TAGS = {
    "云闪付": "云闪付", "飞猪": "飞猪", "美团": "美团", "淘宝": "淘宝",
    "ShopBack": "ShopBack返利", "万事达": "万事达环球赏", "Visa": "Visa Offers",
    "锦江": "锦江汇", "如家": "如家", "IHG": "IHG优悦会", "雅高": "雅高ALL", 
    "万豪": "万豪", "希尔顿": "希尔顿"
}

HK_PRIORITY_KEYWORDS = [
    "汇丰", "Pulse", "中信国际", "GBA", "港卡", "外卡", "境外返现", 
    "境外消费", "HK版", "ShopBack", "万事达环球", "Visa Offer"
]

CHEAP_HOTEL_THRESHOLD = 150
RISKY_LOCATION_KEYWORDS = ["城中村", "郊区", "偏远", "工业区", "远郊"]
SAFE_AREA_KEYWORDS = ["福田", "南山", "深圳湾", "科技园", "香港", "西九龙", "广州南", "天河"]

def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"[\r\n\t]+", " ", text)
    return re.sub(r" {2,}", " ", text).strip()

def extract_price_hint(text: str):
    for pat in [r"(\d+)\s*元[/]?晚", r"仅需\s*(\d+)", r"低至\s*(\d+)", r"[¥]\s*(\d+)"]:
        for m in re.finditer(pat, text):
            v = int(m.group(1))
            if 50 <= v <= 2000: return v
    return None

def extract_tags(text: str) -> list:
    tags = []
    for kw, tag in {**BANK_TAGS, **CHANNEL_TAGS}.items():
        if kw in text and tag not in tags: tags.append(tag)
    return tags

def detect_priority(text: str) -> int:
    tl = text.lower()
    if any(kw.lower() in tl for kw in HK_PRIORITY_KEYWORDS): return 2
    return 0

def categorize(text: str) -> str:
    if any(kw in text for kw in ["酒店","锦江","如家","IHG","雅高","万豪","希尔顿","飞猪"]): return "hotel"
    if any(kw in text for kw in ["美团","淘宝","外卖","云闪付","ShopBack","返现"]): return "daily"
    return "card"

def main():
    all_items = []
    for feed in FEEDS:
        try:
            # 增加超时时间和伪装，防止被封
            resp = requests.get(feed["url"], headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=20)
            resp.encoding = resp.apparent_encoding
            d = feedparser.parse(resp.text)
            for entry in d.entries[:25]:
                title = clean_text(entry.get("title", ""))[:120]
                summary = clean_text(entry.get("summary", entry.get("description", "")))[:300]
                text = title + " " + summary
                
                if not any(kw in text for kw in FILTER_KEYWORDS): continue
                
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                price = extract_price_hint(text)
                
                warnings = []
                if price and price < CHEAP_HOTEL_THRESHOLD: warnings.append(f"低价{price}元 注意偏远或治安")
                for kw in RISKY_LOCATION_KEYWORDS:
                    if kw in text: warnings.append(f"含[{kw}] 建议核查环境"); break

                all_items.append({
                    "title": title, "summary": summary, "link": entry.get("link", ""),
                    "date": datetime(*pub[:6]).strftime("%Y-%m-%d") if pub else "",
                    "source": feed["name"], "tags": extract_tags(text),
                    "category": categorize(text), "price": price,
                    "warnings": warnings,
                    "safeArea": any(kw in text for kw in SAFE_AREA_KEYWORDS),
                    "priority": detect_priority(text),
                })
        except Exception as e:
            print(f"[跳过] {feed['name']} 暂时无法访问", file=sys.stderr)

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

    if os.path.exists("card-tracker.html"):
        with open("card-tracker.html", "r", encoding="utf-8") as f: html = f.read()
        payload = json.dumps(data, ensure_ascii=False)
        script = f'<script id="rss-inject">window.RSS_DATA={payload};</script>'
        if '<script id="rss-inject">' in html:
            html = re.sub(r'<script id="rss-inject">.*?</script>', script, html, flags=re.DOTALL)
        else:
            html = html.replace("</body>", script + "\n</body>")
        with open("card-tracker.html", "w", encoding="utf-8") as f: f.write(html)

    print(f"✅ 完成：抓取 {len(unique)} 条。")

if __name__ == "__main__":
    main()

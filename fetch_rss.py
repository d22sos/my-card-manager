#!/usr/bin/env python3
"""
隐私支付管家 - RSS抓取器 V4.4 (傻瓜化列表管理版)
功能：从同目录下的 feeds.txt 读取订阅源，方便手机端直接维护
"""

import json, re, sys, os
from datetime import datetime

try:
    import feedparser
    import requests
except ImportError:
    print("请先运行: pip install feedparser requests", file=sys.stderr)
    sys.exit(1)

# --- 默认配置 ---
# 如果 feeds.txt 不存在，会使用这里的默认源
DEFAULT_FEEDS = [
    {"name": "机酒卡资讯", "url": "https://www.xinfinite.net/c/airlinehotelcard/6.rss"}
]

FILTER_KEYWORDS = [
    "返现","立减","满减","优惠","积分","酒店","通兑","日历房",
    "锦江","如家","IHG","优悦","雅高","心悦界","万豪","希尔顿",
    "云闪付","飞猪","汇丰","Pulse","中信国际","GBA","大湾区","港卡",
    "外卡","境外消费","境外返现","HK版","ShopBack","万事达环球赏","Visa",
    "活动", "羊毛", "神卡", "免年费"
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def load_feeds_from_file():
    """从 feeds.txt 加载网址，格式：名称,网址"""
    feeds = []
    filename = "feeds.txt"
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "," in line and not line.startswith("#"):
                        name, url = line.split(",", 1)
                        feeds.append({"name": name.strip(), "url": url.strip()})
            print(f"📖 已从 {filename} 成功加载 {len(feeds)} 个订阅源")
        except Exception as e:
            print(f"⚠️ 读取 {filename} 失败: {e}")
    
    return feeds if feeds else DEFAULT_FEEDS

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
    feeds = load_feeds_from_file()
    all_items = []
    
    for feed in feeds:
        try:
            resp = requests.get(feed["url"], headers=HEADERS, timeout=15)
            resp.encoding = resp.apparent_encoding
            
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")
                
            d = feedparser.parse(resp.text)
            for entry in d.entries[:25]:
                title = clean_text(entry.get("title", ""))[:120]
                summary = clean_text(entry.get("summary", entry.get("description", "")))[:300]
                text = title + " " + summary
                
                if not any(kw in text for kw in FILTER_KEYWORDS): continue
                
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                price = extract_price_hint(text)
                
                all_items.append({
                    "title": title, "summary": summary, "link": entry.get("link", ""),
                    "date": datetime(*pub[:6]).strftime("%Y-%m-%d") if pub else "",
                    "source": feed["name"], "tags": extract_tags(text),
                    "category": categorize(text), "price": price,
                    "warnings": [f"低价{price}元" ] if price and price < 150 else [],
                    "safeArea": any(kw in text for kw in ["福田", "南山", "深圳湾", "香港"]),
                    "priority": detect_priority(text),
                })
        except Exception as e:
            all_items.append({
                "title": f"🚫 {feed['name']} - 自动抓取被拦截",
                "summary": f"该源目前无法通过 GitHub 服务器自动抓取（错误:{e}）。请在[资产]页面手动点击直达网址查阅。",
                "link": feed["url"].replace("/feed/", "/").replace("/rss/", "/"),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "系统提示", "tags": ["需手动访问"], "category": "card", "priority": 3, 
            })

    seen = set()
    unique = []
    for item in sorted(all_items, key=lambda x: (x["priority"], x["date"]), reverse=True):
        key = item["title"][:40]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    data = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "items": unique}
    
    with open("rss_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    for filename in ["card-tracker.html", "index.html"]:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f: html = f.read()
            payload = json.dumps(data, ensure_ascii=False)
            script = f'<script id="rss-inject">window.RSS_DATA={payload};</script>'
            html = re.sub(r'<script id="rss-inject">.*?</script>', script, html, flags=re.DOTALL)
            with open(filename, "w", encoding="utf-8") as f: f.write(html)
            break

if __name__ == "__main__":
    main()

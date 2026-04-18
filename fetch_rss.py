#!/usr/bin/env python3
"""
隐私支付管家 - RSS抓取器 V4.2 (防屏蔽加强版)
修复：增加浏览器级别 UA 伪装，添加异常日志
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
    {"name": "机酒卡资讯",       "url": "https://www.xinfinite.net/c/airlinehotelcard/6.rss"},
    {"name": "什么值得买·信用卡", "url": "https://www.smzdm.com/tag/%E4%BF%A1%E7%94%A8%E5%8D%A1/feed/"},
    {"name": "什么值得买·银行",   "url": "https://www.smzdm.com/tag/%E9%93%B6%E8%A1%8C/feed/"},
    {"name": "什么值得买·酒店",   "url": "https://www.smzdm.com/tag/%E9%85%92%E5%BA%97/feed/"},
    {"name": "飞客茶馆·信用卡",   "url": "https://www.feeyo.com/rss/creditcard.xml"},
    {"name": "飞客茶馆·酒店",     "url": "https://www.feeyo.com/rss/hotel.xml"},
]

FILTER_KEYWORDS = [
    "返现","立减","满减","优惠","积分","酒店","通兑","日历房",
    "锦江","如家","IHG","优悦","雅高","心悦界","万豪","希尔顿",
    "云闪付","飞猪","汇丰","Pulse","中信国际","GBA","大湾区","港卡",
    "外卡","境外消费","境外返现","HK版","ShopBack","万事达环球赏","Visa",
    "活动", "羊毛", "神卡", "免年费" # 稍微放宽了过滤条件
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

# 伪装成真实的桌面端浏览器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

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
    print("🚀 开始抓取数据...")
    for feed in FEEDS:
        try:
            resp = requests.get(feed["url"], headers=HEADERS, timeout=15)
            resp.encoding = resp.apparent_encoding
            
            if resp.status_code != 200:
                print(f"[警告] {feed['name']} 返回状态码 {resp.status_code}，可能被反爬屏蔽")
                continue
                
            d = feedparser.parse(resp.text)
            raw_entries_count = len(d.entries)
            valid_entries = 0
            
            for entry in d.entries[:25]:
                title = clean_text(entry.get("title", ""))[:120]
                summary = clean_text(entry.get("summary", entry.get("description", "")))[:300]
                text = title + " " + summary
                
                if not any(kw in text for kw in FILTER_KEYWORDS): continue
                valid_entries += 1
                
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
            print(f"[成功] {feed['name']}: 抓取到 {raw_entries_count} 条，匹配关键字保留 {valid_entries} 条")
        except Exception as e:
            print(f"[错误] {feed['name']} 访问异常: {e}", file=sys.stderr)

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

    # 兼容你的 HTML 文件名，请确保你使用的 HTML 文件名是下面的其中一个
    target_html = None
    for filename in ["card-tracker.html", "index.html"]:
        if os.path.exists(filename):
            target_html = filename
            break

    if target_html:
        with open(target_html, "r", encoding="utf-8") as f: html = f.read()
        payload = json.dumps(data, ensure_ascii=False)
        script = f'<script id="rss-inject">window.RSS_DATA={payload};</script>'
        if '<script id="rss-inject">' in html:
            html = re.sub(r'<script id="rss-inject">.*?</script>', script, html, flags=re.DOTALL)
        else:
            html = html.replace("</body>", script + "\n</body>")
        with open(target_html, "w", encoding="utf-8") as f: f.write(html)
        print(f"✅ 成功将数据注入前端文件：{target_html}")
    else:
        print("⚠️ 未找到 index.html 或 card-tracker.html，已生成 rss_data.json 数据文件。")

    print(f"🎉 任务完成：总共筛选出 {len(unique)} 条匹配信息。")

if __name__ == "__main__":
    main()

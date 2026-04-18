#!/usr/bin/env python3
"""
支付管家 - RSS抓取器 V6
升级：完整覆盖工农中建交邮广发光大浦发民生中信汇丰及港卡关键词
"""

import json, re, sys, os
from datetime import datetime

try:
    import feedparser
    import requests
except ImportError:
    print("请先运行: pip install feedparser requests", file=sys.stderr)
    sys.exit(1)

# ──────────────────────────────────────────────
#  订阅源（feeds.txt 优先，否则用此默认）
# ──────────────────────────────────────────────
DEFAULT_FEEDS = [
    {"name": "机酒卡资讯", "url": "https://www.xinfinite.net/c/airlinehotelcard/6.rss"},
    {"name": "非常旅客",   "url": "https://www.verylvke.com/feed/"},
]

# ──────────────────────────────────────────────
#  过滤关键词（命中任一则保留条目）
# ──────────────────────────────────────────────
FILTER_KEYWORDS = [
    # 通用优惠词
    "返现","立减","满减","优惠","积分","活动","羊毛","神卡","免年费","权益","福利",
    # 酒店品牌
    "酒店","雅高","Accor","ALL积分","IHG","优悦","洲际","假日","英迪格",
    "万豪","希尔顿","锦江","如家","凯悦","香格里拉","威斯汀","美居","诺富特",
    # 航司
    "国航","南航","东航","国泰","里程","升舱","里数","常旅客",
    # 银行 - 内地
    "工行","农行","中行","建行","交行","邮储","广发","光大","浦发","民生","中信","汇丰",
    "ICBC","ABC","CCB","BOCOM","招行",
    # 银行 - 港卡/外卡
    "Pulse","GBA","大湾区","Moin","ZA Bank","ZA卡","中信国际","汇丰HK","中银香港","BOCHKpay",
    # 支付渠道
    "云闪付","Apple Pay","万事达","Mastercard","Visa","银联",
    "万事达环球赏","Visa Offers","ShopBack","TopCashback","Extrabux",
    # 日常消费
    "美团","滴滴","淘宝","拼多多","飞猪","外卖",
]

# ──────────────────────────────────────────────
#  Tag 提取映射（关键词 → 标签名）
# ──────────────────────────────────────────────
BANK_TAGS = {
    # 内地银行
    "工行": "工行", "农行": "农行", "中行": "中行", "建行": "建行",
    "交行": "交行", "邮储": "邮储", "广发": "广发", "光大": "光大",
    "浦发": "浦发", "民生": "民生", "中信": "中信",
    "招商": "招行", "兴业": "兴业", "华夏": "华夏",
    # 港卡
    "汇丰": "汇丰", "Pulse": "汇丰Pulse", "GBA": "GBA大湾区",
    "Moin": "中信Moin", "中信国际": "中信国际HK", "ZA Bank": "ZA Bank",
    "中银香港": "中银香港", "BOCHKpay": "BOCHKpay",
}

CHANNEL_TAGS = {
    "云闪付": "云闪付", "Apple Pay": "Apple Pay",
    "飞猪": "飞猪", "美团": "美团", "淘宝": "淘宝", "拼多多": "拼多多",
    "ShopBack": "ShopBack返利", "TopCashback": "TopCashback",
    "万事达": "万事达环球赏", "Mastercard": "万事达环球赏",
    "Visa": "Visa Offers",
    "锦江": "锦江荟", "如家": "如家", "IHG": "IHG优悦会",
    "雅高": "雅高ALL", "Accor": "雅高ALL",
    "万豪": "万豪", "希尔顿": "希尔顿",
}

# 港卡/境外优先权（priority=2 排最前）
HK_PRIORITY_KWS = [
    "汇丰", "Pulse", "中信国际", "GBA", "Moin", "ZA Bank",
    "港卡", "外卡", "境外返现", "境外消费", "HK版",
    "ShopBack", "TopCashback", "万事达环球", "Visa Offer"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def load_feeds():
    feeds = []
    path = "feeds.txt"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "," in line and not line.startswith("#"):
                        name, url = line.split(",", 1)
                        feeds.append({"name": name.strip(), "url": url.strip()})
            print(f"📖 已从 {path} 加载 {len(feeds)} 个订阅源")
        except Exception as e:
            print(f"⚠️ 读取 {path} 失败: {e}")
    return feeds if feeds else DEFAULT_FEEDS


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z#0-9]+;", " ", text)
    text = re.sub(r"[\r\n\t]+", " ", text)
    return re.sub(r" {2,}", " ", text).strip()


def extract_price(text: str):
    for pat in [r"(\d+)\s*元[/]?晚", r"仅需\s*(\d+)", r"低至\s*(\d+)", r"[¥]\s*(\d+)"]:
        for m in re.finditer(pat, text):
            v = int(m.group(1))
            if 50 <= v <= 5000:
                return v
    return None


def extract_tags(text: str) -> list:
    tags = []
    for kw, tag in {**BANK_TAGS, **CHANNEL_TAGS}.items():
        if kw.lower() in text.lower() and tag not in tags:
            tags.append(tag)
    return tags


def priority(text: str) -> int:
    tl = text.lower()
    if any(k.lower() in tl for k in HK_PRIORITY_KWS):
        return 2
    return 0


def categorize(text: str) -> str:
    if any(k in text for k in ["酒店","锦江","如家","IHG","雅高","Accor","万豪","希尔顿","凯悦"]):
        return "hotel"
    if any(k in text for k in ["美团","淘宝","拼多多","外卖","云闪付","ShopBack","TopCashback","返现"]):
        return "daily"
    return "card"


def main():
    feeds = load_feeds()
    all_items = []

    for feed in feeds:
        print(f"📡 抓取：{feed['name']} …", end=" ")
        try:
            resp = requests.get(feed["url"], headers=HEADERS, timeout=20)
            resp.encoding = resp.apparent_encoding
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")

            d = feedparser.parse(resp.text)
            count = 0
            for entry in d.entries[:30]:
                title   = clean(entry.get("title", ""))[:120]
                summary = clean(entry.get("summary", entry.get("description", "")))[:350]
                text    = title + " " + summary

                if not any(k.lower() in text.lower() for k in FILTER_KEYWORDS):
                    continue

                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                price = extract_price(text)

                all_items.append({
                    "title":    title,
                    "summary":  summary,
                    "link":     entry.get("link", ""),
                    "date":     datetime(*pub[:6]).strftime("%Y-%m-%d") if pub else "",
                    "source":   feed["name"],
                    "tags":     extract_tags(text),
                    "category": categorize(text),
                    "price":    price,
                    "warnings": [f"低价{price}元"] if price and price < 150 else [],
                    "safeArea": any(k in text for k in ["广东","深圳","广州","香港","佛山","东莞"]),
                    "priority": priority(text),
                })
                count += 1
            print(f"✅ {count} 条")

        except Exception as e:
            print(f"❌ {e}")
            all_items.append({
                "title":    f"🚫 {feed['name']} - 抓取失败",
                "summary":  f"错误：{e}。请在[配置]页手动访问官网。",
                "link":     feed["url"],
                "date":     datetime.now().strftime("%Y-%m-%d"),
                "source":   "系统提示",
                "tags":     ["需手动访问"],
                "category": "card",
                "priority": 3,
            })

    # 去重 + 排序（priority 高、日期新 优先）
    seen, unique = set(), []
    for item in sorted(all_items, key=lambda x: (x.get("priority",0), x.get("date","")), reverse=True):
        key = item["title"][:40]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    data = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "items": unique}

    # 写 JSON
    with open("rss_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n📝 rss_data.json 已更新，共 {len(unique)} 条")

    # 注入 HTML
    payload = json.dumps(data, ensure_ascii=False)
    script  = f'<script id="rss-inject">window.RSS_DATA={payload};</script>'

    for fname in ["card-tracker.html", "index.html"]:
        if os.path.exists(fname):
            with open(fname, "r", encoding="utf-8") as f:
                html = f.read()
            html = re.sub(r'<script id="rss-inject">.*?</script>', script, html, flags=re.DOTALL)
            with open(fname, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"💉 已注入 {fname}")
            break


if __name__ == "__main__":
    main()

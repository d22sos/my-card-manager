#!/usr/bin/env python3
"""
信用卡活动RSS抓取器（自动推荐版）
自动提取银行+酒店标签，供前端匹配用户卡片
"""

import json, re, sys, os
from datetime import datetime

try:
    import feedparser
    import requests
except ImportError:
    sys.exit(1)

# 帮你增加了更多飞客茶馆和我爱卡的源，覆盖更全
FEEDS = [
    {"name": "什么值得买·信用卡", "url": "https://www.smzdm.com/tag/%E4%BF%A1%E7%94%A8%E5%8D%A1/feed/"},
    {"name": "什么值得买·银行活动", "url": "https://www.smzdm.com/tag/%E9%93%B6%E8%A1%8C/feed/"},
    {"name": "飞客茶馆·信用卡", "url": "https://www.feeyo.com/rss/creditcard.xml"},
    {"name": "飞客茶馆·酒店", "url": "https://www.feeyo.com/rss/hotel.xml"},
    {"name": "卡宝宝·活动", "url": "https://www.kababao.com/rss.xml"},
    {"name": "我爱卡·资讯", "url": "https://news.51credit.com/rss.xml"},
]

FILTER_KEYWORDS = ["报名","返现","立减","满减","折扣","优惠","积分","酒店","锦江","如家","IHG","优悦","雅高","心悦界","Accor","ALL","云闪付"]

BANK_TAGS = {
    "广发": "广发", "招商": "招行", "建行": "建行", "交行": "交行",
    "工行": "工行", "农行": "农行", "中信": "中信", "光大": "光大",
    "浦发": "浦发", "平安": "平安", "民生": "民生", "华夏": "华夏",
    "如家": "如家", "锦江": "锦江汇"
}

CHANNEL_TAGS = {
    "滴滴": "滴滴", "美团": "美团", "淘宝": "淘宝", "拼多多": "拼多多",
    "酒店": "酒店", "锦江": "锦江汇", "如家": "如家", "IHG": "IHG优悦会",
    "优悦": "IHG优悦会", "雅高": "雅高心悦界", "Accor": "雅高心悦界",
    "心悦界": "雅高心悦界", "云闪付": "云闪付"
}

def extract_tags(text):
    tags = []
    for kw, tag in {**BANK_TAGS, **CHANNEL_TAGS}.items():
        if kw in text and tag not in tags:
            tags.append(tag)
    return tags

def main():
    all_items = []
    for feed in FEEDS:
        try:
            resp = requests.get(feed["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            resp.encoding = resp.apparent_encoding
            d = feedparser.parse(resp.text)
            for entry in d.entries[:30]:
                title = entry.get("title", "")
                summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:250]
                text = title + " " + summary
                if not any(kw in text for kw in FILTER_KEYWORDS):
                    continue
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                date_str = datetime(*pub[:6]).strftime("%Y-%m-%d") if pub else ""
                items = {
                    "title": title.strip(),
                    "summary": summary.strip(),
                    "link": entry.get("link", ""),
                    "date": date_str,
                    "source": feed["name"],
                    "tags": extract_tags(text)
                }
                all_items.append(items)
        except:
            pass

    # 去重
    seen = set()
    unique = [item for item in sorted(all_items, key=lambda x: x["date"], reverse=True) 
              if item["title"][:30] not in seen and not seen.add(item["title"][:30])]

    data = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "items": unique}
    with open("rss_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 已经修复的注入逻辑，保证每次都能成功写入
    if os.path.exists("card-tracker.html"):
        with open("card-tracker.html", "r", encoding="utf-8") as f:
            html = f.read()
            
        script = f'<script id="rss-inject">window.RSS_DATA = {json.dumps(data, ensure_ascii=False)};</script>'
        
        if '<script id="rss-inject">' in html:
            html = re.sub(r'<script id="rss-inject">.*?</script>', script, html, flags=re.DOTALL)
        else:
            html = html.replace("</body>", script + "\n</body>")
            
        with open("card-tracker.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ 抓取 {len(unique)} 条活动并注入")
    print("完成")

if __name__ == "__main__":
    main()

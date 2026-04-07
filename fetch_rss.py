#!/usr/bin/env python3
"""
信用卡活动RSS抓取器（升级版）
新增：锦江汇、IHG、雅高、心悦界、云闪付等酒店关键词
用法：python fetch_rss.py
"""

import json, re, sys, os
from datetime import datetime

try:
    import feedparser
    import requests
except ImportError:
    print("请先安装依赖：pip install feedparser requests")
    sys.exit(1)

# ── RSS 源配置 ─────────────────────────────────────────────
FEEDS = [
    {"name": "什么值得买·信用卡", "url": "https://www.smzdm.com/tag/%E4%BF%A1%E7%94%A8%E5%8D%A1/feed/", "keywords": []},
    {"name": "什么值得买·银行活动", "url": "https://www.smzdm.com/tag/%E9%93%B6%E8%A1%8C/feed/", "keywords": []},
    {"name": "飞客茶馆·信用卡", "url": "https://www.feeyo.com/rss/creditcard.xml", "keywords": []},
    {"name": "卡宝宝·活动", "url": "https://www.kababao.com/rss.xml", "keywords": []},
]

# ── 关键词过滤 + 酒店加强 ───────────────────────────────
FILTER_KEYWORDS = [
    "报名", "返现", "立减", "满减", "折扣", "优惠", "积分",
    "八达通", "广发", "招行", "建行", "交行", "浦发", "中信",
    "工行", "农行", "光大", "华夏", "民生", "平安",
    "滴滴", "美团", "淘宝", "京东", "拼多多", "酒店",
    "锦江", "IHG", "优悦", "雅高", "心悦界", "Accor", "ALL", "云闪付",
]

BANK_TAGS = {
    "广发": "广发", "招商": "招行", "建行": "建行", "交行": "交行",
    "工行": "工行", "农行": "农行", "中信": "中信", "光大": "光大",
    "浦发": "浦发", "平安": "平安", "民生": "民生", "华夏": "华夏",
    "八达通": "八达通", "航空": "航空里程",
}

CHANNEL_TAGS = {
    "滴滴": "滴滴", "美团": "美团", "淘宝": "淘宝", "京东": "京东",
    "拼多多": "拼多多", "酒店": "酒店", "锦江": "锦江汇",
    "IHG": "IHG优悦会", "优悦": "IHG优悦会", "雅高": "雅高心悦界",
    "Accor": "雅高心悦界", "心悦界": "雅高心悦界", "ALL": "雅高心悦界",
    "云闪付": "云闪付",
}

def extract_tags(text):
    tags = []
    for kw, tag in BANK_TAGS.items():
        if kw in text and tag not in tags: tags.append(tag)
    for kw, tag in CHANNEL_TAGS.items():
        if kw in text and tag not in tags: tags.append(tag)
    return tags

# （后面 fetch_feed、main 函数完全不变，保持原样）
def fetch_feed(feed_cfg):
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (RSS Reader)"}
        resp = requests.get(feed_cfg["url"], headers=headers, timeout=10)
        resp.encoding = resp.apparent_encoding
        d = feedparser.parse(resp.text)
        for entry in d.entries[:30]:
            title = entry.get("title", "")
            summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:200]
            text = title + summary
            if FILTER_KEYWORDS and not any(kw in text for kw in FILTER_KEYWORDS):
                continue
            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            date_str = datetime(*pub[:6]).strftime("%Y-%m-%d") if pub else ""
            items.append({
                "title": title.strip(),
                "summary": summary.strip(),
                "link": entry.get("link", ""),
                "date": date_str,
                "source": feed_cfg["name"],
                "tags": extract_tags(text),
            })
        print(f"  ✓ {feed_cfg['name']}：抓到 {len(items)} 条")
    except Exception as e:
        print(f"  ✗ {feed_cfg['name']} 失败：{e}")
    return items

def main():
    print(f"\n{'='*40}")
    print(f"信用卡活动RSS抓取（酒店版）  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*40}")
    
    all_items = []
    for feed in FEEDS:
        all_items.extend(fetch_feed(feed))
    
    seen = set()
    unique = []
    for item in sorted(all_items, key=lambda x: x["date"], reverse=True):
        key = item["title"][:20]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    
    print(f"\n共获取 {len(unique)} 条活动（去重后）")
    
    with open("rss_data.json", "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "count": len(unique), "items": unique}, f, ensure_ascii=False, indent=2)
    print("已保存 rss_data.json")
    
    html_path = "card-tracker.html"
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        data_block = f"""<script id="rss-inject">
window.RSS_DATA = {json.dumps({"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "items": unique}, ensure_ascii=False)};
</script>"""
        if '<script id="rss-inject">' in html:
            html = re.sub(r'<script id="rss-inject">.*?</script>', data_block, html, flags=re.DOTALL)
        else:
            html = html.replace("</body>", data_block + "\n</body>")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"已注入 {html_path}")
    else:
        print(f"未找到 {html_path}，数据已保存到 rss_data.json")
    
    print("\n完成！\n")

if __name__ == "__main__":
    main()
import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
from collections import OrderedDict
import concurrent.futures
import re

OUTPUT_JSON = "https_proxies.json"
OUTPUT_TXT = "https_proxies.txt"
MAX_WORKERS = 60
TEST_URL = "https://httpbin.org/ip"
TIMEOUT = 8

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}

def scrape_freeproxy_world(max_pages=15):
    print("正在抓取 freeproxy.world (所有 HTTPS)...")
    proxies = []
    for page in range(1, max_pages + 1):
        url = f"https://www.freeproxy.world/?type=https&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue

            # 使用正则匹配 Markdown 表格行
            lines = resp.text.splitlines()
            for line in lines:
                if re.match(r'^\|\s*[\d\.]', line):  # 匹配 IP 开头的表格行
                    cols = [col.strip() for col in line.split('|') if col.strip()]
                    if len(cols) >= 3:
                        ip = cols[0]
                        port = cols[1]
                        country = cols[2] if len(cols) > 2 else "Unknown"
                        
                        if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip) and port.isdigit():
                            proxies.append({
                                "ip": ip,
                                "port": int(port),
                                "country": country,
                                "protocol": "https",
                                "source": "freeproxy.world",
                                "last_checked": datetime.now().isoformat()
                            })
            print(f"  第 {page} 页抓取完成 → 当前累计 {len(proxies)} 条")
            time.sleep(1.3)
        except Exception as e:
            print(f"第 {page} 页错误: {e}")
            break
    return proxies

def scrape_proxyscrape():
    print("正在抓取 ProxyScrape...")
    try:
        # 新地址尝试
        urls = [
            "https://api.proxyscrape.com/v4/free-proxy-list/get?protocol=http&ssl=yes&limit=9999",
            "https://proxyscrape.com/free-proxy-list"
        ]
        for url in urls:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                # 如果是文本列表
                if '\n' in resp.text and ':' in resp.text:
                    lines = resp.text.strip().splitlines()
                    proxies = []
                    for line in lines:
                        if ':' in line and not line.startswith('#'):
                            parts = line.strip().split(':')
                            if len(parts) >= 2 and parts[0].count('.') == 3:
                                proxies.append({
                                    "ip": parts[0],
                                    "port": int(parts[1].split()[0]),
                                    "country": "Unknown",
                                    "protocol": "https",
                                    "source": "proxyscrape"
                                })
                    print(f"ProxyScrape 抓取到 {len(proxies)} 条")
                    return proxies
    except Exception as e:
        print(f"ProxyScrape 错误: {e}")
    return []

def check_proxy(proxy):
    proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
    try:
        start = time.time()
        r = requests.get(TEST_URL, proxies={"http": proxy_url, "https": proxy_url},
                        timeout=TIMEOUT, headers=headers)
        if r.status_code in (200, 403, 429):
            proxy["latency"] = round((time.time() - start) * 1000)
            proxy["status"] = "working"
            return proxy
    except:
        pass
    return None

def main():
    start_time = time.time()
    
    all_proxies = scrape_freeproxy_world(max_pages=10)   # 先抓10页，够用
    all_proxies.extend(scrape_proxyscrape())
    
    # 去重
    seen = OrderedDict()
    for p in all_proxies:
        key = f"{p['ip']}:{p['port']}"
        if key not in seen:
            seen[key] = p
    unique_proxies = list(seen.values())
    
    print(f"\n去重后共有 {len(unique_proxies)} 个唯一 HTTPS 代理")
    
    # 验证
    print("开始验证可用代理...")
    working = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_proxy, unique_proxies))
        working = [r for r in results if r is not None]
    
    # 保存
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(working, f, ensure_ascii=False, indent=2)
    
    with open(OUTPUT_TXT, "w") as f:
        for p in working:
            f.write(f"{p['ip']}:{p['port']}\n")
    
    print(f"\n✅ 完成！可用 HTTPS 代理: {len(working)} 个")
    print(f"总耗时: {round(time.time()-start_time, 1)} 秒")

if __name__ == "__main__":
    main()

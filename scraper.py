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

MAX_WORKERS = 40          # 降低并发，防止被封或超时
TEST_URL = "https://httpbin.org/ip"
TIMEOUT = 12              # 放宽超时

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def scrape_freeproxy_world(max_pages=10):
    print("正在抓取 freeproxy.world...")
    proxies = []
    for page in range(1, max_pages + 1):
        try:
            url = f"https://www.freeproxy.world/?type=https&page={page}"
            resp = requests.get(url, headers=headers, timeout=15)
            for line in resp.text.splitlines():
                if re.match(r'^\|\s*[\d\.]', line.strip()):
                    cols = [col.strip() for col in line.split('|') if col.strip()]
                    if len(cols) >= 3:
                        ip = cols[0]
                        port = cols[1]
                        country = cols[2] if len(cols) > 2 else "Unknown"
                        if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip) and port.isdigit():
                            proxies.append({
                                "ip": ip, "port": int(port), "country": country,
                                "protocol": "https", "source": "freeproxy.world"
                            })
            print(f"  freeproxy.world 第 {page} 页 → 累计 {len(proxies)} 条")
            time.sleep(1)
        except Exception as e:
            print(f"freeproxy.world 错误: {e}")
            break
    return proxies

def scrape_proxyscrape():
    print("正在抓取 ProxyScrape...")
    try:
        url = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&limit=9999&ssl=yes"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            count = 0
            for line in resp.text.strip().splitlines():
                if ':' in line:
                    ip, port = line.strip().split(':', 1)
                    proxies_list.append({
                        "ip": ip, "port": int(port), "country": "Unknown",
                        "protocol": "https", "source": "proxyscrape"
                    })
                    count += 1
            print(f"ProxyScrape 抓取到 {count} 条")
    except Exception as e:
        print(f"ProxyScrape 错误: {e}")

def scrape_geonode():
    print("正在抓取 Geonode...")
    try:
        url = "https://proxylist.geonode.com/api/proxy-list?limit=500&protocols=https&speed=medium"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            count = 0
            for item in data.get("data", []):
                proxies_list.append({
                    "ip": item["ip"], 
                    "port": int(item["port"]), 
                    "country": item.get("country", "Unknown"),
                    "protocol": "https", 
                    "source": "geonode"
                })
                count += 1
            print(f"Geonode 抓取到 {count} 条")
    except Exception as e:
        print(f"Geonode 错误: {e}")

def scrape_freeproxylist():
    print("正在抓取 free-proxy-list.net...")
    try:
        urls = ["https://free-proxy-list.net/", "https://www.sslproxies.org/"]
        for url in urls:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            rows = soup.select("table tr")
            for row in rows[1:]:
                cols = row.find_all("td")
                if len(cols) > 1:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip) and port.isdigit():
                        proxies_list.append({
                            "ip": ip, "port": int(port), "country": "Unknown",
                            "protocol": "https", "source": "free-proxy-list.net"
                        })
    except Exception as e:
        print(f"free-proxy-list.net 错误: {e}")

# ==================== 主程序 ====================
proxies_list = []   # 全局临时列表

def main():
    start_time = time.time()
    
    scrape_freeproxy_world()
    scrape_proxyscrape()
    scrape_geonode()
    scrape_freeproxylist()
    
    # 去重
    seen = OrderedDict()
    for p in proxies_list:
        key = f"{p['ip']}:{p['port']}"
        if key not in seen:
            seen[key] = p
    unique_proxies = list(seen.values())
    
    print(f"\n去重后共有 {len(unique_proxies)} 个唯一 HTTPS 代理")
    
    # 验证（已放宽）
    print("开始验证可用代理（已放宽标准）...")
    working = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_proxy, unique_proxies))
        working = [r for r in results if r]
    
    # 保存
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(working, f, ensure_ascii=False, indent=2)
    
    with open(OUTPUT_TXT, "w") as f:
        for p in working:
            f.write(f"{p['ip']}:{p['port']}\n")
    
    print(f"\n🎉 完成！可用 HTTPS 代理: {len(working)} 个")
    print(f"总耗时: {round(time.time()-start_time, 1)} 秒")

def check_proxy(proxy):
    proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
    try:
        start = time.time()
        r = requests.get(TEST_URL, proxies={"http": proxy_url, "https": proxy_url},
                        timeout=TIMEOUT, headers=headers)
        if r.status_code in (200, 403, 429, 404, 503):
            proxy["latency"] = round((time.time() - start) * 1000)
            proxy["status"] = "working"
            proxy["last_checked"] = datetime.now().isoformat()
            return proxy
    except:
        pass
    return None

if __name__ == "__main__":
    main()

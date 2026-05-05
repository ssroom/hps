import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
from collections import OrderedDict
import concurrent.futures
import threading

OUTPUT_JSON = "https_proxies.json"
OUTPUT_TXT = "https_proxies.txt"
MAX_WORKERS = 60
TEST_URL = "https://httpbin.org/ip"
TIMEOUT = 8

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}

def scrape_freeproxy_world():
    print("正在抓取 freeproxy.world (所有 HTTPS)...")
    proxies = []
    page = 1
    while page <= 30:   # 最多抓30页，避免无限循环
        url = f"https://www.freeproxy.world/?type=https&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 新结构适配
            rows = soup.select("table tr")
            for row in rows[1:]:   # 跳过表头
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue
                ip_tag = cols[0].find("a") or cols[0]
                ip = ip_tag.text.strip()
                port = cols[1].text.strip()
                
                country = "Unknown"
                if len(cols) > 2:
                    country_tag = cols[2].find("a")
                    country = country_tag.text.strip() if country_tag else cols[2].text.strip()
                
                if ip and port and port.isdigit():
                    proxies.append({
                        "ip": ip,
                        "port": int(port),
                        "country": country,
                        "protocol": "https",
                        "source": "freeproxy.world"
                    })
            print(f"  第 {page} 页 → {len(rows)-1} 条")
            if len(rows) < 10:  # 最后一页
                break
            page += 1
            time.sleep(1.2)
        except Exception as e:
            print(f"freeproxy.world 错误: {e}")
            break
    return proxies

def scrape_proxyscrape():
    print("正在抓取 ProxyScrape...")
    try:
        # 更新后的 API
        url = "https://api.proxyscrape.com/v4/free-proxy-list/get?protocol=http&ssl=yes&anonymity=all&limit=9999&timeout=8000"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and resp.text.strip():
            lines = [line.strip() for line in resp.text.splitlines() if ':' in line]
            proxies = []
            for line in lines:
                if ':' in line:
                    ip, port = line.split(':', 1)
                    proxies.append({
                        "ip": ip,
                        "port": int(port),
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
        if r.status_code in (200, 403, 429):   # 403/429也算部分可用
            latency = round((time.time() - start) * 1000)
            proxy["latency"] = latency
            proxy["last_checked"] = datetime.now().isoformat()
            proxy["status"] = "working"
            return proxy
    except:
        pass
    return None

def main():
    start_time = time.time()
    
    all_proxies = scrape_freeproxy_world()
    all_proxies.extend(scrape_proxyscrape())
    # spys.one 暂时放弃（反爬太强）
    
    # 去重
    seen = OrderedDict()
    for p in all_proxies:
        key = f"{p['ip']}:{p['port']}"
        if key not in seen:
            seen[key] = p
    unique_proxies = list(seen.values())
    
    print(f"\n去重后共有 {len(unique_proxies)} 个唯一 HTTPS 代理")
    
    # 检查可用性
    print("开始验证可用代理...")
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
    
    print(f"\n✅ 完成！可用 HTTPS 代理: {len(working)} 个")
    print(f"总耗时: {round(time.time()-start_time, 1)} 秒")

if __name__ == "__main__":
    main()

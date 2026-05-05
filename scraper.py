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
MAX_WORKERS = 50          # 并发检查数量，根据自己网络调整
TEST_URL = "https://httpbin.org/ip"  # 用于验证代理
TIMEOUT = 10

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

proxies_list = []
lock = threading.Lock()

def scrape_freeproxy_world():
    print("正在抓取 freeproxy.world...")
    proxies = []
    page = 1
    while True:
        url = f"https://www.freeproxy.world/?type=https&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find("table")
            if not table:
                break
            rows = table.find_all("tr")[1:]
            if not rows:
                break
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 4:
                    continue
                ip = cols[0].text.strip()
                port = cols[1].text.strip()
                country = cols[2].text.strip()
                if ip and port and port.isdigit():
                    proxies.append({
                        "ip": ip,
                        "port": int(port),
                        "country": country,
                        "protocol": "https",
                        "source": "freeproxy.world"
                    })
            print(f"  第 {page} 页抓取完成 ({len(rows)} 条)")
            page += 1
            time.sleep(1.5)
        except Exception as e:
            print(f"freeproxy.world 第 {page} 页错误: {e}")
            break
    return proxies

def scrape_proxyscrape():
    print("正在抓取 ProxyScrape API...")
    try:
        url = "https://api.proxyscrape.com/v4/free-proxy-list/get?protocol=http&ssl=yes&anonymity=all&limit=2000&timeout=10000"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            lines = resp.text.strip().split('\n')
            proxies = []
            for line in lines:
                if ':' in line:
                    ip, port = line.strip().split(':')
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

def scrape_spys_one():
    print("正在抓取 spys.one...")
    proxies = []
    urls = [
        "https://spys.one/en/https-ssl-proxy/",
        "https://spys.one/en/free-proxy-list/"
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            # spys.one 表格结构较复杂，这里提取常见模式
            rows = soup.find_all("tr", class_=lambda x: x and "spy1x" in x or "spy1xx" in x)
            for row in rows:
                tds = row.find_all("td")
                if len(tds) >= 3:
                    proxy_text = tds[0].text.strip()
                    if ':' in proxy_text:
                        ip, port = proxy_text.split(':')
                        country_td = tds[2] if len(tds) > 2 else None
                        country = country_td.text.strip()[:2] if country_td else "Unknown"
                        if ip and port.isdigit():
                            proxies.append({
                                "ip": ip,
                                "port": int(port),
                                "country": country,
                                "protocol": "https",
                                "source": "spys.one"
                            })
            time.sleep(2)
        except Exception as e:
            print(f"spys.one 错误: {e}")
    print(f"spys.one 抓取到 {len(proxies)} 条")
    return proxies

def check_proxy(proxy):
    """并发检查单个代理"""
    proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
    try:
        start = time.time()
        resp = requests.get(TEST_URL, proxies={"http": proxy_url, "https": proxy_url}, 
                           timeout=TIMEOUT, headers=headers)
        if resp.status_code == 200:
            latency = round((time.time() - start) * 1000)
            with lock:
                proxy["latency"] = latency
                proxy["last_checked"] = datetime.now().isoformat()
                proxy["status"] = "working"
            return proxy
    except:
        pass
    return None

def check_all_proxies(proxies):
    print(f"开始并发检查 {len(proxies)} 个代理（最大并发 {MAX_WORKERS}）...")
    working = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(check_proxy, proxies)
        for r in results:
            if r:
                working.append(r)
                print(f"✅ 可用: {r['ip']}:{r['port']}  ({r.get('latency', '?')}ms)")
    return working

# ====================== 主程序 ======================
if __name__ == "__main__":
    start_time = time.time()
    
    all_proxies = []
    all_proxies.extend(scrape_freeproxy_world())
    all_proxies.extend(scrape_proxyscrape())
    all_proxies.extend(scrape_spys_one())
    
    # 去重
    seen = OrderedDict()
    for p in all_proxies:
        key = f"{p['ip']}:{p['port']}"
        if key not in seen:
            seen[key] = p
    unique_proxies = list(seen.values())
    
    print(f"\n去重后共有 {len(unique_proxies)} 个唯一 HTTPS 代理")
    
    # 检查可用性
    working_proxies = check_all_proxies(unique_proxies)
    
    # 保存文件
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(working_proxies, f, ensure_ascii=False, indent=2)
    
    with open(OUTPUT_TXT, "w") as f:
        for p in working_proxies:
            f.write(f"{p['ip']}:{p['port']}\n")
    
    print(f"\n✅ 完成！可用 HTTPS 代理: {len(working_proxies)} 个")
    print(f"耗时: {round(time.time()-start_time, 1)} 秒")
    print(f"文件已保存：{OUTPUT_JSON} 和 {OUTPUT_TXT}")
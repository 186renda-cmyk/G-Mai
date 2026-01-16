import urllib.request
import json
import xml.etree.ElementTree as ET
import os

# 配置信息
HOST = "g-mai.top"
API_KEY = "bb220a8b740949c7973c6e9ee51ac9e9"
KEY_LOCATION = f"https://{HOST}/{API_KEY}.txt"
SITEMAP_FILE = "sitemap.xml"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

def get_urls_from_sitemap(sitemap_path):
    """从 sitemap.xml 解析 URL"""
    urls = []
    try:
        tree = ET.parse(sitemap_path)
        root = tree.getroot()
        # Sitemap namespace
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        for url in root.findall('ns:url', namespace):
            loc = url.find('ns:loc', namespace)
            if loc is not None and loc.text:
                urls.append(loc.text)
        print(f"成功从 {sitemap_path} 提取到 {len(urls)} 个 URL。")
    except Exception as e:
        print(f"读取 Sitemap 失败: {e}")
    return urls

def submit_to_indexnow(url_list):
    """提交 URL 到 IndexNow"""
    if not url_list:
        print("没有 URL 需要提交。")
        return

    data = {
        "host": HOST,
        "key": API_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": url_list
    }

    json_data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(
        INDEXNOW_ENDPOINT, 
        data=json_data, 
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )

    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            if status_code == 200:
                print("✅ 提交成功！IndexNow 已接收请求。")
            elif status_code == 202:
                print("✅ 提交成功！IndexNow 已接收请求（处理中）。")
            else:
                print(f"⚠️ 提交可能遇到问题，状态码: {status_code}")
                print(response.read().decode('utf-8'))
    except urllib.request.HTTPError as e:
        print(f"❌ 提交失败，HTTP 错误: {e.code}")
        print(e.read().decode('utf-8'))
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    print("🚀 开始 IndexNow 自动提交脚本...")
    
    # 检查 sitemap 是否存在
    if os.path.exists(SITEMAP_FILE):
        urls = get_urls_from_sitemap(SITEMAP_FILE)
        if urls:
            print("正在提交以下 URL:")
            for url in urls:
                print(f" - {url}")
            submit_to_indexnow(urls)
    else:
        print(f"❌ 找不到 {SITEMAP_FILE} 文件，请确保脚本在项目根目录下运行。")

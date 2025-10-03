import sys
import os
import time
import json
import requests
import argparse
import csv
from datetime import datetime
from collections import OrderedDict
from urllib.parse import urlparse, parse_qs

# 关闭 DecompressionBombWarning 警告
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0'
headers = {'User-Agent': UA}

# ------------------ booru 辅助函数 ------------------
def get_danbooru_source(danbooru_id, danbooru_username, danbooru_api_key):
    """通过 Danbooru 获取 source 链接"""
    url = f'https://danbooru.donmai.us/posts/{danbooru_id}.json'
    resp = requests.get(url, auth=(danbooru_username, danbooru_api_key), timeout=20)
    for i in resp.json()['media_asset']['variants']:
        if i['type'] == 'original':
            danbooru_original_url = i['url']
    x_website = ''
    if "twitter.com" in resp.json().get('source', '') or "x.com" in resp.json().get('source', ''):
        x_website = resp.json().get('source', '')
    return resp.json()['pixiv_id'], x_website, resp.json()['parent_id'], resp.json()['has_active_children'], danbooru_original_url


# ------------------ 解析搜索结果 ------------------
def parse_result_urls(results_urls_pool):
    """解析 SauceNao 返回的结果链接，提取 pixiv_id / twitter / gelbooru / danbooru"""
    pixiv_results = set()
    gelbooru_results = set()
    danbooru_results = set()
    twitter_results = set()

    for url in results_urls_pool:
        parsed = urlparse(url)

        # Pixiv
        if "pixiv.net" in parsed.netloc:
            query = parse_qs(parsed.query)
            if "illust_id" in query:
                pixiv_results.add(query["illust_id"][0])

        # Twitter / X
        elif "twitter.com" in parsed.netloc or "x.com" in parsed.netloc:
            twitter_results.add(url)

        # Danbooru
        elif "danbooru.donmai.us" in parsed.netloc:
            danbooru_results.add(parsed.path.split("/")[-1])

    return list(pixiv_results), list(twitter_results), list(danbooru_results), list(gelbooru_results)


# ------------------ 保存为 CSV ------------------
def save_csv(pixiv_data, twitter_data, danbooru_data, danbooru_info, timestamp, folder):
    """保存结果为 CSV 文件，包含原文件名"""
    # Pixiv
    pixiv_file = os.path.join(folder, f"pixiv_id.csv")
    with open(pixiv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "url", "original_filename"])  # 新增原文件名列
        for pid, filename in pixiv_data:
            writer.writerow([pid, f"https://www.pixiv.net/artworks/{pid}", filename])
    print(f"[INFO] 已保存 Pixiv ID 至 {pixiv_file}")

    # Twitter
    twitter_file = os.path.join(folder, f"twitter_url.csv")
    with open(twitter_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "original_filename"])  # 新增原文件名列
        for url, filename in twitter_data:
            writer.writerow([url, filename])
    print(f"[INFO] 已保存 Twitter URL 至 {twitter_file}")

    # Danbooru
    danbooru_file = os.path.join(folder, f"danbooru_id.csv")
    with open(danbooru_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "url", "original_url", "parent_id", "has_active_children", "original_filename"])  # 新增原文件名列
        for did, filename in danbooru_data:
            # 从字典中获取当前 did 对应的属性，默认空字符串
            info = danbooru_info.get(did, {})
            writer.writerow([
                did, 
                f"https://danbooru.donmai.us/posts/{did}", 
                info.get("original_url", ""),
                info.get("parent_id", ""),
                info.get("has_active_children", ""),
                filename  # 添加原文件名
            ])
    print(f"[INFO] 已保存 Danbooru ID 至 {danbooru_file}")


# ------------------ SauceNao 搜索函数 ------------------
def search_with_saucenao(folder, api_key, similarity, sleep_time, numbers, minsim, save_path, danbooru_username, danbooru_api_key, proxy_port):
    """批量搜索文件夹中的图片"""
    # 设置代理
    os.environ["http_proxy"] = f'http://127.0.0.1:{proxy_port}'
    os.environ["https_proxy"] = f'http://127.0.0.1:{proxy_port}'

    results_all = []
    files = [f for f in os.scandir(folder) if f.is_file() and f.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]

    # 改为存储 (ID/URL, 原文件名) 的元组
    all_pixiv = set()
    all_twitter = set()
    all_danbooru = set()
    danbooru_info = {}

    for count, file in enumerate(files, 1):
        print(f"\n[INFO] 正在搜索第 {count} 张图片: {file.name}")
        results_urls_pool = []

        try:
            with open(file.path, "rb") as f:
                resp = requests.post(
                    f"http://saucenao.com/search.php?output_type=2&numres={numbers}&minsim={minsim}&dbmask=999&api_key={api_key}",
                    files={"file": f},
                    headers=headers,
                    timeout=20
                )
        except Exception as e:
            print(f"[ERROR] 请求失败: {e}")
            continue

        if resp.status_code != 200:
            print(f"[ERROR] 状态码异常: {resp.status_code}")
            time.sleep(10)
            continue

        try:
            search_results = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(resp.text)
            for i in search_results.get("results", []):
                if float(i["header"]["similarity"]) >= similarity and "ext_urls" in i["data"]:
                    results_urls_pool.extend(i["data"]["ext_urls"])
                if "source" in i["data"]:
                    results_urls_pool.append(i["data"]["source"])
        except Exception as e:
            print(f"[ERROR] JSON 解析失败: {e}")
            continue

        pixiv, twitter, danbooru, gelbooru = parse_result_urls(results_urls_pool)

        # 累积结果，关联原文件名
        for pid in pixiv:
            all_pixiv.add((pid, file.name))
        for url in twitter:
            all_twitter.add((url, file.name))
        for did in danbooru:
            all_danbooru.add((did, file.name))

        if danbooru_username and danbooru_api_key:
            # 使用 Danbooru API 补充信息
            for did, _ in all_danbooru:  # 只需要 ID 部分
                pixiv_id, x_website, parent_id, has_active_children, original_url = get_danbooru_source(did, danbooru_username, danbooru_api_key)
                if pixiv_id:
                    all_pixiv.add((str(pixiv_id), file.name))
                if x_website:
                    all_twitter.add((x_website, file.name))
                # 存储当前 did 对应的属性
                danbooru_info[did] = {
                    "parent_id": parent_id,
                    "has_active_children": has_active_children,
                    "original_url": original_url
                }
        else:
            print("[INFO] 未提供Danbooru凭证，跳过补充信息")

        # 移除无效值
        all_pixiv = {(pid, fn) for pid, fn in all_pixiv if pid not in (None, '')}
        all_twitter = {(url, fn) for url, fn in all_twitter if url not in (None, '')}
        
        # Json文件保存
        result_entry = {
            "file": file.name,
            "pixiv_ids": pixiv,
            "twitter_urls": twitter,
            "danbooru_ids": danbooru,
            "gelbooru_ids": gelbooru
        }
        results_all.append(result_entry)

        print(json.dumps(result_entry, ensure_ascii=False, indent=2))

        if count < len(files):
            print(f"[INFO] 等待 {sleep_time} 秒后继续...")
            time.sleep(sleep_time)

        # 判断结果是否为空，移动文件
        no_results_dir = os.path.join(folder, "no_results")
        complete_dir = os.path.join(folder, "search_complete")
        os.makedirs(no_results_dir, exist_ok=True)
        os.makedirs(complete_dir, exist_ok=True)

        if not pixiv and not twitter and not danbooru:
            dest = os.path.join(no_results_dir, file.name)
            os.replace(file.path, dest)
            print(f"[INFO] 无结果，已移动到 {dest}")
        else:
            dest = os.path.join(complete_dir, file.name)
            os.replace(file.path, dest)
            print(f"[INFO] 已完成，文件移动到 {dest}")


    # 生成日期文件夹
    date_folder = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    os.makedirs(date_folder, exist_ok=True)

    # 保存 JSON
    if save_path:
        save_json_path = os.path.join(date_folder, save_path)
        with open(save_json_path, "w", encoding="utf-8") as f:
            json.dump(results_all, f, ensure_ascii=False, indent=2)
        print(f"\n[INFO] 搜索结果已保存至 {save_json_path}")
    else:
        print("[INFO] 未指定 --save 参数，不保存 JSON 文件")

    # 保存 CSV
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    save_csv(list(all_pixiv), list(all_twitter), list(all_danbooru), danbooru_info, timestamp, date_folder)

    return results_all


# ------------------ 主入口 (命令行) ------------------
def main():
    parser = argparse.ArgumentParser(description="SauceNao 图片批量搜索工具")
    parser.add_argument("folder", help="待搜索图片文件夹路径")
    parser.add_argument("--api_key", required=True, help="SauceNao API Key")
    parser.add_argument("--similarity", type=float, default=70.0, help="最低相似度 (默认70)")
    parser.add_argument("--sleep", type=int, default=10, help="请求间隔秒数 (默认10)")
    parser.add_argument("--num", type=int, default=5, help="返回的结果数量 (默认5)")
    parser.add_argument("--minsim", type=int, default=80, help="SauceNao minsim 参数 (默认80)")
    parser.add_argument("--save", default=None, help="JSON 结果保存路径 (默认不保存，输入文件名可保存)")
    parser.add_argument("--danbooru_username", default=None, help="Danbooru 用户名")
    parser.add_argument("--danbooru_api_key", default=None, help="Danbooru API Key")
    parser.add_argument("--proxy_port", type=int, default=7890, help="代理端口 (默认7890)")
    args = parser.parse_args()

    search_with_saucenao(
        folder=args.folder,
        api_key=args.api_key,
        similarity=args.similarity,
        sleep_time=args.sleep,
        numbers=args.num,
        minsim=args.minsim,
        save_path=args.save,
        danbooru_username=args.danbooru_username,
        danbooru_api_key=args.danbooru_api_key,
        proxy_port=args.proxy_port
    )


if __name__ == "__main__":
    main()
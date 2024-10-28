import json
import sys
import traceback
import fnmatch
import requests
import time
import hmac
import hashlib
import base64
import urllib.parse
import asyncio
import aiohttp
import re
import os
from quark_auto_save import Quark
from check_quark_links import print_bordered_table

# 钉钉通知配置
ACCESS_TOKEN = ""
SECRET = ""

def load_gitignore(gitignore_path='.gitignore'):
    try:
        with open(gitignore_path, 'r') as file:
            return [line.strip() for line in file if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print(f"警告: 未找到 .gitignore 文件: {gitignore_path}")
        return []

def is_ignored(filename, ignore_patterns):
    return any(fnmatch.fnmatch(filename, pattern) for pattern in ignore_patterns)

async def check_directory_content(quark, session, pwd_id, stoken, fid="", ignore_patterns=None):
    if ignore_patterns is None:
        ignore_patterns = []
    
    share_file_list = await quark.get_detail(session, pwd_id, stoken, fid)
    
    if share_file_list is None:
        return None
    
    for item in share_file_list:
        if item.get('file') is True:
            if not is_ignored(item.get('file_name', ''), ignore_patterns):
                return True
        elif item.get('dir') is True:
            result = await check_directory_content(quark, session, pwd_id, stoken, item['fid'], ignore_patterns)
            if result is True:
                return True
    
    return False

def generate_sign():
    timestamp = str(round(time.time() * 1000))
    secret_enc = SECRET.encode('utf-8')
    string_to_sign = f'{timestamp}\n{SECRET}'
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign

def send_dingtalk_notification(message):
    if not ACCESS_TOKEN or not SECRET:
        print("钉钉通知未配置，跳过通知")
        return
        
    timestamp, sign = generate_sign()
    webhook_url = f"https://oapi.dingtalk.com/robot/send?access_token={ACCESS_TOKEN}&timestamp={timestamp}&sign={sign}"
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "msgtype": "text",
        "text": {
            "content": message
        },
        "at": {
            "isAtAll": False
        }
    }
    
    response = requests.post(webhook_url, headers=headers, json=data)
    print(f"钉钉通知发送状态: {response.status_code}")
    print(f"钉钉通知响应: {response.text}")
    
async def check_movie_links(config_file):
    try:
        # 构建正确的文件路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        report_path = os.path.join(base_dir, 'auto', 'report.log')
        print(f"尝试读取文件: {report_path}")
        
        # 加载 .gitignore 规则
        ignore_patterns = load_gitignore()

        # 读取配置文件
        with open(config_file, 'r', encoding='utf-8') as file:
            config_data = json.load(file)

        # 获取cookie
        cookie = config_data.get('cookie', [])[0] if config_data.get('cookie') else None
        if not cookie:
            print("错误: 配置文件中没有找到 cookie。", file=sys.stderr)
            return 1

        async with aiohttp.ClientSession() as session:
            # 创建Quark对象
            quark = Quark(cookie, 0)
            
            # 验证账号
            if not await quark.init(session):
                print("错误: 账号验证失败，请检查cookie是否有效。", file=sys.stderr)
                return 1

            print(f"账号验证成功: {quark.nickname}")

            # 读取report.log文件
            try:
                with open(report_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                print(f"成功读取文件，内容长度: {len(content)} 字符")
            except FileNotFoundError:
                print(f"错误: 找不到文件 {report_path}", file=sys.stderr)
                return 1

            # 解析影片信息
            movie_info = []
            current_movie = None
            start_parsing = False
            
            for line in content.split('\n'):
                line = line.strip()
                
                # 开始标记
                if line == "影片名称及其对应的网盘链接和豆瓣链接:":
                    start_parsing = True
                    continue
                    
                if not start_parsing:
                    continue
                
                # 匹配影片名称
                if line.startswith('影片名称:'):
                    if current_movie and 'url' in current_movie:
                        movie_info.append(current_movie)
                    movie_name = line[5:].strip()
                    current_movie = {'name': movie_name}
                    print(f"找到影片: {movie_name}")
                
                # 匹配夸克网盘链接
                elif '夸克网盘链接:' in line:
                    if current_movie:
                        url = line.split('夸克网盘链接:')[1].strip()
                        current_movie['url'] = url
                        print(f"找到链接: {url}")

            # 添加最后一个影片
            if current_movie and 'url' in current_movie:
                movie_info.append(current_movie)

            print(f"\n总共找到 {len(movie_info)} 个影片信息")
            for movie in movie_info:
                print(f"影片: {movie['name']} - {movie['url']}")

            invalid_links = []
            valid_links = []
            empty_links = []

            # 检查每个链接
            for movie in movie_info:
                movie_name = movie['name']
                shareurl = movie['url']
                
                print(f"正在检查: {movie_name}")
                pwd_id, _ = quark.get_id_from_url(shareurl)
                is_valid, stoken = await quark.get_stoken(session, pwd_id)

                if is_valid:
                    content_check = await check_directory_content(quark, session, pwd_id, stoken, ignore_patterns=ignore_patterns)
                    if content_check is None:
                        print(f"链接无效: {movie_name} - 无法获取内容")
                        invalid_links.append((movie_name, shareurl))
                    elif content_check:
                        print(f"链接有效且包含非忽略文件: {movie_name}")
                        valid_links.append((movie_name, shareurl))
                    else:
                        print(f"链接有效但仅包含被忽略的文件: {movie_name}")
                        empty_links.append((movie_name, shareurl))
                else:
                    print(f"链接无效: {movie_name} - {stoken}")
                    invalid_links.append((movie_name, shareurl))

            # 将结果写入日志文件
            log_file_path = 'movie_check_result.log'
            with open(log_file_path, 'w', encoding='utf-8') as log_file:
                # 写入有效链接
                for movie_name, url in valid_links:
                    log_file.write(f"{movie_name}={url}=有效\n")
                
                # 写入无效链接
                for movie_name, url in invalid_links:
                    log_file.write(f"{movie_name}={url}=无效\n")
                    
                # 写入被屏蔽链接
                for movie_name, url in empty_links:
                    log_file.write(f"{movie_name}={url}=被屏蔽\n")

            # 打印汇总结果
            print("\n检查结果汇总:")
            
            if invalid_links:
                print_bordered_table("无效链接", invalid_links, ["电影名称", "无效URL"])
            if empty_links:
                print_bordered_table("仅包含被忽略文件的链接", empty_links, ["电影名称", "URL"])
            if valid_links:
                print_bordered_table("有效非空链接", valid_links, ["电影名称", "有效URL"])
            
            total_checked = len(valid_links) + len(empty_links) + len(invalid_links)
            print(f"\n总计检查了 {len(movie_info)} 个链接，其中 {len(valid_links)} 个有效且包含非忽略文件，{len(empty_links)} 个仅包含被忽略文件，{len(invalid_links)} 个无效。")

            # 生成简化的JSON结果
            result = {
                "valid": [{"movie_name": m, "url": u} for m, u in valid_links],
                "empty": [{"movie_name": m, "url": u} for m, u in empty_links],
                "invalid": [{"movie_name": m, "url": u} for m, u in invalid_links]
            }
            
            # 保存JSON结果
            with open('movie_check_result.json', 'w', encoding='utf-8') as file:
                json.dump(result, file, ensure_ascii=False, indent=2)

            # 发送钉钉通知
            if invalid_links or empty_links:
                message = "夸克网盘链接有效性检测\n\n"
                if invalid_links:
                    message += "无效链接:\n"
                    for name, url in invalid_links:
                        message += f" 《{name}》: {url}\n"
                if empty_links:
                    message += "\n被屏蔽的链接:\n"
                    for name, url in empty_links:
                        message += f" 《{name}》: {url}\n"
                send_dingtalk_notification(message)

        return 0
    except Exception as e:
        print(f"发生错误: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python3 check_movie_links.py <配置文件路径>", file=sys.stderr)
        sys.exit(1)
    
    config_file = sys.argv[1]
    asyncio.run(check_movie_links(config_file))
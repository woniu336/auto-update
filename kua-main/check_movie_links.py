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

def check_directory_content(quark, pwd_id, stoken, fid="", ignore_patterns=None):
    if ignore_patterns is None:
        ignore_patterns = []
    
    share_file_list = quark.get_detail(pwd_id, stoken, fid)
    
    if share_file_list is None:
        return None
    
    for item in share_file_list:
        if item.get('file') is True:
            if not is_ignored(item.get('file_name', ''), ignore_patterns):
                return True
        elif item.get('dir') is True:
            result = check_directory_content(quark, pwd_id, stoken, item['fid'], ignore_patterns)
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

def check_movie_links(config_file, movie_links_file):
    try:
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

        # 创建Quark对象
        quark = Quark(cookie, 0)

        # 验证账号
        if not quark.init():
            print("错误: 账号验证失败，请检查cookie是否有效。", file=sys.stderr)
            return 1

        print(f"账号验证成功: {quark.nickname}")

        # 读取电影链接文件
        with open(movie_links_file, 'r', encoding='utf-8') as file:
            movie_links = file.readlines()

        invalid_links = []
        valid_links = []
        empty_links = []

        for line in movie_links:
            parts = line.strip().split('@')
            if len(parts) != 2:
                print(f"警告: 忽略格式不正确的行: {line.strip()}")
                continue
            
            movie_name, shareurl = parts

            print(f"正在检查: {movie_name}")
            pwd_id, _ = quark.get_id_from_url(shareurl)
            is_valid, stoken = quark.get_stoken(pwd_id)

            if is_valid:
                content_check = check_directory_content(quark, pwd_id, stoken, ignore_patterns=ignore_patterns)
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

        # 打印汇总结果
        print("\n检查结果汇总:")
        
        if invalid_links:
            print_bordered_table("无效链接", invalid_links, ["电影名称", "无效URL"])
        if empty_links:
            print_bordered_table("仅包含被忽略文件的链接", empty_links, ["电影名称", "URL"])
        if valid_links:
            print_bordered_table("有效非空链接", valid_links, ["电影名称", "有效URL"])
        
        print(f"\n总计检查了 {len(movie_links)} 个链接，其中 {len(valid_links)} 个有效且包含非忽略文件，{len(empty_links)} 个仅包含被忽略文件，{len(invalid_links)} 个无效。")

        # 更新链接文件
        with open(movie_links_file, 'w', encoding='utf-8') as file:
            for movie_name, shareurl in valid_links + empty_links + invalid_links:
                file.write(f"{movie_name}@{shareurl}\n")

        # 生成JSON结果
        result = {
            "valid": [{"movie_name": m, "url": u} for m, u in valid_links],
            "empty": [{"movie_name": m, "url": u} for m, u in empty_links],
            "invalid": [{"movie_name": m, "url": u} for m, u in invalid_links]
        }
        
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
    if len(sys.argv) < 3:
        print("使用方法: python3 check_movie_links.py <配置文件路径> <电影链接文件路径>", file=sys.stderr)
        sys.exit(1)
    
    config_file = sys.argv[1]
    movie_links_file = sys.argv[2]
    sys.exit(check_movie_links(config_file, movie_links_file))

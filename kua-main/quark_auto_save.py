#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Modify: 2024-04-03
# Repo: https://github.com/Cp0204/quark_auto_save
# ConfigFile: quark_config.json

import os
import re
import sys
import json
import time
import random
import asyncio
import aiohttp
import logging
from datetime import datetime
from functools import lru_cache

# 兼容青龙
try:
    from treelib import Tree
except ImportError:
    os.system("pip3 install treelib aiohttp &> /dev/null")
    from treelib import Tree

CONFIG_DATA = {}
NOTIFYS = []
GH_PROXY = os.environ.get("GH_PROXY", "https://ghproxy.net/")

MAGIC_REGEX = {
    "$TV": {
        "pattern": ".*?(S\\d{1,2}E)?P?(\\d{1,3}).*?\\.(mpmkv)",
        "replace": "\\1\\2.\\3",
    },
}

# 设置日志配置
logging.basicConfig(
    filename='quark_save.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def fetch(session, method, url, **kwargs):
    try:
        async with session.request(method, url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()
    except Exception as e:
        logging.error(f"请求失败: {method} {url} - {e}")
        return None

def magic_regex_func(pattern, replace):
    keyword = pattern
    if keyword in CONFIG_DATA["magic_regex"]:
        pattern = CONFIG_DATA["magic_regex"][keyword]["pattern"]
        if replace == "":
            replace = CONFIG_DATA["magic_regex"][keyword]["replace"]
    return pattern, replace

async def send_ql_notify(title, body):
    try:
        import notify
        if CONFIG_DATA.get("push_config"):
            CONFIG_DATA["push_config"]["CONSOLE"] = True
            notify.push_config = CONFIG_DATA["push_config"]
        await notify.send(title, body)
    except Exception as e:
        logging.error(f"发送通知消息失败: {e}")

def add_notify(text):
    global NOTIFYS
    NOTIFYS.append(text)
    logging.info(text)
    return text

def download_file_sync(url, save_path):
    try:
        import requests
        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, "wb") as file:
                file.write(response.content)
            return True
        else:
            logging.error(f"下载文件失败: {url} - 状态码 {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"下载文件异常: {url} - {e}")
        return False

def get_cookies(cookie_val):
    if isinstance(cookie_val, list):
        return cookie_val
    elif cookie_val:
        if "\n" in cookie_val:
            return cookie_val.split("\n")
        else:
            return [cookie_val]
    else:
        return False

class Quark:
    def __init__(self, cookie, index=None):
        self.cookie = cookie.strip()
        self.index = index + 1
        self.is_active = False
        self.nickname = ""
        self.st = self.match_st_form_cookie(cookie)
        self.mparam = self.match_mparam_form_cookie(cookie)
        self.savepath_fid = {"/": "0"}

    def match_st_form_cookie(self, cookie):
        match = re.search(r"=(st[a-zA-Z0-9]+);", cookie)
        return match.group(1) if match else False

    def match_mparam_form_cookie(self, cookie):
        mparam = {}
        kps_match = re.search(r"(?<!\w)kps=([a-zA-Z0-9%]+)[;&]?", cookie)
        sign_match = re.search(r"(?<!\w)sign=([a-zA-Z0-9%]+)[;&]?", cookie)
        vcode_match = re.search(r"(?<!\w)vcode=([a-zA-Z0-9%]+)[;&]?", cookie)
        if kps_match and sign_match and vcode_match:
            mparam = {
                "kps": kps_match.group(1).replace("%25", "%"),
                "sign": sign_match.group(1).replace("%25", "%"),
                "vcode": vcode_match.group(1).replace("%25", "%"),
            }
        return mparam

    def common_headers(self):
        headers = {
            "cookie": self.cookie,
            "content-type": "application/json",
        }
        if self.st:
            headers["x-clouddrive-st"] = self.st
        return headers

    async def init(self, session):
        account_info = await self.get_account_info(session)
        if account_info:
            self.is_active = True
            self.nickname = account_info["nickname"]
            return account_info
        else:
            return False

    async def get_account_info(self, session):
        url = "https://pan.quark.cn/account/info"
        querystring = {"fr": "pc", "platform": "pc"}
        headers = self.common_headers()
        response = await fetch(session, "GET", url, headers=headers, params=querystring)
        if response and response.get("data"):
            return response["data"]
        else:
            return False

    async def get_growth_info(self, session):
        url = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info"
        querystring = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.mparam.get("kps"),
            "sign": self.mparam.get("sign"),
            "vcode": self.mparam.get("vcode"),
        }
        headers = {
            "content-type": "application/json",
        }
        response = await fetch(session, "GET", url, headers=headers, params=querystring)
        if response and response.get("data"):
            return response["data"]
        else:
            return False

    async def get_growth_sign(self, session):
        url = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/sign"
        querystring = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.mparam.get("kps"),
            "sign": self.mparam.get("sign"),
            "vcode": self.mparam.get("vcode"),
        }
        payload = {
            "sign_cyclic": True,
        }
        headers = {
            "content-type": "application/json",
        }
        response = await fetch(session, "POST", url, json=payload, headers=headers, params=querystring)
        if response and response.get("data"):
            return True, response["data"]["sign_daily_reward"]
        elif response:
            return False, response["message"]
        else:
            return False, "未知错误"

    def get_id_from_url(self, url):
        url = url.replace("https://pan.quark.cn/s/", "")
        pattern = r"(\w+)(#/list/share.*/(\w+))?"
        match = re.search(pattern, url)
        if match:
            pwd_id = match.group(1)
            if match.group(2):
                pdir_fid = match.group(3)
            else:
                pdir_fid = 0
            return pwd_id, pdir_fid
        else:
            return None

    async def get_stoken(self, session, pwd_id):
        url = "https://drive-m.quark.cn/1/clouddrive/share/sharepage/token"
        querystring = {"pr": "ucpro", "fr": "h5"}
        payload = {"pwd_id": pwd_id, "passcode": ""}
        headers = self.common_headers()
        response = await fetch(session, "POST", url, json=payload, headers=headers, params=querystring)
        if response and response.get("data"):
            return True, response["data"]["stoken"]
        elif response:
            return False, response["message"]
        else:
            return False, "未知错误"

    async def get_detail(self, session, pwd_id, stoken, pdir_fid):
        file_list = []
        page = 1
        while True:
            url = "https://drive-m.quark.cn/1/clouddrive/share/sharepage/detail"
            querystring = {
                "pr": "ucpro",
                "fr": "pc",
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": pdir_fid,
                "force": "0",
                "_page": page,
                "_size": "50",
                "_fetch_banner": "0",
                "_fetch_share": "0",
                "_fetch_total": "1",
                "_sort": "file_type:asc,updated_at:desc",
            }
            headers = self.common_headers()
            response = await fetch(session, "GET", url, headers=headers, params=querystring)
            if response and response["data"]["list"]:
                file_list += response["data"]["list"]
                page += 1
            else:
                break
            if len(file_list) >= response["metadata"]["_total"]:
                break
        return file_list

    @lru_cache(maxsize=128)
    async def get_fids(self, session, file_paths):
        fids = []
        while file_paths:
            batch = file_paths[:50]
            file_paths = file_paths[50:]
            url = "https://drive-m.quark.cn/1/clouddrive/file/info/path_list"
            querystring = {"pr": "ucpro", "fr": "pc"}
            payload = {"file_path": batch, "namespace": "0"}
            headers = self.common_headers()
            response = await fetch(session, "POST", url, json=payload, headers=headers, params=querystring)
            if response and response["code"] == 0:
                fids += response["data"]
            else:
                logging.error(f"获取目录ID失败: {response['message'] if response else '无响应'}")
                break
        return fids

    async def ls_dir(self, session, pdir_fid):
        file_list = []
        page = 1
        while True:
            url = "https://drive-m.quark.cn/1/clouddrive/file/sort"
            querystring = {
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "pdir_fid": pdir_fid,
                "_page": page,
                "_size": "50",
                "_fetch_total": "1",
                "_fetch_sub_dirs": "0",
                "_sort": "file_type:asc,updated_at:desc",
            }
            headers = self.common_headers()
            response = await fetch(session, "GET", url, headers=headers, params=querystring)
            if response and response["data"]["list"]:
                file_list += response["data"]["list"]
                page += 1
            else:
                break
            if len(file_list) >= response["metadata"]["_total"]:
                break
        return file_list

    async def save_file(self, session, fid_list, fid_token_list, to_pdir_fid, pwd_id, stoken):
        url = "https://drive-m.quark.cn/1/clouddrive/share/sharepage/save"
        querystring = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "app": "clouddrive",
            "__dt": int(random.uniform(1, 5) * 60 * 1000),
            "__t": datetime.now().timestamp(),
        }
        querystring["fr"] = "h5" if self.st else "pc"
        payload = {
            "fid_list": fid_list,
            "fid_token_list": fid_token_list,
            "to_pdir_fid": to_pdir_fid,
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": "0",
            "scene": "link",
        }
        headers = self.common_headers()
        response = await fetch(session, "POST", url, json=payload, headers=headers, params=querystring)
        return response

    async def mkdir(self, session, dir_path):
        url = "https://drive-m.quark.cn/1/clouddrive/file"
        querystring = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {
            "pdir_fid": "0",
            "file_name": "",
            "dir_path": dir_path,
            "dir_init_lock": False,
        }
        headers = self.common_headers()
        response = await fetch(session, "POST", url, json=payload, headers=headers, params=querystring)
        return response

    async def rename(self, session, fid, file_name):
        url = "https://drive-m.quark.cn/1/clouddrive/file/rename"
        querystring = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {"fid": fid, "file_name": file_name}
        headers = self.common_headers()
        response = await fetch(session, "POST", url, json=payload, headers=headers, params=querystring)
        return response

    async def delete(self, session, filelist):
        url = "https://drive-m.quark.cn/1/clouddrive/file/delete"
        querystring = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {"action_type": 2, "filelist": filelist, "exclude_fids": []}
        headers = self.common_headers()
        response = await fetch(session, "POST", url, json=payload, headers=headers, params=querystring)
        return response

    async def recycle_list(self, session, page=1, size=30):
        url = "https://drive-m.quark.cn/1/clouddrive/file/recycle/list"
        querystring = {
            "_page": page,
            "_size": size,
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
        }
        headers = self.common_headers()
        response = await fetch(session, "GET", url, headers=headers, params=querystring)
        if response:
            return response["data"]["list"]
        else:
            return []

    async def recycle_remove(self, session, record_list):
        url = "https://drive-m.quark.cn/1/clouddrive/file/recycle/remove"
        querystring = {"uc_param_str": "", "fr": "pc", "pr": "ucpro"}
        payload = {
            "select_mode": 2,
            "record_list": record_list,
        }
        headers = self.common_headers()
        response = await fetch(session, "POST", url, json=payload, headers=headers, params=querystring)
        return response

    async def update_savepath_fid(self, session, tasklist):
        dir_paths = [
            re.sub(r"/{2,}", "/", f"/{item['savepath']}")
            for item in tasklist
            if not item.get("enddate")
            or (
                datetime.now().date()
                <= datetime.strptime(item["enddate"], "%Y-%m-%d").date()
            )
        ]
        if not dir_paths:
            return False
        dir_paths_exist_arr = await self.get_fids(session, tuple(dir_paths))
        dir_paths_exist = [item["file_path"] for item in dir_paths_exist_arr]
        dir_paths_unexist = list(set(dir_paths) - set(dir_paths_exist) - set(["/"]))
        tasks = []
        for dir_path in dir_paths_unexist:
            tasks.append(self.mkdir(session, dir_path))
        mkdir_results = await asyncio.gather(*tasks)
        for dir_path, mkdir_return in zip(dir_paths_unexist, mkdir_results):
            if mkdir_return and mkdir_return.get("code") == 0:
                new_dir = mkdir_return["data"]
                dir_paths_exist_arr.append(
                    {"file_path": dir_path, "fid": new_dir["fid"]}
                )
                logging.info(f"创建文件夹：{dir_path}")
            else:
                logging.error(f"创建文件夹：{dir_path} 失败, {mkdir_return['message'] if mkdir_return else '无响应'}")
        # 储存目标目录的fid
        for dir_path in dir_paths_exist_arr:
            self.savepath_fid[dir_path["file_path"]] = dir_path["fid"]

    async def do_save_check(self, session, shareurl, savepath):
        try:
            pwd_id, pdir_fid = self.get_id_from_url(shareurl)
            is_sharing, stoken = await self.get_stoken(session, pwd_id)
            if not is_sharing:
                add_notify(f"❌：{stoken}\n")
                return False
            share_file_list = await self.get_detail(session, pwd_id, stoken, pdir_fid)
            fid_list = [item["fid"] for item in share_file_list]
            fid_token_list = [item["share_fid_token"] for item in share_file_list]
            file_name_list = [item["file_name"] for item in share_file_list]
            if not fid_list:
                return False
            get_fids = await self.get_fids(session, (savepath,))
            to_pdir_fid = (
                get_fids[0]["fid"] if get_fids else (await self.mkdir(session, savepath))["data"]["fid"]
            )
            save_file_return = await self.save_file(session, fid_list, fid_token_list, to_pdir_fid, pwd_id, stoken)
            if not save_file_return:
                return False
            if save_file_return["code"] == 41017:
                return False
            elif save_file_return["code"] == 0:
                dir_file_list = await self.ls_dir(session, to_pdir_fid)
                del_list = [
                    item["fid"]
                    for item in dir_file_list
                    if (item["file_name"] in file_name_list)
                    and ((datetime.now().timestamp() - item["created_at"]) < 60)
                ]
                if del_list:
                    await self.delete(session, del_list)
                    recycle_list = await self.recycle_list(session)
                    record_id_list = [
                        item["record_id"]
                        for item in recycle_list
                        if item["fid"] in del_list
                    ]
                    await self.recycle_remove(session, record_id_list)
                return save_file_return
            else:
                return False
        except Exception as e:
            if os.environ.get("DEBUG") == "True":
                logging.error(f"转存测试失败: {str(e)}")
            return False

    async def do_save_task(self, session, task):
        if task.get("shareurl_ban"):
            logging.info(f"《{task['taskname']}》：{task['shareurl_ban']}")
            return

        pwd_id, pdir_fid = self.get_id_from_url(task["shareurl"])
        is_sharing, stoken = await self.get_stoken(session, pwd_id)
        if not is_sharing:
            add_notify(f"❌《{task['taskname']}》：{stoken}\n")
            task["shareurl_ban"] = stoken
            return
        updated_tree = await self.dir_check_and_save(session, task, pwd_id, stoken, pdir_fid)
        if updated_tree.size(1) > 0:
            add_notify(f"✅《{task['taskname']}》添加追更：\n{updated_tree}")
            return True
        else:
            logging.info(f"任务结束：没有新的转存任务")
            return False

    async def dir_check_and_save(self, session, task, pwd_id, stoken, pdir_fid="", subdir_path=""):
        tree = Tree()
        tree.create_node(task["savepath"], pdir_fid)
        share_file_list = await self.get_detail(session, pwd_id, stoken, pdir_fid)

        if not share_file_list:
            if subdir_path == "":
                task["shareurl_ban"] = "分享为空，文件已被分享者删除"
                add_notify(f"《{task['taskname']}》：{task['shareurl_ban']}")
            return tree
        elif (
            len(share_file_list) == 1
            and share_file_list[0]["dir"]
            and subdir_path == ""
        ):
            logging.info("🧠 该分享是一个文件夹，读取文件夹内列表")
            share_file_list = await self.get_detail(session, pwd_id, stoken, share_file_list[0]["fid"])

        savepath = re.sub(r"/{2,}", "/", f"/{task['savepath']}{subdir_path}")
        if not self.savepath_fid.get(savepath):
            get_fids = await self.get_fids(session, (savepath,))
            if get_fids:
                self.savepath_fid[savepath] = get_fids[0]["fid"]
            else:
                logging.error(f"❌ 目录 {savepath} fid获取失败，跳过转存")
                return tree
        to_pdir_fid = self.savepath_fid[savepath]
        dir_file_list = await self.ls_dir(session, to_pdir_fid)

        need_save_list = []
        for share_file in share_file_list:
            if share_file["dir"] and task.get("update_subdir", False):
                pattern, replace = task["update_subdir"], ""
            else:
                pattern, replace = magic_regex_func(task["pattern"], task["replace"])
            if re.search(pattern, share_file["file_name"]):
                save_name = (
                    re.sub(pattern, replace, share_file["file_name"])
                    if replace != ""
                    else share_file["file_name"]
                )
                if task.get("ignore_extension") and not share_file["dir"]:
                    compare_func = lambda a, b1, b2: (
                        os.path.splitext(a)[0] == os.path.splitext(b1)[0]
                        or os.path.splitext(a)[0] == os.path.splitext(b2)[0]
                    )
                else:
                    compare_func = lambda a, b1, b2: (a == b1 or a == b2)
                file_exists = any(
                    compare_func(
                        dir_file["file_name"], share_file["file_name"], save_name
                    )
                    for dir_file in dir_file_list
                )
                if not file_exists:
                    share_file["save_name"] = save_name
                    need_save_list.append(share_file)
                elif share_file["dir"]:
                    if task.get("update_subdir", False):
                        logging.info(f"检查子文件夹：{savepath}/{share_file['file_name']}")
                        subdir_tree = await self.dir_check_and_save(
                            session,
                            task,
                            pwd_id,
                            stoken,
                            share_file["fid"],
                            f"{subdir_path}/{share_file['file_name']}",
                        )
                        if subdir_tree.size(1) > 0:
                            tree.create_node(
                                "📁" + share_file["file_name"],
                                share_file["fid"],
                                parent=pdir_fid,
                            )
                            tree.merge(share_file["fid"], subdir_tree, deep=False)
            if share_file["fid"] == task.get("startfid", ""):
                break

        fid_list = [item["fid"] for item in need_save_list]
        fid_token_list = [item["share_fid_token"] for item in need_save_list]
        save_name_list = [item["save_name"] for item in need_save_list]
        if fid_list:
            save_file_return = await self.save_file(session, fid_list, fid_token_list, to_pdir_fid, pwd_id, stoken)
            err_msg = None
            if save_file_return and save_file_return.get("code") == 0:
                task_id = save_file_return["data"]["task_id"]
                query_task_return = await self.query_task(session, task_id)
                if query_task_return and query_task_return.get("code") == 0:
                    save_name_list.sort()
                    for item in need_save_list:
                        icon = (
                            "📁"
                            if item["dir"] == True
                            else "🎞️" if item["obj_category"] == "video" else ""
                        )
                        tree.create_node(
                            f"{icon}{item['save_name']}", item["fid"], parent=pdir_fid
                        )
                else:
                    err_msg = query_task_return["message"] if query_task_return else "无响应"
            else:
                err_msg = save_file_return["message"] if save_file_return else "无响应"

            if err_msg:
                add_notify(f"❌《{task['taskname']}》转存失败：{err_msg}\n")
        return tree

    async def query_task(self, session, task_id):
        retry_index = 0
        while True:
            url = "https://drive-m.quark.cn/1/clouddrive/task"
            querystring = {
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "task_id": task_id,
                "retry_index": retry_index,
                "__dt": int(random.uniform(1, 5) * 60 * 1000),
                "__t": datetime.now().timestamp(),
            }
            headers = self.common_headers()
            response = await fetch(session, "GET", url, headers=headers, params=querystring)
            if response:
                if response["data"]["status"] != 0:
                    break
                else:
                    if retry_index == 0:
                        logging.info(f"正在等待[{response['data']['task_title']}]执行结果")
                    else:
                        logging.info(".")
                    retry_index += 1
                    await asyncio.sleep(0.5)
            else:
                break
        return response

    async def do_rename_task(self, session, task, subdir_path=""):
        pattern, replace = magic_regex_func(task["pattern"], task["replace"])
        if not pattern or not replace:
            return False
        savepath = re.sub(r"/{2,}", "/", f"/{task['savepath']}{subdir_path}")
        if not self.savepath_fid.get(savepath):
            fids = await self.get_fids(session, (savepath,))
            if fids:
                self.savepath_fid[savepath] = fids[0]["fid"]
            else:
                return False
        dir_file_list = await self.ls_dir(session, self.savepath_fid[savepath])
        dir_file_name_list = [item["file_name"] for item in dir_file_list]
        rename_tasks = []
        for dir_file in dir_file_list:
            if dir_file["dir"]:
                rename_tasks.append(self.do_rename_task(session, task, f"{subdir_path}/{dir_file['file_name']}"))
            if re.search(pattern, dir_file["file_name"]):
                save_name = (
                    re.sub(pattern, replace, dir_file["file_name"])
                    if replace != ""
                    else dir_file["file_name"]
                )
                if save_name != dir_file["file_name"] and (
                    save_name not in dir_file_name_list
                ):
                    rename_tasks.append(self.rename(session, dir_file["fid"], save_name))
        rename_results = await asyncio.gather(*rename_tasks)
        is_rename = any(rename_results)
        return is_rename

async def verify_account(session, account):
    logging.info(f"▶️ 验证第{account.index}个账号")
    if "__uid" not in account.cookie:
        logging.info(f"💡 不存在cookie必要参数，判断为仅签到")
        return False
    else:
        account_info = await account.init(session)
        if not account_info:
            add_notify(f"👤 第{account.index}个账号登录失败，cookie无效❌")
            return False
        else:
            logging.info(f"👤 账号昵称: {account_info['nickname']}✅")
            return True

def format_bytes(size_bytes: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {units[i]}"

async def do_sign(session, account):
    if not account.mparam:
        logging.info("⏭️ 移动端参数未设置，跳过签到")
        return
    growth_info = await account.get_growth_info(session)
    if growth_info:
        growth_message = f"💾 {'88VIP' if growth_info['88VIP'] else '普通用户'} 总空间：{format_bytes(growth_info['total_capacity'])}，签到累计获得：{format_bytes(growth_info['cap_composition'].get('sign_reward', 0))}"
        if growth_info["cap_sign"]["sign_daily"]:
            sign_message = f"📅 签到记录: 今日已签到+{int(growth_info['cap_sign']['sign_daily_reward']/1024/1024)}MB，连签进度({growth_info['cap_sign']['sign_progress']}/{growth_info['cap_sign']['sign_target']})✅"
            message = f"{sign_message}\n{growth_message}"
            logging.info(message)
        else:
            sign, sign_return = await account.get_growth_sign(session)
            if sign:
                sign_message = f"📅 执行签到: 今日签到+{int(sign_return/1024/1024)}MB，连签进度({growth_info['cap_sign']['sign_progress']+1}/{growth_info['cap_sign']['sign_target']})✅"
                message = f"{sign_message}\n{growth_message}"
                if (
                    CONFIG_DATA.get("push_config", {}).get("QUARK_SIGN_NOTIFY") == False
                    or os.environ.get("QUARK_SIGN_NOTIFY") == "false"
                ):
                    logging.info(message)
                else:
                    message = message.replace("今日", f"[{account.nickname}]今日")
                    add_notify(message)
            else:
                logging.error(f"📅 签到异常: {sign_return}")

async def do_save(session, account, tasklist=[]):
    emby = Emby(
        CONFIG_DATA.get("emby", {}).get("url", ""),
        CONFIG_DATA.get("emby", {}).get("apikey", ""),
    )
    logging.info(f"转存账号: {account.nickname}")
    await account.update_savepath_fid(session, tasklist)

    def check_date(task):
        return (
            (not task.get("enddate") or datetime.now().date() <= datetime.strptime(task["enddate"], "%Y-%m-%d").date())
            and (
                not task.get("runweek")
                or (datetime.today().weekday() + 1 in task.get("runweek"))
            )
        )

    tasks = []
    for index, task in enumerate(tasklist):
        if check_date(task):
            logging.info(f"#{index+1}------------------")
            logging.info(f"任务名称: {task['taskname']}")
            logging.info(f"分享链接: {task['shareurl']}")
            logging.info(f"目标目录: {task['savepath']}")
            logging.info(f"正则匹配: {task['pattern']}")
            logging.info(f"正则替换: {task['replace']}")
            if task.get("enddate"):
                logging.info(f"任务截止: {task['enddate']}")
            if task.get("emby_id"):
                logging.info(f"刷媒体库: {task['emby_id']}")
            if task.get("ignore_extension"):
                logging.info(f"忽略后缀: {task['ignore_extension']}")
            if task.get("update_subdir"):
                logging.info(f"更子目录: {task['update_subdir']}")
            is_new = await account.do_save_task(session, task)
            is_rename = await account.do_rename_task(session, task)
            if emby.is_active and (is_new or is_rename) and task.get("emby_id") != "0":
                if task.get("emby_id"):
                    await emby.refresh(session, task["emby_id"])
                else:
                    match_emby_id = await emby.search(session, task["taskname"])
                    if match_emby_id:
                        task["emby_id"] = match_emby_id
                        await emby.refresh(session, match_emby_id)
    logging.info("转存任务完成")

class Emby:
    def __init__(self, emby_url, emby_apikey):
        self.is_active = False
        if emby_url and emby_apikey:
            self.emby_url = emby_url
            self.emby_apikey = emby_apikey
            # 初始化时不进行请求，需要在异步环境中调用方法

    async def get_info(self, session):
        url = f"{self.emby_url}/emby/System/Info"
        headers = {"X-Emby-Token": self.emby_apikey}
        response = await fetch(session, "GET", url, headers=headers, params={})
        if response and "application/json" in response.get("Content-Type", ""):
            logging.info(
                f"Emby媒体库: {response.get('ServerName','')} v{response.get('Version','')}"
            )
            return True
        else:
            logging.error(f"Emby媒体库: 连接失败❌ {response.text if response else '无响应'}")
            return False

    async def refresh(self, session, emby_id):
        if emby_id:
            url = f"{self.emby_url}/emby/Items/{emby_id}/Refresh"
            headers = {"X-Emby-Token": self.emby_apikey}
            querystring = {
                "Recursive": "true",
                "MetadataRefreshMode": "FullRefresh",
                "ImageRefreshMode": "FullRefresh",
                "ReplaceAllMetadata": "false",
                "ReplaceAllImages": "false",
            }
            response = await fetch(session, "POST", url, headers=headers, params=querystring)
            if response and response.text == "":
                logging.info(f"🎞 刷新Emby媒体库：成功✅")
                return True
            else:
                logging.error(f"🎞 刷新Emby媒体库：{response.text if response else '无响应'}❌")
                return False

    async def search(self, session, media_name):
        if media_name:
            url = f"{self.emby_url}/emby/Items"
            headers = {"X-Emby-Token": self.emby_apikey}
            querystring = {
                "IncludeItemTypes": "Series",
                "StartIndex": 0,
                "SortBy": "SortName",
                "SortOrder": "Ascending",
                "ImageTypeLimit": 0,
                "Recursive": "true",
                "SearchTerm": media_name,
                "Limit": 10,
                "IncludeSearchTypes": "false",
            }
            response = await fetch(session, "GET", url, headers=headers, params=querystring)
            if response and "application/json" in response.get("Content-Type", ""):
                if response.get("Items"):
                    for item in response["Items"]:
                        if item["IsFolder"]:
                            logging.info(
                                f"🎞 《{item['Name']}》匹配到Emby媒体库ID：{item['Id']}"
                            )
                            return item["Id"]
            else:
                logging.error(f"🎞 搜索Emby媒体库：{response.text if response else '无响应'}❌")
        return False

async def main():
    global CONFIG_DATA
    start_time = datetime.now()
    logging.info("===============程序开始===============")
    logging.info(f"⏰ 执行时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    config_path = sys.argv[1] if len(sys.argv) > 1 else "quark_config.json"
    task_index = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None

    if not os.path.exists(config_path):
        if os.environ.get("QUARK_COOKIE"):
            logging.info(
                f"⚙️ 读取到 QUARK_COOKIE 环境变量，仅签到领空间。如需执行转存，请删除该环境变量后配置 {config_path} 文件"
            )
            cookie_val = os.environ.get("QUARK_COOKIE")
            cookie_form_file = False
        else:
            logging.info(f"⚙️ 配置文件 {config_path} 不存在❌，正远程从下载配置模版")
            config_url = f"{GH_PROXY}https://raw.githubusercontent.com/Cp0204/quark_auto_save/main/quark_config.json"
            if download_file_sync(config_url, config_path):
                logging.info("⚙️ 配置模版下载成功✅，请到程序目录中手动配置")
            return
    else:
        logging.info(f"⚙️ 正从 {config_path} 文件中读取配置")
        with open(config_path, "r", encoding="utf-8") as file:
            CONFIG_DATA = json.load(file)
        cookie_val = CONFIG_DATA.get("cookie")
        if not CONFIG_DATA.get("magic_regex"):
            CONFIG_DATA["magic_regex"] = MAGIC_REGEX
        cookie_form_file = True

    cookies = get_cookies(cookie_val)
    if not cookies:
        logging.error("❌ cookie 未配置")
        return

    async with aiohttp.ClientSession() as session:
        accounts = [Quark(cookie, index) for index, cookie in enumerate(cookies)]
        logging.info("===============验证账号===============")
        verify_tasks = [verify_account(session, account) for account in accounts]
        await asyncio.gather(*verify_tasks)
        logging.info("===============签到任务===============")
        sign_tasks = [do_sign(session, account) for account in accounts]
        await asyncio.gather(*sign_tasks)
        logging.info("===============转存任务===============")
        if accounts[0].is_active and cookie_form_file:
            tasklist = CONFIG_DATA.get("tasklist", [])
            if task_index is not None and 0 <= task_index < len(tasklist):
                await do_save(session, accounts[0], [tasklist[task_index]])
            else:
                await do_save(session, accounts[0], tasklist)
        logging.info("===============推送通知===============")
        if NOTIFYS:
            notify_body = "\n".join(NOTIFYS)
            await send_ql_notify("【夸克自动追更】", notify_body)
        if cookie_form_file:
            with open(config_path, "w", encoding="utf-8") as file:
                json.dump(CONFIG_DATA, file, ensure_ascii=False, indent=2)
    end_time = datetime.now()
    duration = end_time - start_time
    logging.info("===============程序结束===============")
    logging.info(f"😃 运行时长: {round(duration.total_seconds(), 2)}s")

if __name__ == "__main__":
    asyncio.run(main())
import requests
from bs4 import BeautifulSoup
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# 设置日志
logging.basicConfig(
    filename='scraping.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# 定义请求头以模拟真实浏览器，避免403错误
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' 
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/114.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Referer': 'https://ddys.pro/',
    'Connection': 'keep-alive'
}

# 定义重试策略：最多重试3次，每次等待5秒，针对特定异常进行重试
retry_strategy = (
    retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(5),
        retry=retry_if_exception_type((requests.Timeout, requests.HTTPError))
    )
)

@retry_strategy
def get_movie_links(page_url, session):
    """
    从影片展示页面获取所有影片的实际链接。
    """
    try:
        response = session.get(page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()  # 如果响应状态码不是200，将引发HTTPError
        soup = BeautifulSoup(response.text, 'html.parser')
        movie_links = []
        for container in soup.find_all('div', class_='post-box-container'):
            title_tag = container.find('h2', class_='post-box-title').find('a')
            if title_tag and 'href' in title_tag.attrs:
                movie_link = title_tag['href']
                movie_links.append(movie_link)
        logging.info(f"在页面 {page_url} 找到 {len(movie_links)} 个影片链接。")
        return movie_links
    except requests.Timeout:
        logging.error(f"请求超时：无法访问页面 {page_url}")
        raise
    except requests.HTTPError as http_err:
        logging.error(f"HTTP错误：无法访问页面 {page_url} - {http_err}")
        raise
    except Exception as e:
        logging.error(f"解析页面 {page_url} 时发生错误：{e}")
        return []

@retry_strategy
def extract_pan_links(movie_url, session):
    """
    从实际影片页面提取影片标题、网盘链接和豆瓣链接。
    """
    try:
        response = session.get(movie_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 检查页面是否为有效的影片页面，通过查找h1.post-title
        title_tag = soup.find('h1', class_='post-title')
        if not title_tag:
            logging.error(f"页面 {movie_url} 缺少影片标题，可能是无效页面。")
            return None, None, None, movie_url  # 标记为失败
        
        # 提取影片标题
        title = title_tag.text.strip() if title_tag else "未知标题"
        
        # 初始化网盘链接
        pan_links = {}
        
        # 使用更全面的搜索，遍历所有文本节点以查找网盘链接
        all_text = soup.get_text(separator='\n')
        
        # 定义网盘类型及其对应的正则表达式
        pan_patterns = {
            '夸克': r'https://pan\.quark\.cn/s/\w+',
            '百度': r'https://pan\.baidu\.com/s/[\w\-]+\?pwd=[\w\d]+',
            'uc': r'https://drive\.uc\.cn/s/\w+'
        }
        
        # 查找所有网盘链接
        for pan_type, pattern in pan_patterns.items():
            matches = re.findall(pattern, all_text)
            if matches:
                # 取第一个匹配的链接
                pan_links[pan_type] = matches[0]
        
        # 提取豆瓣链接
        douban_link = ""
        mod_div = soup.find('div', class_='mod')
        if mod_div:
            doulist_subj_div = mod_div.find('div', class_='v-overflowHidden doulist-subject')
            if doulist_subj_div:
                title_div = doulist_subj_div.find('div', class_='title')
                a_tag = title_div.find('a', href=re.compile(r'https://movie\.douban\.com/subject/\d+')) if title_div else None
                if a_tag and 'href' in a_tag.attrs:
                    douban_link = a_tag['href'].strip()
        
        # 日志记录
        if douban_link:
            logging.info(f"已提取影片《{title}》的网盘链接和豆瓣链接。")
        else:
            logging.info(f"已提取影片《{title}》的网盘链接，没有找到豆瓣链接。")
        
        return title, pan_links, douban_link, None  # 正常返回，无错误
    except requests.Timeout:
        logging.error(f"请求超时：无法访问影片页面 {movie_url}")
        return None, None, None, movie_url  # 标记为失败
    except requests.HTTPError as http_err:
        logging.error(f"HTTP错误：无法访问影片页面 {movie_url} - {http_err}")
        return None, None, None, movie_url  # 标记为失败
    except Exception as e:
        logging.error(f"解析影片页面 {movie_url} 时发生错误：{e}")
        return None, None, None, movie_url  # 标记为失败

def process_movie(movie_url, session):
    """
    处理单个影片的爬取任务。
    """
    return extract_pan_links(movie_url, session)

def main():
    base_url = "https://ddys.pro/page/{}/"
    start_page = 1
    max_pages = 1  # 设置要爬取的最大页面数
    all_movies = []
    no_pan_movies = []
    failed_pages = []
    
    # 使用Session保持连接，提高效率
    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=5) as executor:
            for page in range(start_page, start_page + max_pages):
                page_url = base_url.format(page)
                try:
                    movie_links = get_movie_links(page_url, session)
                except Exception as e:
                    logging.error(f"页面 {page_url} 经过重试仍无法访问，跳过此页面。")
                    continue  # 跳过此页面
                
                if not movie_links:
                    logging.info(f"页面 {page_url} 没有找到任何影片链接，继续下一个页面。")
                    continue  # 继续下一个页面
                
                # 提交所有影片爬取任务
                futures = {executor.submit(process_movie, link, session): link for link in movie_links}
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            title, pan_links, douban_link, failed_url = result
                            if failed_url:
                                failed_pages.append(failed_url)
                            elif title:
                                all_movies.append((title, pan_links, douban_link))
                                if not pan_links:
                                    no_pan_movies.append(title)
                    except Exception as e:
                        movie_url = futures[future]
                        logging.error(f"处理影片 {movie_url} 时发生异常：{e}")
                        failed_pages.append(movie_url)
                
                logging.info(f"已完成页面 {page} 的爬取，等待10秒后继续。")
                time.sleep(10)  # 每个页面间隔10秒
    
    # 生成报告
    try:
        with open('report.log', 'w', encoding='utf-8') as f:
            # 写入无法访问的影片页面列表
            if failed_pages:
                f.write("无法访问的影片页面列表（404或其他错误）:\n")
                for failed_page in failed_pages:
                    f.write(f"- {failed_page}\n")
                f.write("\n")
            else:
                f.write("没有无法访问的影片页面。\n\n")
            
            # 写入总影片数量
            f.write(f"总影片数量: {len(all_movies)}\n")
            # 写入没有包含网盘信息的影片数量
            f.write(f"没有包含网盘信息的影片数量: {len(no_pan_movies)}\n\n")
            # 写入没有包含网盘信息的影片列表
            if no_pan_movies:
                f.write("没有包含网盘信息的影片列表:\n")
                for movie in no_pan_movies:
                    f.write(f"- {movie}\n")
                f.write("\n")
            
            # 写入每个影片的名称、网盘链接和豆瓣链接
            f.write("影片名称及其对应的网盘链接和豆瓣链接:\n")
            for title, links, douban_link in all_movies:
                f.write(f"影片名称: {title}\n")
                if links:
                    for pan, link in links.items():
                        f.write(f"  {pan}网盘链接: {link}\n")
                else:
                    f.write("  无网盘链接\n")
                
                if douban_link:
                    f.write(f"  豆瓣链接: {douban_link}\n")
                else:
                    f.write("  无豆瓣链接\n")
                
                f.write("\n")
        logging.info("报告已生成至 report.log。")
    except Exception as e:
        logging.error(f"生成报告时发生错误：{e}")

if __name__ == "__main__":
    main()
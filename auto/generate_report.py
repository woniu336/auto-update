import re
import aiohttp
import asyncio
import os
from bs4 import BeautifulSoup
import time
import random
import json
from pathlib import Path
import hashlib
import math

# 全局常量定义
CACHE_DURATION = 86400 * 30  # 缓存时间30天

class Movie:
    def __init__(self, name, quark_link, baidu_link, uc_link, douban_link):
        self.name = name
        self.quark_link = quark_link
        self.baidu_link = baidu_link
        self.uc_link = uc_link
        self.douban_link = douban_link
        self.douban_id = self.extract_douban_id()
        self.image_url = ''
        self.cache_key = self._generate_cache_key()

    def extract_douban_id(self):
        """从豆瓣链接中提取豆瓣ID"""
        match = re.search(r'/subject/(\d+)/', self.douban_link)
        return match.group(1) if match else ''

    def _generate_cache_key(self):
        """生成唯一的缓存键"""
        if self.douban_id:
            return f"douban_{self.douban_id}"
        else:
            return f"name_{hashlib.md5(self.name.encode('utf-8')).hexdigest()}"

    async def fetch_douban_image(self, session, headers, cache_dir, max_retries=3, retry_delay=5):
        """异步获取豆瓣图片链接，带重试机制和缓存"""
        cache_file = Path(cache_dir) / f"{self.cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    if cache_data.get('timestamp', 0) + CACHE_DURATION > time.time():
                        if cache_data.get('douban_id') == self.douban_id:
                            self.image_url = cache_data['image_url']
                            print(f"从缓存加载图片: {self.name}")
                            return
            except Exception as e:
                print(f"读取缓存失败 {self.name}: {str(e)}")

        for retry in range(max_retries):
            try:
                await asyncio.sleep(random.uniform(1, 3))
                
                headers.update({
                    'Cookie': 'bid=' + ''.join(random.choice('0123456789abcdef') for _ in range(11)),
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                })
                
                async with session.get(self.douban_link, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    
                    if 'sec.douban.com' in str(response.url):
                        self.image_url = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMDAiIGhlaWdodD0iMzAwIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7pnIDopoHpqozor4E8L3RleHQ+PC9zdmc+'
                        return
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    img_div = soup.find('div', id='mainpic')
                    if img_div:
                        img_tag = img_div.find('img')
                        if img_tag and 'src' in img_tag.attrs:
                            self.image_url = img_tag['src']
                            self._save_to_cache(cache_file)
                            print(f"已缓存图片: {self.name}")
                            return

                    sharing_a = soup.find('a', class_='bn-sharing')
                    if sharing_a and 'data-pic' in sharing_a.attrs:
                        self.image_url = sharing_a['data-pic']
                        self._save_to_cache(cache_file)
                        print(f"已缓存图片: {self.name}")
                        return
                    
                    raise Exception("未找到图片链接")
                    
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"重试 {retry + 1}/{max_retries} 获取图片 {self.name}: {str(e)}")
                    await asyncio.sleep(retry_delay)
                    continue
                print(f"达到最大重试次数 {self.name}: {str(e)}")
                self.image_url = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMDAiIGhlaWdodD0iMzAwIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7ml6DmtYvor4Tlm77niYc8L3RleHQ+PC9zdmc+'

    def _save_to_cache(self, cache_file):
        """保存图片URL到缓存"""
        try:
            cache_data = {
                'image_url': self.image_url,
                'timestamp': int(time.time()),
                'douban_id': self.douban_id,
                'name': self.name
            }
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存失败 {self.name}: {str(e)}")

class ReportGenerator:
    def __init__(self, log_path, output_html, quark_log_path='../kua-main/quark_save.log', cache_dir='./cache'):
        self.log_path = log_path
        self.output_html = output_html
        self.quark_log_path = quark_log_path
        self.cache_dir = cache_dir
        self.movies = []
        self.total_movies = 0
        self.inaccessible_urls = []
        self.violation_movies = []  # 新增：存储违规影片列表
        
        # 创建缓存目录
        os.makedirs(cache_dir, exist_ok=True)
        
        # 清理过期缓存
        self._clean_expired_cache()

    def _clean_expired_cache(self):
        """清理过期的缓存文件"""
        try:
            cache_dir = Path(self.cache_dir)
            current_time = time.time()
            for cache_file in cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    if cache_data.get('timestamp', 0) + CACHE_DURATION <= current_time:
                        cache_file.unlink()
                        print(f"删除过期缓存: {cache_file.name}")
                except Exception as e:
                    print(f"清理缓存文件失败 {cache_file}: {str(e)}")
        except Exception as e:
            print(f"清理缓存目录失败: {str(e)}")

    def parse_log(self):
        with open(self.log_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # 修正后的正则表达式，确保匹配正确的影片名称和链接
        inaccessible_section = re.search(
            r'无法访问的影片页面列表（404或其他错误）:\n((?:- .+\n)*)', 
            content,
            re.MULTILINE
        )
        if inaccessible_section:
            self.inaccessible_urls = re.findall(r'- (.+)', inaccessible_section.group(1))
        else:
            self.inaccessible_urls = []  # 确保当没有匹配时不会引发错误

        total_match = re.search(r'总影片数量:\s*(\d+)', content)
        self.total_movies = int(total_match.group(1)) if total_match else 0

        movie_pattern = re.compile(
            r'影片名称:\s*(.*?)\n'
            r'(?:\s+夸克网盘链接:\s*(.*?)\n)?'
            r'(?:\s+百度网盘链接:\s*(.*?)\n)?'
            r'(?:\s+uc网盘链接:\s*(.*?)\n)?'
            r'\s+豆瓣链接:\s*(.*?)(?:\n|$)',
            re.DOTALL
        )
        
        for match in movie_pattern.finditer(content):
            name, quark, baidu, uc, douban = match.groups()
            movie = Movie(
                name=name.strip(),
                quark_link=quark.strip() if quark else '',
                baidu_link=baidu.strip() if baidu else '',
                uc_link=uc.strip() if uc else '',
                douban_link=douban.strip() if douban else ''
            )
            self.movies.append(movie)

    def parse_quark_log(self):
        """解析夸克日志文件，提取违规影片"""
        try:
            with open(self.quark_log_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # 分割成每个任务块
            task_blocks = re.split(r'#\d+------------------\n', content)
            
            for block in task_blocks:
                if '：文件涉及违规内容' in block:
                    # 提取任务名称
                    match = re.search(r'任务名称:\s*(.*?)\n', block)
                    if match:
                        movie_name = match.group(1).strip()
                        if movie_name and movie_name not in self.violation_movies:
                            self.violation_movies.append(movie_name)
            
            print(f"发现 {len(self.violation_movies)} 个违规影片")
        except Exception as e:
            print(f"解析夸克日志失败: {str(e)}")

    async def fetch_all_images(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15'
        ]

        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Referer': 'https://movie.douban.com'
        }

        connector = aiohttp.TCPConnector(limit=5)  # 限制并发连接数
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for movie in self.movies:
                headers['User-Agent'] = random.choice(user_agents)
                task = movie.fetch_douban_image(session, headers.copy(), self.cache_dir)
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
    def _generate_violation_section(self):
        """生成违规影片和无法访问URL展示区域的HTML"""
        # 违规影片部分
        violation_movies_html = '\n'.join([f'<div class="violation-item">{movie}</div>' 
                                         for movie in self.violation_movies])
        
        # 无法访问URL部分
        inaccessible_urls_html = '\n'.join([f'<div class="inaccessible-item"><a href="{url}" target="_blank">{url}</a></div>' 
                                           for url in self.inaccessible_urls])
        
        violation_section = ''
        if self.violation_movies:
            violation_section = f'''
            <div class="violation-section">
                <h2 class="violation-title">资源失效的影片</h2>
                <div class="violation-list">
                    {violation_movies_html}
                </div>
            </div>
            '''
        
        inaccessible_section = ''
        if self.inaccessible_urls:
            inaccessible_section = f'''
            <div class="inaccessible-section">
                <h2 class="inaccessible-title">海外禁看的影片页面</h2>
                <div class="inaccessible-list">
                    {inaccessible_urls_html}
                </div>
            </div>
            '''
        
        return violation_section + inaccessible_section

    async def run(self):
        self.parse_log()
        self.parse_quark_log()  # 添加这行
        print("开始异步获取图片...")
        await self.fetch_all_images()
        print("图片获取完成，开始生成HTML...")
        self.generate_html()
    
    def generate_html(self):
        # 定义分页变量
        movies_per_page = 25
        total_pages = math.ceil(len(self.movies) / movies_per_page)
        
        current_time = time.strftime("%Y-%m-%d %H:%M", time.localtime())
        
        css_styles = '''
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 40px;
            flex-wrap: wrap;
        }
        .stat-circle {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: #4CAF50;
            color: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            text-align: center;
        }
        .stat-circle h3 {
            margin: 0;
            font-size: 14px;
        }
        .stat-circle .number {
            font-size: 24px;
            font-weight: bold;
            margin: 5px 0;
        }
        .movies-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
            padding: 20px;
            min-height: 500px;
        }
        .movie-card {
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.2s;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .movie-card:hover {
            transform: translateY(-5px);
        }
        .movie-image {
            width: 100%;
            height: 280px;
            object-fit: cover;
            cursor: pointer;
            background-color: #eee;
        }
        .movie-info {
            padding: 10px;
            width: 100%;
            text-align: center;
        }
        .movie-title {
            font-size: 14px;
            margin: 5px 0;
            height: 40px;
            overflow: hidden;
        }
        .button-group {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 5px;
            padding: 10px 0;
        }
        .btn {
            padding: 5px 8px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            color: white;
            transition: background-color 0.2s;
            min-width: 60px;
            max-width: 80px;
            margin: 2px;
        }
        .btn-copy {
            background-color: #4CAF50;
        }
        .btn-copy:hover {
            background-color: #45a049;
        }
        .generation-time {
            text-align: center;
            color: #666;
            margin: 10px 0;
            font-size: 14px;
        }
        .pagination {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        .page-btn {
            padding: 8px 12px;
            border: 1px solid #4CAF50;
            border-radius: 4px;
            cursor: pointer;
            background: white;
            color: #4CAF50;
            transition: all 0.2s;
        }
        .page-btn:hover {
            background: #4CAF50;
            color: white;
        }
        .page-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .violation-section {
            margin: 20px 0;
            padding: 20px;
            background-color: #fff3f3;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .violation-title {
            color: #ff4444;
            margin-bottom: 10px;
            text-align: center;
        }
        .violation-list {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
        }
        .violation-item {
            background: #fff;
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #ffcccc;
        }
        .inaccessible-section {
            margin: 20px 0;
            padding: 20px;
            background-color: #f3f3ff;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .inaccessible-title {
            color: #4444ff;
            margin-bottom: 10px;
            text-align: center;
        }
        .inaccessible-list {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
        }
        .inaccessible-item {
            background: #fff;
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #ccccff;
        }
        .inaccessible-item a {
            color: #4444ff;
            text-decoration: none;
        }
        .inaccessible-item a:hover {
            text-decoration: underline;
        }
        @media (max-width: 600px) {
            .stat-circle {
                width: 100px;
                height: 100px;
            }
            .stat-circle .number {
                font-size: 20px;
            }
            .btn {
                font-size: 10px;
                padding: 5px;
            }
        }
        '''

        html_content = f'''
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>影片报告</title>
            <style>
            {css_styles}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>影片报告</h1>
                    <div class="generation-time">生成时间：{current_time}</div>
                    <div class="stats">
                        <div class="stat-circle">
                            <h3>总影片数量</h3>
                            <div class="number">{self.total_movies}</div>
                        </div>
                        <div class="stat-circle">
                            <h3>海外禁看数量</h3>
                            <div class="number">{len(self.inaccessible_urls)}</div>
                        </div>
                        <div class="stat-circle">
                            <h3>资源失效数量</h3>
                            <div class="number">{len(self.violation_movies)}</div>
                        </div>
                    </div>
                </div>

                <!-- 添加违规影片展示区域 -->
                {self._generate_violation_section()}

                <!-- 分页控制 -->
                <div class="pagination">
                    <button class="page-btn" onclick="changePage('prev')" id="prevBtn">上一页</button>
                    <span id="pageInfo"></span>
                    <button class="page-btn" onclick="changePage('next')" id="nextBtn">下一页</button>
                </div>
                
                <!-- 电影网格 -->
                <div id="movieGrid" class="movies-grid">
                </div>
                
                <!-- 底部分页控制 -->
                <div class="pagination">
                    <button class="page-btn" onclick="changePage('prev')" id="prevBtnBottom">上一页</button>
                    <span id="pageInfoBottom"></span>
                    <button class="page-btn" onclick="changePage('next')" id="nextBtnBottom">下一页</button>
                </div>
            </div>

            <script>
                const moviesData = {json.dumps([{
                    'name': movie.name,
                    'image_url': movie.image_url,
                    'douban_link': movie.douban_link,
                    'quark_link': movie.quark_link,
                    'baidu_link': movie.baidu_link,
                    'uc_link': movie.uc_link
                } for movie in self.movies])};
                
                const MOVIES_PER_PAGE = {movies_per_page};
                let currentPage = 1;
                
                function renderMovies(page) {{
                    const start = (page - 1) * MOVIES_PER_PAGE;
                    const end = start + MOVIES_PER_PAGE;
                    const movieGrid = document.getElementById('movieGrid');
                    movieGrid.innerHTML = '';
                    
                    moviesData.slice(start, end).forEach(movie => {{
                        const buttons = [];
                        if (movie.quark_link) buttons.push(`<button class="btn btn-copy" onclick="copyToClipboard('${{movie.quark_link}}', '夸克链接')">夸克</button>`);
                        if (movie.baidu_link) buttons.push(`<button class="btn btn-copy" onclick="copyToClipboard('${{movie.baidu_link}}', '百度链接')">百度</button>`);
                        if (movie.uc_link) buttons.push(`<button class="btn btn-copy" onclick="copyToClipboard('${{movie.uc_link}}', 'UC链接')">UC</button>`);
                        
                        const movieCard = `
                            <div class="movie-card">
                                <img class="movie-image" data-src="${{movie.image_url}}" alt="${{movie.name}} 海报" 
                                     src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMDAiIGhlaWdodD0iMzAwIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7liqDovb3kuK0uLi48L3RleHQ+PC9zdmc+"
                                     onclick="extractAndCopyDoubanId('${{movie.douban_link}}')"
                                     loading="lazy" referrerpolicy="no-referrer">
                                <div class="movie-info">
                                    <div class="movie-title">${{movie.name}}</div>
                                    <div class="button-group">
                                        ${{buttons.join('')}}
                                    </div>
                                </div>
                            </div>
                        `;
                        movieGrid.innerHTML += movieCard;
                    }});
                    
                    updatePagination();
                    initLazyLoading();
                }}
                
                function changePage(action) {{
                    if (action === 'prev' && currentPage > 1) {{
                        currentPage--;
                    }} else if (action === 'next' && currentPage < Math.ceil(moviesData.length / MOVIES_PER_PAGE)) {{
                        currentPage++;
                    }}
                    renderMovies(currentPage);
                    window.scrollTo(0, 0);
                }}
                
                function updatePagination() {{
                    const totalPages = Math.ceil(moviesData.length / MOVIES_PER_PAGE);
                    const pageInfo = `第 ${{currentPage}} / ${{totalPages}} 页`;
                    document.getElementById('pageInfo').textContent = pageInfo;
                    document.getElementById('pageInfoBottom').textContent = pageInfo;
                    
                    document.getElementById('prevBtn').disabled = currentPage === 1;
                    document.getElementById('nextBtn').disabled = currentPage === totalPages;
                    document.getElementById('prevBtnBottom').disabled = currentPage === 1;
                    document.getElementById('nextBtnBottom').disabled = currentPage === totalPages;
                }}
                
                document.addEventListener('DOMContentLoaded', function() {{
                    renderMovies(1);
                }});

                function extractAndCopyDoubanId(url) {{
                    if (!url) {{
                        alert('没有豆瓣链接');
                        return;
                    }}
                    const match = url.match(/subject\\/(\\d+)/);
                    if (match && match[1]) {{
                        copyToClipboard(match[1], '豆瓣ID');
                    }} else {{
                        alert('无法提取豆瓣ID');
                    }}
                }}

                function copyToClipboard(text, type) {{
                    if (!text) {{
                        alert('没有可复制的内容');
                        return;
                    }}
                    navigator.clipboard.writeText(text).then(function() {{
                        alert(type + '已复制到剪贴板');
                    }}).catch(function(err) {{
                        alert('复制失败：' + err);
                    }});
                }}

                function initLazyLoading() {{
                    var lazyImages = document.querySelectorAll('img[data-src]');
                    var imageObserver = new IntersectionObserver(function(entries, observer) {{
                        entries.forEach(function(entry) {{
                            if (entry.isIntersecting) {{
                                var img = entry.target;
                                img.src = img.dataset.src;
                                observer.unobserve(img);
                            }}
                        }});
                    }});

                    lazyImages.forEach(function(img) {{
                        imageObserver.observe(img);
                    }});
                }}
            </script>
        </body>
        </html>
        '''

        with open(self.output_html, 'w', encoding='utf-8') as file:
            file.write(html_content)
        print(f"HTML 报告已生成: {self.output_html}")

if __name__ == "__main__":
    generator = ReportGenerator(log_path='./report.log', output_html='../index.html')
    asyncio.run(generator.run())
import re
import os

def clean_title(title):
    # 移除括号及其内容
    cleaned = re.sub(r'\s*\([^)]*\)', '', title).strip()
    return cleaned

def process_log_file():
    # 确保目标目录存在
    os.makedirs('../kua-main', exist_ok=True)
    output_file = '../kua-main/movie_links.txt'
    
    # 读取现有的链接（如果文件存在）
    existing_links = {}
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    title = line.split('=')[0]
                    existing_links[title] = line.strip()

    # 处理report.log
    new_links = []  # 使用列表来保持顺序
    
    try:
        with open('report.log', 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 定位到实际的影片列表开始位置
            start_marker = "影片名称及其对应的网盘链接和豆瓣链接:"
            if start_marker not in content:
                raise Exception("找不到影片列表开始标记")
            
            # 获取影片列表部分的内容
            movie_section = content.split(start_marker)[1].strip()
            
            # 分割每个影片信息块
            movie_blocks = []
            current_block = []
            
            for line in movie_section.split('\n'):
                if line.strip():  # 非空行
                    current_block.append(line)
                elif current_block:  # 空行且当前块非空
                    movie_blocks.append('\n'.join(current_block))
                    current_block = []
            
            # 处理最后一个块
            if current_block:
                movie_blocks.append('\n'.join(current_block))
            
            # 处理每个影片块
            for block in movie_blocks:
                lines = block.split('\n')
                # 确保这是一个有效的影片块（必须包含影片名称、夸克链接和豆瓣链接）
                if not (lines[0].startswith('影片名称:') and 
                       any('夸克网盘链接:' in line for line in lines) and
                       any('豆瓣链接:' in line for line in lines)):
                    continue
                
                title = clean_title(lines[0].replace('影片名称:', '').strip())
                
                quark_link = None
                for line in lines:
                    if '夸克网盘链接:' in line:
                        quark_link = line.replace('夸克网盘链接:', '').strip()
                        quark_link = quark_link.replace('  ', '')
                        break
                
                if title and quark_link:
                    formatted_line = f"{title}={quark_link}=/yyds/{title}"
                    new_links.append((title, formatted_line))
                    print(f"处理影片: {title}")

        # 更新现有链接，保持新的顺序
        final_links = []
        processed_titles = set()
        
        # 首先添加新的链接
        for title, line in new_links:
            final_links.append(line)
            processed_titles.add(title)
        
        # 添加旧的、未被更新的链接
        for title, line in existing_links.items():
            if title not in processed_titles:
                final_links.append(line)
        
        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in final_links:
                f.write(line + '\n')
                
        print(f"写入完成，总链接数量: {len(final_links)}")
        
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")

if __name__ == '__main__':
    process_log_file()
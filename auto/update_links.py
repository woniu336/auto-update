import re

def read_quark_links(quark_file):
    quark_dict = {}
    with open(quark_file, 'r', encoding='utf-8') as f:
        for line in f:
            if '>>>' in line:
                movie, link = line.strip().split('>>>')
                quark_dict[movie] = link
    return quark_dict

def update_report_log(report_file, quark_dict):
    with open(report_file, 'r', encoding='utf-8') as f:
        content = f.read()

    for movie, new_quark_link in quark_dict.items():
        # 构建匹配模式，忽略影片名称后的括号内容
        pattern = rf'(影片名称: {re.escape(movie)}(?:\s*\([^)]*\))?\s+夸克网盘链接: )https?://\S+'
        # 替换新的夸克链接
        content, count = re.subn(pattern, rf'\1{new_quark_link}', content)
        if count == 0:
            print(f'未找到电影 {movie} 的夸克链接，未进行更新。')

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    quark_file = 'quark-share-123.txt'
    report_file = 'report.log'
    quark_dict = read_quark_links(quark_file)
    update_report_log(report_file, quark_dict)
    print('报告已更新。')

if __name__ == '__main__':
    main()
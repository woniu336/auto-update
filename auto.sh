#!/bin/bash

# 颜色定义
CYAN='\033[0;36m'
LIGHT_CYAN='\033[1;36m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 配置文件路径
CONFIG_FILE="./kua-main/quark_config.json"
COOKIE_FILE="./auto/cookie.txt"
RUN_ALL_SCRIPT="./run_all.sh"
MOVIE_LINKS_FILE="./kua-main/check_movie_links.py"  # 添加这行
SCRAPER_FILE="./auto/scraper.py"  # 添加新的文件路径

# 显示菜单部分
show_menu() {
    clear
    echo -e "${CYAN}┌────────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│       低端影视夸克网盘追更脚本               │${NC}"
    echo -e "${CYAN}├────────────────────────────────────────────┤${NC}"
    echo -e "${LIGHT_CYAN}│  1.${NC} 安装依赖                             ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  2.${NC} 更新Cookie                           ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  3.${NC} 设置钉钉通知                         ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  4.${NC} 设置夸克网盘转存目录ID               ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  5.${NC} 自动分享测试                         ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  6.${NC} 设置爬取页数                         ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  7.${NC} 手动运行测试                         ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  8.${NC} 设置定时任务                         ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  0.${NC} 退出                                 ${CYAN}│${NC}"
    echo -e "${CYAN}└────────────────────────────────────────────┘${NC}"
}

# 安装依赖
install_dependencies() {
    echo -e "${YELLOW}开始安装依赖...${NC}"
    
    # 安装Python依赖
    echo -e "${CYAN}安装Python依赖...${NC}"
    pip install requests beautifulsoup4 tenacity aiohttp treelib
    
    # 安装系统依赖
    echo -e "${CYAN}安装系统依赖...${NC}"
    sudo apt-get update
    sudo apt-get install -y jq
    
    echo -e "${GREEN}依赖安装完成${NC}"
}

# 更新Cookie
update_cookie() {
    echo -e "${YELLOW}请输入新的Cookie:${NC}"
    read new_cookie
    
    # 检查配置文件是否存在
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}错误：找不到配置文件 $CONFIG_FILE${NC}"
        return
    fi
    
    # 更新 quark_config.json
    jq --arg cookie "$new_cookie" '.cookie = [$cookie]' $CONFIG_FILE > tmp.$$.json && mv tmp.$$.json $CONFIG_FILE
    
    # 更新 cookie.txt
    echo "$new_cookie" > $COOKIE_FILE
    
    echo -e "${GREEN}Cookie已更新到以下位置：${NC}"
    echo -e "${CYAN}1. $CONFIG_FILE${NC}"
    echo -e "${CYAN}2. $COOKIE_FILE${NC}"
}

# 设置钉钉通知
set_dingtalk_notify() {
    echo -e "${YELLOW}请输入钉钉机器人的token:${NC}"
    read access_token
    echo -e "${YELLOW}请输入钉钉机器人的secret:${NC}"
    read secret

    # 检查配置文件是否存在
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}错误：找不到配置文件 $CONFIG_FILE${NC}"
        return
    fi

    # 检查 check_movie_links.py 文件是否存在
    if [ ! -f "$MOVIE_LINKS_FILE" ]; then
        echo -e "${RED}错误：找不到文件 $MOVIE_LINKS_FILE${NC}"
        return
    fi

    # 更新 quark_config.json
    jq '.push_config.DD_BOT_TOKEN = "'$access_token'" | .push_config.DD_BOT_SECRET = "'$secret'"' $CONFIG_FILE > tmp.$$.json && mv tmp.$$.json $CONFIG_FILE

    # 更新 check_movie_links.py
    awk -v token="$access_token" -v secret="$secret" '
    /^ACCESS_TOKEN = / { print "ACCESS_TOKEN = \"" token "\""; next }
    /^SECRET = / { print "SECRET = \"" secret "\""; next }
    { print }
    ' "$MOVIE_LINKS_FILE" > tmp.$$.py && mv tmp.$$.py "$MOVIE_LINKS_FILE"

    echo -e "${GREEN}钉钉通知设置已更新${NC}"
    echo -e "${CYAN}Token: $access_token${NC}"
    echo -e "${CYAN}Secret: $secret${NC}"
    echo -e "${CYAN}已更新以下文件：${NC}"
    echo -e "${CYAN}1. $CONFIG_FILE${NC}"
    echo -e "${CYAN}2. $MOVIE_LINKS_FILE${NC}"
}

# 设置夸克网盘转存目录ID
set_directory_id() {
    echo -e "${YELLOW}请输入新的目录ID:${NC}"
    read dir_id
    
    # 检查文件是否存在
    if [ ! -f "$RUN_ALL_SCRIPT" ]; then
        echo -e "${RED}错误：找不到脚本文件 $RUN_ALL_SCRIPT${NC}"
        return
    fi

    if [ ! -f "./auto/update_links.py" ]; then
        echo -e "${RED}错误：找不到脚本文件 ./auto/update_links.py${NC}"
        return
    fi
    
    # 更新 run_all.sh 中的目录ID
    sed -i "s/--fid [a-zA-Z0-9]*/--fid $dir_id/g" $RUN_ALL_SCRIPT
    
    # 更新 update_links.py 中的目录ID
    sed -i "s/quark-share-[a-zA-Z0-9]*/quark-share-$dir_id/g" "./auto/update_links.py"
    
    echo -e "${GREEN}目录ID已更新为: $dir_id${NC}"
    echo -e "${CYAN}已更新以下文件：${NC}"
    echo -e "${CYAN}1. $RUN_ALL_SCRIPT${NC}"
    echo -e "${CYAN}2. ./auto/update_links.py${NC}"
}

# 自动分享测试
test_auto_share() {
    echo -e "${YELLOW}开始自动分享测试...${NC}"
    current_dir=$(pwd)
    
    # 从run_all.sh中获取fid
    fid=$(grep -o 'fid [0-9a-f]\{32\}' "$RUN_ALL_SCRIPT" | head -1 | awk '{print $2}')
    
    if [ -z "$fid" ]; then
        echo -e "${RED}错误：无法获取fid，请先在菜单4中设置夸克网盘转存目录ID${NC}"
        return
    fi
    
    if [ ! -d "./auto" ]; then
        echo -e "${RED}错误：找不到 auto 目录${NC}"
        return
    fi
    
    cd ./auto
    echo -e "${CYAN}执行同步目录...${NC}"
    php ./QuarkService.php --options syn_dir --fid ${fid} || {
        echo -e "${RED}QuarkService.php syn_dir 执行失败${NC}"
    }
    sleep 2
    sudo chown root:root quark-dir-${fid}.txt || echo "更改dir文件所有者失败"
    
    echo -e "${CYAN}执行分享...${NC}"
    php ./QuarkService.php --options share --fid ${fid} --type 'repeat' || {
        echo -e "${RED}QuarkService.php share 执行失败${NC}"
    }
    sleep 2
    sudo chown root:root quark-share-${fid}.txt || echo "更改share文件所有者失败"
    
    cd "$current_dir"
    echo -e "${GREEN}自动分享测试完成${NC}"
}

# 新增：设置爬取页数
set_max_pages() {
    echo -e "${YELLOW}请输入要爬取的页面数 (当前默认为1):${NC}"
    read max_pages

    # 验证输入是否为正整数
    if ! [[ "$max_pages" =~ ^[0-9]+$ ]] || [ "$max_pages" -lt 1 ]; then
        echo -e "${RED}错误：请输入大于0的整数${NC}"
        return
    fi  # 将 } 改为 fi

    # 检查文件是否存在
    if [ ! -f "$SCRAPER_FILE" ]; then
        echo -e "${RED}错误：找不到文件 $SCRAPER_FILE${NC}"
        return
    fi  # 将 } 改为 fi

    # 更新 scraper.py 中的 max_pages
    sed -i "s/max_pages = [0-9][0-9]*/max_pages = $max_pages/" "$SCRAPER_FILE"

    echo -e "${GREEN}爬取页数已更新为: $max_pages${NC}"
    echo -e "${CYAN}已更新文件：$SCRAPER_FILE${NC}"
}

# 手动运行测试
run_manual_test() {
    echo -e "${YELLOW}开始手动运行测试，需要一点时间...${NC}"
    
    if [ ! -f "$RUN_ALL_SCRIPT" ]; then
        echo -e "${RED}错误：找不到 run_all.sh 脚本${NC}"
        return
    fi
    
    bash "$RUN_ALL_SCRIPT"
    echo -e "${GREEN}手动运行测试完成${NC}"
}

# 设置定时任务
set_cron_job() {
    echo -e "${YELLOW}请输入定时任务表达式 (回车默认: 0 7,18 * * * 每天早上7点和下午18点执行):${NC}"
    read cron_expression
    
    if [ -z "$cron_expression" ]; then
        cron_expression="0 7,18 * * *"
    fi
    
    # 获取脚本的绝对路径
    script_path=$(readlink -f $RUN_ALL_SCRIPT)
    
    # 检查脚本是否存在
    if [ ! -f "$script_path" ]; then
        echo -e "${RED}错误：找不到脚本文件 $script_path${NC}"
        return
    fi
    
    # 添加或更新定时任务
    (crontab -l 2>/dev/null | grep -v "$RUN_ALL_SCRIPT"; echo "$cron_expression $script_path") | crontab -
    
    echo -e "${GREEN}定时任务已设置: $cron_expression${NC}"
    echo -e "${CYAN}将在每天早上7点和下午18点执行脚本: $script_path${NC}"
}

# 等待用户按Enter键
wait_for_enter() {
    echo -e "${YELLOW}按Enter键返回主菜单...${NC}"
    read
}

# 主循环部分
while true; do
    show_menu
    read -p "请选择操作: " choice
    case $choice in
        1) install_dependencies; wait_for_enter ;;
        2) update_cookie; wait_for_enter ;;
        3) set_dingtalk_notify; wait_for_enter ;;
        4) set_directory_id; wait_for_enter ;;
        5) test_auto_share; wait_for_enter ;;
        6) set_max_pages; wait_for_enter ;;
        7) run_manual_test; wait_for_enter ;;
        8) set_cron_job; wait_for_enter ;;
        0) echo -e "${GREEN}退出程序${NC}"; exit 0 ;;
        *) echo -e "${RED}无效的选择，请重新输入${NC}"; wait_for_enter ;;
    esac
done
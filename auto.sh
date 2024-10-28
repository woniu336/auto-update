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

# 显示菜单
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
    echo -e "${LIGHT_CYAN}│  6.${NC} 手动运行测试                         ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  7.${NC} 设置定时任务                         ${CYAN}│${NC}"
    echo -e "${LIGHT_CYAN}│  8.${NC} 设置脚本启动快捷键                   ${CYAN}│${NC}"
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

    # 更新配置文件
    jq '.push_config.DD_BOT_TOKEN = "'$access_token'" | .push_config.DD_BOT_SECRET = "'$secret'"' $CONFIG_FILE > tmp.$$.json && mv tmp.$$.json $CONFIG_FILE

    echo -e "${GREEN}钉钉通知设置已更新${NC}"
    echo -e "${CYAN}Token: $access_token${NC}"
    echo -e "${CYAN}Secret: $secret${NC}"
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
    
    if [ ! -d "./auto" ]; then
        echo -e "${RED}错误：找不到 auto 目录${NC}"
        return
    fi
    
    cd ./auto
    echo -e "${CYAN}执行同步目录...${NC}"
    php ./QuarkService.php --options syn_dir --fid 4a39e2d04e6c497f88184c58d8662f75 || {
        echo -e "${RED}QuarkService.php syn_dir 执行失败${NC}"
    }
    
    echo -e "${CYAN}执行分享...${NC}"
    php ./QuarkService.php --options share --fid 4a39e2d04e6c497f88184c58d8662f75 --type 'repeat' || {
        echo -e "${RED}QuarkService.php share 执行失败${NC}"
    }
    
    cd "$current_dir"
    echo -e "${GREEN}自动分享测试完成${NC}"
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

# 设置脚本启动快捷键
set_shortcut() {
    echo -e "${YELLOW}请输入快捷键命令 (例如: q):${NC}"
    read shortcut
    
    if [ -z "$shortcut" ]; then
        echo -e "${RED}错误：快捷键不能为空${NC}"
        return
    fi
    
    # 获取当前脚本的绝对路径
    SCRIPT_PATH=$(readlink -f "$0")
    
    # 删除已存在的别名
    sed -i "/alias.*$(basename $SCRIPT_PATH)/d" ~/.bashrc
    
    # 添加新的别名
    echo "alias $shortcut='bash $SCRIPT_PATH'" >> ~/.bashrc
    
    echo -e "${GREEN}快捷键已设置为: $shortcut${NC}"
    echo -e "${YELLOW}请运行以下命令使设置生效：${NC}"
    echo -e "${CYAN}source ~/.bashrc${NC}"
}

# 等待用户按Enter键
wait_for_enter() {
    echo -e "${YELLOW}按Enter键返回主菜单...${NC}"
    read
}

# 主循环
while true; do
    show_menu
    read -p "请选择操作: " choice
    case $choice in
        1) install_dependencies; wait_for_enter ;;
        2) update_cookie; wait_for_enter ;;
        3) set_dingtalk_notify; wait_for_enter ;;
        4) set_directory_id; wait_for_enter ;;
        5) test_auto_share; wait_for_enter ;;
        6) run_manual_test; wait_for_enter ;;
        7) set_cron_job; wait_for_enter ;;
        8) set_shortcut; wait_for_enter ;;
        0) echo -e "${GREEN}退出程序${NC}"; exit 0 ;;
        *) echo -e "${RED}无效的选择，请重新输入${NC}"; wait_for_enter ;;
    esac
done
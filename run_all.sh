#!/bin/bash

# 设置日志文件路径
LOG_FILE="execution.log"

# 开始记录日志
{
  echo "==================== $(date) ===================="
  
  # 爬取资源
  echo "开始爬取资源..."
  cd auto
  python3 scraper.py || echo "scraper.py 执行失败"
  
  # 转换格式
  echo "开始转换格式..."
  python3 process_links.py || echo "process_links.py 执行失败"
  
  # 更新json配置
  echo "开始更新json配置..."
  cd ../kua-main
  python3 movie_list.py || echo "movie_list.py 执行失败"
  
  # 转存
  echo "开始转存..."
  python3 quark_auto_save.py quark_config.json || echo "quark_auto_save.py 执行失败"
  
  # 自动分享
  echo "开始自动分享..."
  cd ../auto
  php ./QuarkService.php --options syn_dir --fid 4a39e2d04e6c497f88184c58d8662f || echo "QuarkService.php syn_dir 执行失败"
  php ./QuarkService.php --options share --fid 4a39e2d04e6c497f88184c58d8662f --type 'repeat' || echo "QuarkService.php share 执行失败"
  
  # 替换夸克网盘
  echo "开始替换夸克网盘..."
  python3 update_links.py || echo "update_links.py 执行失败"
  
  # 检查链接有效性
  echo "开始检查链接有效性..."
  cd ../kua-main
  python3 check_movie_links.py quark_config.json || echo "check_movie_links.py 执行失败"
  
  # 生成html页面
  echo "开始生成html页面..."
  cd ../auto
  python3 generate_report.py || echo "generate_report.py 执行失败"
  
  echo "==================== 完成 $(date) ===================="
} >> "$LOG_FILE" 2>&1

# 确保脚本静默执行
exit 0
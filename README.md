## 使用方法

```
cd /www/wwwboot/123.com  # 定位到站点目录，可以是静态
```

然后：



```
git clone https://github.com/woniu336/auto-update.git
cd auto-update
chmod +x run_all.sh
chmod +x auto.sh && ./auto.sh
```


## 功能

从低端影视网站页面爬取影片信息，并把夸克网盘资源转存到自己的夸克网盘并自动生成分享链接，最后在目录下生成html页面（见底下）

可以设置定时转存更新

注意：**只有夸克网盘资源是你自己的**（脚本会自动替换），百度和UC依然是低端影视分享出来的。

![image.png](https://img.meituan.net/video/9b5427a42bba2dacd64147a8d9a5e9c01041599.png)



## 脚本流程

> 这个脚本的主要功能是：从日志文件中解析电影信息，异步获取豆瓣电影海报，并生成一个包含电影网格展示、分页功能和资源状态统计的交互式HTML报告页面。
>
> 具体流程为：
> 1. 读取日志文件，解析电影名称、网盘链接和豆瓣链接
> 2. 异步爬取豆瓣电影海报并缓存
> 3. 统计资源状态（总数、失效数、海外禁看数）
> 4. 生成响应式HTML页面，支持分页浏览和链接复制功能



## 注意事项

如果遇到问题：需要启用 proc_open、exec 和 putenv 函数，

如果是宝塔面板，可以在php中把这三个函数删除，然后重启php

![image.png](https://img.meituan.net/video/04986329d158c74d5d67bdd83437198229247.png)


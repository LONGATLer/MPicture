# MPicture
这是一个用于搜索和管理图片的项目，目前已完成了通过SauceNAO的API批量获取搜索结果并保存Pixiv，gelbooru，X三个网站的结果的代码
目前仅完成了图片对应id或网址的爬取，具体下载图片还需要其他工具的辅助
未来计划：
1.完善exe的制作
2.优化代码
3.对pixiv网站的关注进行查重，若新的图片作者为未关注者会保存其id
4.制作pixiv和x的图片下载功能

已打包为exe，运行方法如下：
usage: saucenao_cli.exe [-h] --api_key API_KEY [--similarity SIMILARITY] [--sleep SLEEP] [--num NUM] [--minsim MINSIM]
[--save SAVE] [--danbooru_username DANBOORU_USERNAME] [--danbooru_api_key DANBOORU_API_KEY]
[--proxy_port PROXY_PORT]
folder

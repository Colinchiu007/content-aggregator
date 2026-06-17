# PROJECT-001 源扩展配置补丁
# 将以下内容合并到 config/config.yaml 的 sources: 列表中

# ============ 科技类（P0）============
- name: "36氪"
  rss_url: "https://36kr.com/feed"
  column: "tech"
  enabled: true
  fetch_full_content: true

- name: "IT之家"
  rss_url: "https://www.ithome.com/rss/"
  column: "tech"
  enabled: true
  fetch_full_content: true

- name: "稀土掘金"
  rss_url: "https://juejin.cn/atom.xml"
  column: "tech"
  enabled: true
  fetch_full_content: true

# ============ 财经类（P0）============
- name: "华尔街见闻"
  rss_url: "https://wallstreetcn.com/feed"
  column: "finance"
  enabled: true
  fetch_full_content: true

- name: "财联社"
  rss_url: "https://www.cls.cn/rss/"
  column: "finance"
  enabled: true
  fetch_full_content: false   # 需网页爬取全文

- name: "金十数据"
  rss_url: "https://www.jin10.com/rss/"
  column: "finance"
  enabled: true
  fetch_full_content: false

# ============ 热点榜单（P1，需爬虫）============
# 知乎热榜 - 需新建 collector
# 微博热搜 - 需新建 collector  
# 抖音热点 - 已有 douyin_hot collector
# 百度热搜 - 需新建 collector

# ============ 国际类（P1）============
- name: "Hacker News"
  rss_url: "https://news.ycombinator.com/rss"
  column: "world"
  enabled: true
  fetch_full_content: false

- name: "Product Hunt"
  rss_url: "https://www.producthunt.com/feed"
  column: "tech"
  enabled: true
  fetch_full_content: false

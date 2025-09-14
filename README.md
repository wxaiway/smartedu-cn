# 国家中小学教材下载工具集

本项目提供完整的解决方案，用于批量下载国家中小学教材资源（PDF和音频），并提供前端查询界面。共收录**3080本**教材资源。

## 项目结构

```
smartedu-cn/
├── python-solution/              # Python批量下载方案
│   ├── batch_downloader.py      # 整合版批量下载器（主程序）
│   ├── download_tasks.json      # 3471个教材的下载任务
│   ├── api_analysis_simple.py   # 获取教材目录数据
│   ├── generate_download_tasks.py # 生成下载任务列表
│   └── 下载使用说明.md          # 详细使用指南
│
├── frontend/                    # 纯前端查询下载界面
│   ├── index.html              # 主页面
│   ├── textbooks.js            # 教材数据（3080条）
│   ├── convert_data_final.py   # 数据转换脚本
│   └── README.md               # 前端使用说明
│
└── tampermonkey/                # 浏览器脚本方案
    ├── smartedu-pdf-direct-extractor.user.js  # Token获取脚本
    └── README.md                # 脚本使用说明
```

## 快速开始

### 方案一：Python批量下载（推荐）

1. **获取认证Token**
   ```bash
   # 安装Tampermonkey脚本
   # 登录平台后，脚本会显示Token
   ```

2. **批量下载教材**
   ```bash
   cd python-solution
   
   # 下载所有教材（含音频）
   python batch_downloader.py --token "你的Token"
   
   # 仅下载PDF（更快）
   python batch_downloader.py --token "你的Token" --no-multimedia
   
   # 按学段下载
   python batch_downloader.py --token "你的Token" --stage 小学
   ```

### 方案二：前端查询界面

```bash
cd frontend
# 使用Python简单服务器
python -m http.server 8000
# 或使用其他静态服务器
```

访问 http://localhost:8000 即可使用查询界面。

### 方案三：浏览器手动下载

1. 安装 `tampermonkey/smartedu-pdf-direct-extractor.user.js`
2. 访问教材页面，自动提取PDF链接
3. 适合少量下载或验证Token

## 主要功能

### 批量下载器特性
- ✅ 支持3080本教材批量下载
- ✅ 智能提取音频资源（英语、语文等）
- ✅ CDN自动切换（3个节点）
- ✅ 断点续传和失败重试
- ✅ 灵活的过滤选项（学段/学科/版本）
- ✅ 并发控制和速率限制
- ✅ 详细的进度显示和日志

### 前端特性
- 🔍 智能搜索：支持教材名称、学科、年级、版本等多维度搜索
  - 分词搜索：自动分词，支持多关键词组合
  - 中文年级支持：`一年级` 和 `1年级` 都能正确匹配
  - 模糊匹配：输入部分关键词即可查找
- 🎯 人教版专区：独立的人教版教材快速选择界面
  - 热门组合：小学语文/数学全套、初中理科/文科全套等
  - 灵活选择：支持年级和学科的自由组合
  - 智能联动：根据年级自动显示可用学科
- 🏷️ 多维筛选：按学段、学科、年级、出版社筛选
- 📱 响应式设计：完美适配PC和移动端
- 🌙 深色模式：支持明暗主题切换
- 📊 双视图模式：表格视图和卡片视图
- 💾 百度网盘下载：提供分享链接和文件路径
- 📋 导出功能：支持导出教材清单为CSV文件

### 支持的资源类型
- **PDF教材**：所有教材的PDF版本
- **音频资源**：主要在语言类教材（MP3格式）
- **视频资源**：因DRM保护无法下载

## 教材统计

根据最新数据（2025年9月14日更新）：

| 学段 | 数量 | 主要学科 |
|------|------|----------|
| 小学 | 1399本 | 语文、数学、英语、音乐、美术、科学等 |
| 初中 | 764本 | 各主要学科 |
| 高中 | 511本 | 各主要学科 |
| 特殊教育 | 289本 | 生活适应、沟通交往等 |
| 小学（五•四学制） | 97本 | 各主要学科 |
| 初中（五•四学制） | 20本 | 各主要学科 |
| **总计** | **3080本** | |

注：已清理无法下载的教材数据391个

## 下载示例

```bash
# 下载小学英语教材（含音频）
python batch_downloader.py --token "TOKEN" --stage 小学 --subject 英语

# 下载人教版教材
python batch_downloader.py --token "TOKEN" --version 人教

# 限制下载10本测试
python batch_downloader.py --token "TOKEN" --limit 10

# 重试失败的任务
python batch_downloader.py --token "TOKEN" --retry-failed
```

## 目录结构示例

```
教材库/
├── 小学/
│   ├── 语文/
│   │   └── 人教/
│   │       └── 1年级/
│   │           └── 上/
│   │               └── 语文_1年级_上_人教.pdf
│   └── 英语/
│       └── 人教/
│           └── 3年级/
│               └── 上/
│                   ├── 英语_3年级_上_人教.pdf
│                   └── 英语_3年级_上_人教_音频/
│                       └── Unit 1/
│                           └── Lesson 1/
│                               └── AUDIO-1_Listen and say.mp3
├── 初中/
├── 高中/
└── 特殊教育/
```

## 系统要求

- Python 3.7+
- 稳定的网络连接
- 充足的存储空间（完整下载需200GB+）
- 有效的认证Token

## 注意事项

1. **Token有效期**：Token会过期，需定期更新
2. **下载速度**：建议使用默认并发设置（3线程）
3. **存储空间**：提前准备足够的磁盘空间
4. **合理使用**：避免对服务器造成过大压力
5. **版权说明**：下载内容仅供个人学习使用

## 技术栈

- **Python**: 主要开发语言
- **Requests**: HTTP请求处理
- **Tampermonkey**: 浏览器脚本支持
- **Tqdm**: 进度条显示

## 贡献指南

欢迎提交Issue和Pull Request！

## 相关项目

参考了 [tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser) 的部分思路。

## 免责声明

本工具仅供学习研究使用，请勿用于商业用途。所有下载内容版权归原作者所有。

## 公众号
![伟贤AI之路](images/mp.jpg)

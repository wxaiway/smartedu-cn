# Tampermonkey 脚本使用说明

## smartedu-pdf-direct-extractor.user.js

这是一个用于国家中小学智慧教育平台的PDF提取和下载工具，支持Token获取功能。

### 功能特点

1. **自动提取PDF信息**
   - 自动查找页面中的PDF链接
   - 支持多种查找方式（iframe、React组件、网络请求拦截等）
   - 自动识别私有/公开链接

2. **Token获取和显示**
   - 自动从localStorage获取Access Token
   - 在界面上显示Token，方便复制
   - 支持一键复制Token

3. **智能下载**
   - 自动清理文件名（去除"义务教育教科书"等前缀）
   - 支持多种下载方式
   - 实时显示下载进度

4. **信息导出**
   - 复制链接时导出完整的JSON信息
   - 包含contentId、pdfUrl、token等所有必要信息

### 安装方法

1. 安装Tampermonkey浏览器扩展
2. 点击Tampermonkey图标，选择"创建新脚本"
3. 将 `smartedu-pdf-direct-extractor.user.js` 的内容复制粘贴进去
4. 保存脚本（Ctrl+S）

### 使用方法

1. **登录平台**
   - 访问 https://auth.smartedu.cn/uias/login
   - 使用账号登录

2. **打开教材页面**
   - 浏览到任意教材详情页
   - 页面右侧会自动出现"PDF提取工具"面板

3. **获取Token**
   - 工具面板下方会显示"Token信息"
   - 如果已登录，会自动显示Token
   - 点击"复制Token"按钮复制Token

4. **下载PDF**
   - 点击"提取PDF信息"查看PDF链接
   - 点击"下载PDF"直接下载
   - 或点击"复制链接"获取完整的JSON信息

### 导出的JSON格式

点击"复制链接"时，会复制以下格式的JSON：

```json
{
  "contentId": "教材ID",
  "contentType": "资源类型",
  "pageUrl": "当前页面URL",
  "pdfUrl": "PDF下载链接",
  "title": "教材标题",
  "accessToken": "认证Token"
}
```

### 批量下载准备

1. 使用此脚本获取Token
2. 复制Token保存备用
3. 使用Python批量下载工具时，将Token作为配置参数

### 注意事项

- Token有效期可能有限，建议定期更新
- 部分教材可能需要特定权限才能下载
- 下载速度取决于网络状况

### 更新日志

- v5.0 (2025-01-12)
  - 新增Token获取和显示功能
  - 改进信息导出，支持完整JSON格式
  - 优化用户界面
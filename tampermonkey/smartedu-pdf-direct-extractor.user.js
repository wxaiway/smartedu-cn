// ==UserScript==
// @name         国家中小学智慧教育平台PDF直接提取器
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  从已加载的PDF中直接提取数据，支持Token获取和显示
// @author       Assistant
// @match        https://basic.smartedu.cn/tchMaterial/detail*
// @match        https://*.smartedu.cn/tchMaterial/detail*
// @grant        GM_xmlhttpRequest
// @grant        GM_download
// @grant        GM_setClipboard
// @connect      *
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    console.log('PDF提取器已启动');

    // 创建UI
    function createUI() {
        const container = document.createElement('div');
        container.style.cssText = `
            position: fixed;
            top: 100px;
            right: 20px;
            z-index: 9999;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            max-width: 300px;
        `;
        
        container.innerHTML = `
            <h4 style="margin: 0 0 10px 0; font-size: 16px;">PDF提取工具</h4>
            <div id="pdf-info" style="font-size: 12px; color: #666; margin-bottom: 10px;">
                正在查找PDF信息...
            </div>
            <button id="extract-btn" style="
                width: 100%;
                padding: 10px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                margin-bottom: 10px;
                display: none;
            ">提取PDF信息</button>
            <textarea id="pdf-url-text" style="
                width: 100%;
                height: 80px;
                margin-top: 10px;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 12px;
                resize: vertical;
                display: none;
            " readonly></textarea>
            <button id="copy-url-btn" style="
                width: 100%;
                padding: 8px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                margin-top: 5px;
                display: none;
            ">复制链接</button>
            <button id="download-btn" style="
                width: 100%;
                padding: 8px;
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                margin-top: 5px;
                display: none;
            ">下载PDF</button>
            <div id="download-status" style="
                margin-top: 10px;
                padding: 10px;
                background: #f5f5f5;
                border-radius: 4px;
                font-size: 12px;
                display: none;
            "></div>
            <hr style="margin: 15px 0; border: none; border-top: 1px solid #eee;">
            <div style="margin-top: 10px;">
                <h5 style="margin: 0 0 5px 0; font-size: 14px;">Token信息</h5>
                <div id="token-info" style="font-size: 12px; color: #666; margin-bottom: 5px;">
                    正在获取Token...
                </div>
                <textarea id="token-text" style="
                    width: 100%;
                    height: 60px;
                    padding: 8px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    font-size: 11px;
                    font-family: monospace;
                    resize: vertical;
                    display: none;
                " readonly></textarea>
                <button id="copy-token-btn" style="
                    width: 100%;
                    padding: 8px;
                    background-color: #9C27B0;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    margin-top: 5px;
                    display: none;
                ">复制Token</button>
            </div>
        `;
        
        document.body.appendChild(container);
        return container;
    }

    // 查找PDF URL的各种方法
    function findPdfUrl() {
        console.log('开始查找PDF URL...');
        
        // 方法1: 从window对象查找（优先查找已加载的PDF）
        if (window.PDFViewerApplication && window.PDFViewerApplication.url) {
            console.log('从PDFViewer找到:', window.PDFViewerApplication.url);
            return window.PDFViewerApplication.url;
        }
        
        // 方法2: 从所有iframe查找
        const iframes = document.querySelectorAll('iframe');
        for (let iframe of iframes) {
            // 检查iframe的src
            if (iframe.src) {
                // 查找包含viewer.html的iframe（PDF.js viewer）
                if (iframe.src.includes('viewer.html') || iframe.src.includes('viewer.js')) {
                    // 从viewer URL中提取PDF文件URL
                    const urlMatch = iframe.src.match(/[?&]file=([^&]+)/);
                    if (urlMatch) {
                        let pdfUrl = decodeURIComponent(urlMatch[1]);
                        
                        // 处理可能的HTML实体编码
                        pdfUrl = pdfUrl.replace(/&amp;/g, '&');
                        
                        if (pdfUrl.includes('.pdf')) {
                            console.log('从iframe viewer参数找到:', pdfUrl);
                            
                            // 保存认证headers（如果有）
                            const headersMatch = iframe.src.match(/[?&]headers=([^&#]+)/);
                            if (headersMatch) {
                                try {
                                    const headersEncoded = decodeURIComponent(headersMatch[1]);
                                    const headers = JSON.parse(headersEncoded);
                                    window.__pdfHeaders = headers;
                                    console.log('找到认证headers:', headers);
                                } catch (e) {}
                            }
                            
                            return pdfUrl;
                        }
                    }
                    
                    try {
                        // 尝试从iframe内部获取PDF URL
                        const iframeWindow = iframe.contentWindow;
                        if (iframeWindow && iframeWindow.PDFViewerApplication && iframeWindow.PDFViewerApplication.url) {
                            console.log('从iframe PDFViewer找到:', iframeWindow.PDFViewerApplication.url);
                            return iframeWindow.PDFViewerApplication.url;
                        }
                    } catch (e) {
                        console.log('跨域限制，继续尝试其他方法');
                    }
                }
                
                // 直接是PDF URL
                if (iframe.src.includes('.pdf') && !iframe.src.includes('viewer')) {
                    console.log('从iframe src找到:', iframe.src);
                    return iframe.src;
                }
            }
        }
        
        // 方法3: 从页面脚本中查找包含特定格式的PDF URL
        const pageScripts = document.querySelectorAll('script');
        for (let script of pageScripts) {
            if (script.textContent) {
                // 查找各种可能的PDF URL格式
                const patterns = [
                    /https?:\/\/[^'"]+\.ykt\.cbern\.com\.cn[^'"]+\.pdf/g,
                    /url['"]\s*:\s*['"]([^'"]+\.pdf[^'"]*)['"]/g,
                    /pdfUrl['"]\s*:\s*['"]([^'"]+)['"]/g,
                    /src['"]\s*:\s*['"]([^'"]+\.pdf[^'"]*)['"]/g
                ];
                
                for (let pattern of patterns) {
                    const matches = script.textContent.matchAll(pattern);
                    for (let match of matches) {
                        const url = match[1] || match[0];
                        if (url && url.includes('.pdf') && url.includes('ykt.cbern.com.cn')) {
                            console.log('从脚本中找到:', url);
                            return url;
                        }
                    }
                }
            }
        }
        
        // 方法4: 从localStorage/sessionStorage查找
        try {
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                const value = localStorage.getItem(key);
                if (value && value.includes('.pdf') && value.includes('ykt.cbern.com.cn')) {
                    const urlMatch = value.match(/https?:\/\/[^'"]+\.pdf/);
                    if (urlMatch) {
                        console.log('从localStorage找到:', urlMatch[0]);
                        return urlMatch[0];
                    }
                }
            }
        } catch (e) {}
        
        // 方法5: 从React组件查找
        const reactRoot = document.querySelector('#root');
        if (reactRoot) {
            const fiber = Object.keys(reactRoot).find(key => key.startsWith('__reactFiber'));
            if (fiber) {
                let node = reactRoot[fiber];
                const pdfUrl = searchFiberForPdf(node);
                if (pdfUrl && pdfUrl.includes('.pdf')) {
                    console.log('从React组件找到:', pdfUrl);
                    return pdfUrl;
                }
            }
        }
        
        // 方法6: 从网络请求拦截
        if (window.__capturedPdfUrl) {
            console.log('从拦截的请求找到:', window.__capturedPdfUrl);
            return window.__capturedPdfUrl;
        }
        
        return null;
    }

    // 递归搜索React Fiber树
    function searchFiberForPdf(fiber, depth = 0) {
        if (!fiber || depth > 20) return null;
        
        // 检查memoizedProps
        if (fiber.memoizedProps) {
            const pdfUrl = extractPdfFromProps(fiber.memoizedProps);
            if (pdfUrl) return pdfUrl;
        }
        
        // 检查stateNode
        if (fiber.stateNode && typeof fiber.stateNode === 'object') {
            const pdfUrl = extractPdfFromProps(fiber.stateNode);
            if (pdfUrl) return pdfUrl;
        }
        
        // 递归检查
        const childUrl = searchFiberForPdf(fiber.child, depth + 1);
        if (childUrl) return childUrl;
        
        const siblingUrl = searchFiberForPdf(fiber.sibling, depth + 1);
        if (siblingUrl) return siblingUrl;
        
        return null;
    }

    // 从对象中提取PDF URL
    function extractPdfFromProps(obj, depth = 0) {
        if (!obj || depth > 10) return null;
        
        if (typeof obj === 'string' && obj.includes('.pdf')) {
            return obj;
        }
        
        if (typeof obj === 'object') {
            for (let key in obj) {
                if (obj.hasOwnProperty(key)) {
                    const result = extractPdfFromProps(obj[key], depth + 1);
                    if (result) return result;
                }
            }
        }
        
        return null;
    }

    // 拦截fetch请求
    function interceptRequests() {
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            const url = args[0];
            if (typeof url === 'string' && url.includes('.pdf')) {
                console.log('拦截到PDF请求:', url);
                window.__capturedPdfUrl = url;
            }
            return originalFetch.apply(this, args);
        };
    }

    // 获取文件名
    function getFileName(pdfUrl) {
        let fileName = '';
        
        // 方法1：从PDF URL中提取文件名
        if (pdfUrl) {
            const urlParts = pdfUrl.split('/');
            const lastPart = urlParts[urlParts.length - 1];
            
            // 解码URL编码的文件名
            if (lastPart && lastPart.includes('.pdf')) {
                try {
                    fileName = decodeURIComponent(lastPart);
                    // 去除可能的时间戳
                    fileName = fileName.replace(/_\d{13}\.pdf$/, '.pdf');
                    
                    // 去除常见的前缀
                    fileName = fileName
                        .replace(/^义务教育教科书\s*/, '')
                        .replace(/^义务教育\s*/, '')
                        .replace(/^教科书\s*/, '')
                        .replace(/^普通高中教科书\s*/, '')
                        .replace(/^普通高中\s*/, '')
                        .replace(/^高中教科书\s*/, '')
                        .replace(/^人教版\s*/, '')
                        .replace(/^部编版\s*/, '')
                        .trim();
                    
                    console.log('从URL提取的文件名:', fileName);
                    
                    // 如果文件名合理，直接返回
                    if (fileName && fileName !== '.pdf' && !fileName.includes('手机版')) {
                        return fileName;
                    }
                } catch (e) {
                    console.log('URL解码失败');
                }
            }
        }
        
        // 方法2：从页面获取教材信息
        // 查找包含教材名称的元素
        const selectors = [
            'h1',
            '.resource-title',
            '.content-title',
            '[class*="title"]:not([class*="nav"]):not([class*="menu"])',
            '.book-name',
            '.material-name'
        ];
        
        for (let selector of selectors) {
            const elements = document.querySelectorAll(selector);
            for (let element of elements) {
                const text = element.textContent?.trim();
                if (text && text.length > 2 && text.length < 100) {
                    // 检查是否包含教材相关关键词
                    if (text.includes('教材') || text.includes('课本') || 
                        text.includes('年级') || text.includes('上册') || 
                        text.includes('下册') || /[一二三四五六七八九]年级/.test(text)) {
                        fileName = text;
                        console.log('从页面元素提取:', fileName);
                        break;
                    }
                }
            }
            if (fileName) break;
        }
        
        // 方法3：从页面标题获取
        if (!fileName || fileName === '手机版') {
            fileName = document.title;
            // 去除常见的网站后缀
            fileName = fileName.replace(/[-_].*?(智慧教育|教育平台|中小学).*$/g, '');
            console.log('从页面标题提取:', fileName);
        }
        
        // 清理文件名 - 再次去除可能在其他地方出现的前缀
        fileName = fileName
            .replace(/^义务教育教科书\s*/, '')
            .replace(/^义务教育\s*/, '')
            .replace(/^教科书\s*/, '')
            .replace(/^普通高中教科书\s*/, '')
            .replace(/^普通高中\s*/, '')
            .replace(/[\/\\:*?"<>|]/g, '_')  // 替换非法字符
            .replace(/\s+/g, '_')             // 替换空格为下划线
            .replace(/_{2,}/g, '_')           // 合并多个下划线
            .replace(/^_|_$/g, '')            // 去除首尾下划线
            .trim();
        
        // 如果还是没有合适的名称，使用默认名称
        if (!fileName || fileName === '手机版' || fileName.length < 2) {
            const date = new Date().toLocaleDateString('zh-CN').replace(/\//g, '-');
            fileName = `教材_${date}`;
        }
        
        // 确保有.pdf扩展名
        if (!fileName.endsWith('.pdf')) {
            fileName += '.pdf';
        }
        
        console.log('最终文件名:', fileName);
        return fileName;
    }

    // 下载PDF的多种方法
    async function downloadPdf(pdfUrl, fileName) {
        const statusDiv = document.querySelector('#download-status');
        const downloadBtn = document.querySelector('#download-btn');
        
        statusDiv.style.display = 'block';
        downloadBtn.disabled = true;
        
        // 方法1: 使用GM_download（如果URL可直接访问）
        try {
            statusDiv.innerHTML = '<span style="color: #2196F3;">正在尝试方法1：直接下载...</span>';
            
            GM_download({
                url: pdfUrl,
                name: fileName,
                saveAs: true,
                onload: function() {
                    statusDiv.innerHTML = '<span style="color: #4CAF50;">✓ 下载成功！</span>';
                    downloadBtn.disabled = false;
                },
                onerror: function(error) {
                    console.log('方法1失败:', error);
                    // 尝试方法2
                    downloadMethod2(pdfUrl, fileName);
                }
            });
        } catch (e) {
            console.log('GM_download不可用，尝试其他方法');
            downloadMethod2(pdfUrl, fileName);
        }
    }

    // 方法2: 使用fetch获取数据
    async function downloadMethod2(pdfUrl, fileName) {
        const statusDiv = document.querySelector('#download-status');
        const downloadBtn = document.querySelector('#download-btn');
        
        statusDiv.innerHTML = '<span style="color: #2196F3;">正在尝试方法2：通过代理下载...</span>';
        
        // 获取认证信息
        const authKey = Object.keys(localStorage).find(key => key.startsWith("ND_UC_AUTH"));
        let accessToken = null;
        if (authKey) {
            try {
                const tokenData = JSON.parse(localStorage.getItem(authKey));
                accessToken = JSON.parse(tokenData.value).access_token;
            } catch (e) {}
        }
        
        // 使用页面中找到的headers或构建新的
        let headers = {
            'Referer': window.location.href,
            'User-Agent': navigator.userAgent
        };
        
        // 如果从iframe中提取到了headers，优先使用
        if (window.__pdfHeaders) {
            headers = { ...headers, ...window.__pdfHeaders };
            console.log('使用页面提取的headers');
        } else if (accessToken) {
            headers['X-ND-AUTH'] = `MAC id="${accessToken}",nonce="0",mac="0"`;
            console.log('使用localStorage的token');
        }
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: pdfUrl,
            responseType: 'blob',
            headers: headers,
            onprogress: function(e) {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    statusDiv.innerHTML = `<span style="color: #2196F3;">下载中: ${percent}%</span>`;
                }
            },
            onload: function(response) {
                if (response.status === 200) {
                    // 检查是否真的是PDF
                    const blob = response.response;
                    if (blob.type === 'application/pdf' || blob.size > 1000000) { // PDF或大于1MB的文件
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = fileName;
                        a.click();
                        window.URL.revokeObjectURL(url);
                        
                        statusDiv.innerHTML = '<span style="color: #4CAF50;">✓ 下载成功！</span>';
                        downloadBtn.disabled = false;
                    } else {
                        // 可能是错误页面
                        statusDiv.innerHTML = '<span style="color: #f44336;">✗ 下载的不是PDF文件</span>';
                        downloadMethod3(pdfUrl, fileName);
                    }
                } else {
                    // 尝试方法3
                    downloadMethod3(pdfUrl, fileName);
                }
            },
            onerror: function() {
                // 尝试方法3
                downloadMethod3(pdfUrl, fileName);
            }
        });
    }

    // 方法3: 通过iframe下载
    function downloadMethod3(pdfUrl, fileName) {
        const statusDiv = document.querySelector('#download-status');
        const downloadBtn = document.querySelector('#download-btn');
        
        statusDiv.innerHTML = '<span style="color: #2196F3;">正在尝试方法3：iframe下载...</span>';
        
        try {
            // 创建隐藏的iframe
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = pdfUrl;
            document.body.appendChild(iframe);
            
            // 等待加载后尝试保存
            iframe.onload = function() {
                try {
                    // 尝试触发下载
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                    if (iframeDoc.querySelector('embed, object')) {
                        statusDiv.innerHTML = '<span style="color: #4CAF50;">✓ PDF已在新窗口打开，请手动保存</span>';
                    }
                } catch (e) {
                    statusDiv.innerHTML = '<span style="color: #FF9800;">⚠ 请在打开的新窗口中手动保存PDF</span>';
                }
                downloadBtn.disabled = false;
                
                // 清理iframe
                setTimeout(() => {
                    document.body.removeChild(iframe);
                }, 3000);
            };
            
            // 同时打开新窗口作为备选
            window.open(pdfUrl, '_blank');
            
        } catch (e) {
            statusDiv.innerHTML = '<span style="color: #f44336;">✗ 下载失败，请尝试手动下载</span>';
            downloadBtn.disabled = false;
        }
    }

    // 获取Access Token
    function getAccessToken() {
        const authKey = Object.keys(localStorage).find(key => key.startsWith("ND_UC_AUTH"));
        if (!authKey) {
            console.log('未找到认证信息');
            return null;
        }
        
        try {
            const tokenData = JSON.parse(localStorage.getItem(authKey));
            const accessToken = JSON.parse(tokenData.value).access_token;
            console.log('成功获取Access Token');
            return accessToken;
        } catch (e) {
            console.error('解析Token失败:', e);
            return null;
        }
    }

    // 获取当前页面的信息
    function getPageInfo() {
        const info = {
            url: window.location.href,
            contentId: null,
            contentType: null
        };
        
        // 从URL中提取参数
        const urlParams = new URLSearchParams(window.location.search);
        info.contentId = urlParams.get('contentId');
        info.contentType = urlParams.get('contentType') || 'assets_document';
        
        return info;
    }

    // 主函数
    function init() {
        interceptRequests();
        const container = createUI();
        const infoDiv = container.querySelector('#pdf-info');
        const extractBtn = container.querySelector('#extract-btn');
        const urlText = container.querySelector('#pdf-url-text');
        const copyBtn = container.querySelector('#copy-url-btn');
        const downloadBtn = container.querySelector('#download-btn');
        
        // Token相关元素
        const tokenInfoDiv = container.querySelector('#token-info');
        const tokenText = container.querySelector('#token-text');
        const copyTokenBtn = container.querySelector('#copy-token-btn');
        
        // 获取并显示Token
        const accessToken = getAccessToken();
        if (accessToken) {
            tokenInfoDiv.textContent = '已找到Access Token';
            tokenInfoDiv.style.color = '#4CAF50';
            tokenText.value = accessToken;
            tokenText.style.display = 'block';
            copyTokenBtn.style.display = 'block';
            
            copyTokenBtn.onclick = () => {
                GM_setClipboard(accessToken);
                copyTokenBtn.textContent = '已复制!';
                setTimeout(() => {
                    copyTokenBtn.textContent = '复制Token';
                }, 2000);
            };
        } else {
            tokenInfoDiv.textContent = '未找到Token，请先登录';
            tokenInfoDiv.style.color = '#f44336';
        }
        
        // 显示页面信息
        const pageInfo = getPageInfo();
        console.log('页面信息:', pageInfo);
        
        let currentPdfUrl = null;
        let checkCount = 0;
        const maxChecks = 30;
        
        const checkInterval = setInterval(() => {
            checkCount++;
            
            const pdfUrl = findPdfUrl();
            
            if (pdfUrl) {
                clearInterval(checkInterval);
                currentPdfUrl = pdfUrl;
                infoDiv.textContent = '已找到PDF资源！';
                infoDiv.style.color = '#4CAF50';
                extractBtn.style.display = 'block';
                
                extractBtn.onclick = () => {
                    // 显示找到的URL
                    console.log('提取到的PDF URL:', pdfUrl);
                    urlText.value = pdfUrl;
                    urlText.style.display = 'block';
                    copyBtn.style.display = 'block';
                    downloadBtn.style.display = 'block';
                    
                    // 在状态区显示URL类型和页面信息
                    const urlInfo = document.createElement('div');
                    urlInfo.style.cssText = 'font-size: 11px; color: #666; margin-top: 5px; word-break: break-all;';
                    urlInfo.innerHTML = `
                        URL类型: ${pdfUrl.includes('-private') ? '私有链接' : '公开链接'}<br>
                        ContentId: ${pageInfo.contentId || '未知'}<br>
                        ContentType: ${pageInfo.contentType || '未知'}
                    `;
                    urlText.parentNode.insertBefore(urlInfo, urlText.nextSibling);
                };
                
                copyBtn.onclick = () => {
                    // 生成带有完整信息的JSON
                    const downloadInfo = {
                        contentId: pageInfo.contentId,
                        contentType: pageInfo.contentType,
                        pageUrl: pageInfo.url,
                        pdfUrl: currentPdfUrl,
                        title: getFileName(currentPdfUrl).replace('.pdf', ''),
                        accessToken: accessToken || null
                    };
                    
                    // 复制JSON到剪贴板
                    GM_setClipboard(JSON.stringify(downloadInfo, null, 2));
                    copyBtn.textContent = '已复制完整信息!';
                    setTimeout(() => {
                        copyBtn.textContent = '复制链接';
                    }, 2000);
                };
                
                downloadBtn.onclick = () => {
                    const fileName = getFileName(currentPdfUrl);
                    downloadPdf(currentPdfUrl, fileName);
                };
                
                // 自动点击提取按钮
                setTimeout(() => {
                    extractBtn.click();
                }, 500);
                
            } else if (checkCount >= maxChecks) {
                clearInterval(checkInterval);
                infoDiv.textContent = '未找到PDF资源';
                infoDiv.style.color = '#f44336';
            } else {
                infoDiv.textContent = `正在查找PDF... (${checkCount}/${maxChecks})`;
            }
        }, 1000);
    }

    // 等待页面加载完成后初始化
    if (document.readyState === 'complete') {
        setTimeout(init, 1000);
    } else {
        window.addEventListener('load', () => {
            setTimeout(init, 1000);
        });
    }

})();
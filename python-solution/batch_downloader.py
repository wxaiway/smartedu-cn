#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合版批量下载器 - 精简且功能完整的单一版本
整合了enhanced、multimedia_enhanced和unified的核心功能
移除了无用的FFmpeg视频下载功能
"""

import json
import os
import sys
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import logging
from tqdm import tqdm
import threading
import random
from typing import Dict, List, Optional

class IntegrityChecker:
    """文件完整性检查器"""
    def __init__(self, mode: str = 'smart', session: requests.Session = None):
        """
        mode: 
        - 'strict': 总是进行网络验证
        - 'local': 只检查本地文件存在性
        - 'smart': 智能模式，基于文件大小和时间判断
        """
        self.mode = mode
        self.session = session or requests.Session()
        self.logger = logging.getLogger(__name__)
        
    def check_file_integrity(self, file_path: Path, url: str = None) -> tuple[bool, str]:
        """检查文件完整性
        返回: (是否完整, 原因)
        """
        # 文件不存在
        if not file_path.exists():
            return False, "文件不存在"
            
        file_size = file_path.stat().st_size
        
        # local模式：只检查文件存在和基本大小
        if self.mode == 'local':
            if file_size < 1024:  # 小于1KB认为不完整
                return False, f"文件过小: {file_size} bytes"
            return True, "本地检查通过"
            
        # smart模式：智能判断
        elif self.mode == 'smart':
            # 检查文件类型和大小
            if file_path.suffix == '.pdf':
                # PDF文件检查
                if file_size < 10 * 1024:  # 小于10KB
                    return False, f"PDF文件过小: {file_size} bytes"
                    
                # 快速检查PDF文件头
                try:
                    with open(file_path, 'rb') as f:
                        header = f.read(5)
                        if header != b'%PDF-':
                            return False, "无效的PDF文件头"
                        
                        # 检查PDF结尾（快速定位到文件末尾）
                        f.seek(-1024, 2)  # 从文件末尾前1KB开始
                        tail = f.read()
                        if b'%%EOF' not in tail:
                            return False, "PDF文件可能不完整（缺少EOF标记）"
                            
                except Exception as e:
                    return False, f"读取文件失败: {e}"
                    
                return True, "智能检查通过"
                
            elif file_path.suffix in ['.mp3', '.m4a']:
                # 音频文件检查
                if file_size < 5 * 1024:  # 小于5KB
                    return False, f"音频文件过小: {file_size} bytes"
                    
                # 检查MP3文件头
                if file_path.suffix == '.mp3':
                    try:
                        with open(file_path, 'rb') as f:
                            header = f.read(3)
                            # MP3文件可能以ID3标签开始，或直接是帧同步
                            if header[:3] != b'ID3' and header[:2] != b'\xff\xfb':
                                # 继续检查是否是有效的MP3
                                f.seek(0)
                                data = f.read(min(4096, file_size))
                                # 查找MP3帧同步标志
                                if b'\xff\xfb' not in data and b'\xff\xfa' not in data:
                                    return False, "无效的MP3文件格式"
                    except Exception as e:
                        return False, f"读取音频文件失败: {e}"
                        
                return True, "智能检查通过"
                
            else:
                # 其他文件类型，只检查大小
                if file_size < 100:  # 小于100字节
                    return False, f"文件过小: {file_size} bytes"
                return True, "智能检查通过"
                
        # strict模式：进行网络验证
        elif self.mode == 'strict' and url:
            try:
                self.logger.debug(f"执行严格检查: {file_path.name}")
                head_resp = self.session.head(url, timeout=10)
                head_resp.raise_for_status()
                
                remote_size = int(head_resp.headers.get('Content-Length', 0))
                
                if remote_size == 0:
                    # 服务器未返回文件大小，退回到智能检查
                    return self._fallback_to_smart_check(file_path)
                    
                if file_size != remote_size:
                    return False, f"文件大小不匹配: 本地={file_size}, 远程={remote_size}"
                    
                return True, "严格检查通过"
                
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"网络检查失败，退回到智能检查: {e}")
                # 网络失败时退回到智能检查
                return self._fallback_to_smart_check(file_path)
                
        # 默认通过
        return True, "检查通过"
        
    def _fallback_to_smart_check(self, file_path: Path) -> tuple[bool, str]:
        """退回到智能检查模式"""
        original_mode = self.mode
        self.mode = 'smart'
        result = self.check_file_integrity(file_path)
        self.mode = original_mode
        return result

class RateLimiter:
    """请求限流器"""
    def __init__(self, requests_per_second: float = 2.0, enabled: bool = True):
        self.rate = requests_per_second
        self.enabled = enabled
        self.last_request = 0
        self.lock = threading.Lock()
        
    def wait_if_needed(self):
        """确保请求不超过限制"""
        if not self.enabled:
            return
            
        with self.lock:
            now = time.time()
            time_since_last = now - self.last_request
            min_interval = 1.0 / self.rate
            if time_since_last < min_interval:
                time.sleep(min_interval - time_since_last)
            self.last_request = time.time()

class IntegratedBatchDownloader:
    def __init__(self, token, tasks_file="download_tasks.json", max_workers=3, output_dir=None, 
                 retry_failed=False, enable_multimedia=True, enable_retry=True, 
                 rate_limit=2.0, enable_ratelimit=True, integrity_mode='smart'):
        self.token = token
        self.tasks_file = Path(tasks_file)
        self.max_workers = max_workers
        self.output_dir = Path(output_dir) if output_dir else Path("教材库")
        self.retry_failed = retry_failed
        self.enable_multimedia = enable_multimedia
        self.enable_retry = enable_retry
        self.max_retries = 3
        self.session = requests.Session()
        
        # 设置请求头
        self.headers = {
            "X-ND-AUTH": f'MAC id="{token}",nonce="0",mac="0"',
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br"
        }
        self.session.headers.update(self.headers)
        
        # 速率限制
        self.rate_limiter = RateLimiter(requests_per_second=rate_limit, enabled=enable_ratelimit)
        
        # 完整性检查器
        self.integrity_checker = IntegrityChecker(mode=integrity_mode, session=self.session)
        self.integrity_mode = integrity_mode
        
        # CDN节点列表
        self.cdn_nodes = [
            "r1-ndr-private.ykt.cbern.com.cn",
            "r2-ndr-private.ykt.cbern.com.cn",
            "r3-ndr-private.ykt.cbern.com.cn"
        ]
        
        # 下载统计
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "multimedia": 0,
            "videos_downloaded": 0,
            "videos_skipped_drm": 0,
            "audios_downloaded": 0,
            "retry_count": 0,
            "cdn_switch_count": 0,
            "start_time": None,
            "end_time": None
        }
        
        # 失败记录
        self.failed_tasks = []
        
        # 多媒体资源记录
        self.multimedia_resources = []
        
        # 资源类型映射
        self.resource_type_mapping = {
            "assets_video": "视频",
            "assets_audio": "音频",
            "assets_image": "图片",
            "assets_document": "文档"
        }
        
        # 设置日志
        self.setup_logging()
        
    def setup_logging(self):
        """设置日志"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_tasks(self):
        """加载任务列表"""
        if self.retry_failed:
            # 从失败任务文件加载
            failed_file = Path("failed_tasks.json")
            if not failed_file.exists():
                self.logger.error("失败任务文件不存在: failed_tasks.json")
                sys.exit(1)
            
            with open(failed_file, "r", encoding="utf-8") as f:
                failed_data = json.load(f)
            
            # 提取失败任务中的task对象
            self.tasks = [item["task"] for item in failed_data]
            self.stats["total"] = len(self.tasks)
            self.logger.info(f"加载了 {self.stats['total']} 个失败任务进行重试")
        else:
            # 从正常任务文件加载
            if not self.tasks_file.exists():
                self.logger.error(f"任务文件不存在: {self.tasks_file}")
                sys.exit(1)
                
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.tasks = data.get("tasks", [])
            self.stats["total"] = len(self.tasks)
            self.logger.info(f"加载了 {self.stats['total']} 个下载任务")
            
    def is_thematic_course(self, task):
        """判断是否是专题课程"""
        page_url = task.get("page_url", "")
        return "contentType=thematic_course" in page_url
        
    def get_thematic_resources(self, task):
        """获取专题课程的资源列表"""
        content_id = task["content_id"]
        resources_url = f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/special_edu/thematic_course/{content_id}/resources/list.json"
        
        try:
            self.rate_limiter.wait_if_needed()
            resp = self.session.get(resources_url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"获取专题课程资源失败: {task['id']} - {e}")
            return None
            
    def get_pdf_url(self, task):
        """获取PDF下载URL"""
        # 检查是否是专题课程
        if self.is_thematic_course(task):
            return self.get_thematic_pdf_url(task)
        else:
            return self.get_normal_pdf_url(task)
            
    def get_normal_pdf_url(self, task):
        """获取普通教材的PDF URL并检查音频资源"""
        api_url = task["api_url"]
        
        try:
            self.rate_limiter.wait_if_needed()
            # 获取资源详情
            resp = self.session.get(api_url, timeout=30)
            resp.raise_for_status()
            
            data = resp.json()
            
            pdf_url = None
            
            # 查找PDF资源
            for item in data.get("ti_items", []):
                if item.get("lc_ti_format") == "pdf":
                    pdf_urls = item.get("ti_storages", [])
                    if pdf_urls:
                        pdf_url = pdf_urls[0]
                        break
                        
            # 检查热区数据中的音频资源（仅在启用多媒体时）
            if self.enable_multimedia:
                self.extract_audio_from_hot_zone(task, data)
            
            if not pdf_url:
                self.logger.warning(f"未找到PDF资源: {task['id']} - {task['original_title']}")
            
            return pdf_url
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"获取资源详情失败: {task['id']} - {e}")
            return None
        except json.JSONDecodeError:
            self.logger.error(f"解析JSON失败: {task['id']}")
            return None
            
    def extract_audio_from_hot_zone(self, task, resource_data):
        """从热区数据中提取音频资源"""
        try:
            # 查找热区数据
            hot_zone_url = None
            for item in resource_data.get("ti_items", []):
                if item.get("ti_file_flag") == "hot_zone":
                    hot_zone_storages = item.get("ti_storages", [])
                    if hot_zone_storages:
                        hot_zone_url = hot_zone_storages[0]
                        break
                        
            if not hot_zone_url:
                return
                
            self.rate_limiter.wait_if_needed()
                
            # 下载热区数据
            hot_zone_resp = self.session.get(hot_zone_url, timeout=30)
            hot_zone_resp.raise_for_status()
            hot_zone_data = hot_zone_resp.text
            
            # 尝试解析JSON格式的热区数据
            audio_list = []
            try:
                # 热区数据通常是JSON数组
                hot_zone_json = json.loads(hot_zone_data)
                if isinstance(hot_zone_json, list):
                    for item in hot_zone_json:
                        if "audio_src" in item and "audio_name" in item:
                            audio_list.append({
                                "url": item["audio_src"],
                                "name": item["audio_name"],
                                "page": item.get("current_page", 0),
                                "hotzone_number": item.get("hotzone_number", ""),
                                "audio_id": item.get("audio_id", "")
                            })
            except json.JSONDecodeError:
                # 如果不是JSON，尝试正则提取
                mp3_pattern = r'https?://[^\s"]+\.mp3'
                mp3_urls = re.findall(mp3_pattern, hot_zone_data)
                for i, url in enumerate(mp3_urls):
                    audio_list.append({
                        "url": url,
                        "name": f"音频_{i+1}",
                        "page": 0,
                        "hotzone_number": f"AUDIO-{i+1}",
                        "audio_id": ""
                    })
            
            if audio_list:
                self.logger.info(f"从热区数据中发现 {len(audio_list)} 个音频文件")
                
                # 构建音频资源列表
                multimedia_resources = {
                    "videos": [],
                    "audios": [],
                    "images": []
                }
                
                for audio in audio_list:
                    audio_info = {
                        "title": audio["name"],
                        "url": audio["url"],
                        "format": "mp3",
                        "source": "hot_zone",
                        "page": audio["page"],
                        "hotzone_number": audio["hotzone_number"],
                        "audio_id": audio["audio_id"]
                    }
                    multimedia_resources["audios"].append(audio_info)
                
                # 下载音频资源
                if multimedia_resources["audios"]:
                    self.download_multimedia_resources(task, multimedia_resources)
                    
                    # 记录多媒体资源
                    self.multimedia_resources.append({
                        "task": task,
                        "multimedia": multimedia_resources
                    })
                    
        except Exception as e:
            self.logger.error(f"解析热区数据失败 [{task['id']}]: {e}")
            
    def check_m3u8_drm(self, m3u8_url):
        """检查M3U8是否有DRM加密"""
        try:
            self.rate_limiter.wait_if_needed()
            
            # 下载m3u8文件内容
            resp = self.session.get(m3u8_url, timeout=10)
            resp.raise_for_status()
            m3u8_content = resp.text
            
            # 检查是否包含加密信息
            has_encryption = "#EXT-X-KEY" in m3u8_content
            
            # 进一步检查是否是DRM
            has_drm = False
            if has_encryption:
                # 检查密钥URL是否是DRM服务器
                if "ndvideo-key.ykt.eduyun.cn" in m3u8_content:
                    has_drm = True
                    
            return has_drm
            
        except Exception as e:
            self.logger.error(f"检查M3U8加密失败: {e}")
            # 保守起见，如果检查失败，假设有DRM
            return True
            
    def get_thematic_pdf_url(self, task):
        """获取专题课程的PDF URL并处理多媒体资源"""
        resources = self.get_thematic_resources(task)
        if not resources:
            return None
            
        # 查找资源
        pdf_url = None
        multimedia_resources = {
            "videos": [],
            "audios": [],
            "images": []
        }
        
        for resource in resources:
            resource_type = resource.get("resource_type_code", "")
            resource_title = resource.get("title", "未知资源")
            
            # 处理视频资源（检查DRM）
            if resource_type == "assets_video" and self.enable_multimedia:
                for item in resource.get("ti_items", []):
                    # 检查是否有加密标记
                    custom_props = item.get("custom_properties", {})
                    has_drm = custom_props.get("encryption") == "drm"
                    
                    video_format = item.get("lc_ti_format", "")
                    if video_format in ["mp4", "video/mp4", "m3u8", "video/m3u8"]:
                        video_storages = item.get("ti_storages", [])
                        if video_storages:
                            video_url = video_storages[0]
                            actual_format = "m3u8" if "m3u8" in video_format else "mp4"
                            
                            # 如果是m3u8，进一步检查DRM
                            if actual_format == "m3u8" and not has_drm:
                                has_drm = self.check_m3u8_drm(video_url)
                                
                            video_info = {
                                "title": resource_title,
                                "resource_id": resource.get("id"),
                                "url": video_url,
                                "format": actual_format,
                                "has_drm": has_drm
                            }
                            multimedia_resources["videos"].append(video_info)
                            break
            
            # 处理音频资源
            elif resource_type == "assets_audio" and self.enable_multimedia:
                for item in resource.get("ti_items", []):
                    audio_format = item.get("lc_ti_format", "")
                    if audio_format in ["mp3", "audio/mp3", "wav", "m4a"]:
                        audio_storages = item.get("ti_storages", [])
                        if audio_storages:
                            audio_info = {
                                "title": resource_title,
                                "resource_id": resource.get("id"),
                                "url": audio_storages[0],
                                "format": audio_format.replace("audio/", "")
                            }
                            multimedia_resources["audios"].append(audio_info)
                            break
            
            # 处理PDF文档
            elif resource_type == "assets_document" and not pdf_url:
                for item in resource.get("ti_items", []):
                    if item.get("lc_ti_format") == "pdf":
                        pdf_storages = item.get("ti_storages", [])
                        if pdf_storages:
                            pdf_url = pdf_storages[0]
                            break
        
        # 下载多媒体资源（仅在启用时）
        if self.enable_multimedia and any(multimedia_resources.values()):
            self.download_multimedia_resources(task, multimedia_resources)
        
        # 记录多媒体资源信息
        if any(multimedia_resources.values()):
            self.multimedia_resources.append({
                "task": task,
                "multimedia": multimedia_resources
            })
            total_multimedia = sum(len(resources) for resources in multimedia_resources.values())
            self.logger.info(f"发现 {total_multimedia} 个多媒体资源: {task['original_title']}")
            
        if not pdf_url:
            self.logger.warning(f"专题课程未找到PDF: {task['id']} - {task['original_title']}")
            
        return pdf_url
            
    def extract_cdn_node(self, url):
        """从URL中提取CDN节点"""
        match = re.search(r'(r[1-3]-ndr-private\.ykt\.cbern\.com\.cn)', url)
        return match.group(1) if match else "unknown"
        
    def generate_cdn_urls(self, original_url):
        """生成所有可能的CDN URL列表"""
        # 如果URL不包含CDN节点，直接返回原始URL
        if not any(cdn in original_url for cdn in self.cdn_nodes):
            return [original_url]
        
        urls = [original_url]
        current_cdn = self.extract_cdn_node(original_url)
        
        # 生成其他CDN节点的URL
        for cdn_node in self.cdn_nodes:
            if cdn_node != current_cdn and current_cdn != "unknown":
                alternative_url = original_url.replace(current_cdn, cdn_node)
                urls.append(alternative_url)
        
        return urls
        
    def download_file_with_retry(self, url, save_path, task_id):
        """带重试机制的文件下载，支持CDN切换"""
        max_retries = self.max_retries if self.enable_retry else 1
        last_error = None
        urls_to_try = self.generate_cdn_urls(url)
        
        for url_to_try in urls_to_try:
            for attempt in range(max_retries):
                try:
                    # 指数退避策略（仅在启用重试时）
                    if attempt > 0 and self.enable_retry:
                        delay = min(2 ** attempt + random.uniform(0, 1), 30)
                        self.logger.info(f"[{task_id}] 第{attempt+1}次重试，等待{delay:.1f}秒...")
                        time.sleep(delay)
                        self.stats["retry_count"] += 1
                    
                    # 添加限流
                    self.rate_limiter.wait_if_needed()
                    
                    # 如果切换了CDN，记录日志
                    if url_to_try != url:
                        self.logger.info(f"[{task_id}] 尝试切换CDN: {self.extract_cdn_node(url_to_try)}")
                    
                    result = self.download_file(url_to_try, save_path, task_id)
                    
                    if result in ["success", "skipped"]:
                        if url_to_try != url:
                            self.logger.info(f"[{task_id}] CDN切换成功: {self.extract_cdn_node(url)} -> {self.extract_cdn_node(url_to_try)}")
                            self.stats["cdn_switch_count"] += 1
                        return result
                        
                    last_error = "下载失败"
                        
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    
                    if attempt == max_retries - 1:
                        self.logger.warning(f"[{task_id}] CDN {self.extract_cdn_node(url_to_try)} 失败: {e}")
                    else:
                        self.logger.warning(f"[{task_id}] 下载失败，准备重试: {e}")
        
        self.logger.error(f"[{task_id}] 所有CDN节点均失败，最后错误: {last_error}")
        return "failed"
        
    def download_file(self, url, save_path, task_id):
        """下载文件"""
        try:
            # 确保目录存在
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用完整性检查器检查文件
            if save_path.exists():
                is_complete, reason = self.integrity_checker.check_file_integrity(save_path, url)
                if is_complete:
                    self.logger.info(f"文件已存在且完整，跳过: {save_path.name} ({reason})")
                    return "skipped"
                else:
                    self.logger.info(f"文件存在但不完整，重新下载: {save_path.name} ({reason})")
                    
            # 下载文件
            resp = self.session.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            
            # 获取文件大小
            total_size = int(resp.headers.get('Content-Length', 0))
            
            # 写入文件
            temp_path = save_path.with_suffix('.tmp')
            downloaded = 0
            
            with open(temp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
            # 验证下载
            if total_size > 0 and downloaded != total_size:
                temp_path.unlink()
                raise Exception(f"下载不完整: {downloaded}/{total_size}")
                
            # 重命名临时文件
            temp_path.rename(save_path)
            
            self.logger.info(f"下载成功: {save_path.name} ({self.format_size(downloaded)})")
            return "success"
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"下载失败 [{task_id}]: {e}")
            return "failed"
        except Exception as e:
            self.logger.error(f"下载出错 [{task_id}]: {e}")
            return "failed"
            
    def format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def sanitize_filename(self, filename):
        """清理文件名，移除非法字符"""
        # 移除或替换非法字符
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        # 移除首尾空格和点
        filename = filename.strip('. ')
        # 限制长度
        if len(filename) > 100:
            filename = filename[:100]
        return filename
    
    def get_multimedia_save_path(self, task, resource_type, resource_info, index):
        """获取多媒体资源的保存路径"""
        # 获取PDF的保存路径
        original_path = Path(task["save_path"])
        if original_path.parts[0] == "教材库":
            pdf_path = self.output_dir / Path(*original_path.parts[1:])
        else:
            pdf_path = self.output_dir / original_path
        
        # 获取PDF文件名（不含扩展名）
        pdf_stem = pdf_path.stem
        
        # 构建多媒体资源目录
        resource_subdir = self.resource_type_mapping.get(resource_type, "其他")
        base_multimedia_dir = pdf_path.parent / f"{pdf_stem}_{resource_subdir}"
        
        # 对于音频资源，尝试解析单元和课程信息
        if resource_type == "assets_audio" and isinstance(resource_info, dict):
            title = resource_info.get("title", "")
            hotzone_number = resource_info.get("hotzone_number", "")
            
            # 尝试从title中解析单元和课程信息
            # 示例: "Unit 1_Lesson 1_1 Listen, read and find out."
            parts = title.split("_")
            if len(parts) >= 2:
                unit_part = parts[0].strip()  # "Unit 1"
                lesson_part = parts[1].strip()  # "Lesson 1"
                content_part = "_".join(parts[2:]).strip() if len(parts) > 2 else title
                
                # 创建目录结构
                multimedia_dir = base_multimedia_dir / unit_part / lesson_part
                
                # 使用热区编号和内容作为文件名
                if hotzone_number:
                    filename = f"{hotzone_number}_{self.sanitize_filename(content_part)}.mp3"
                else:
                    filename = f"{index:02d}_{self.sanitize_filename(content_part)}.mp3"
            else:
                # 如果无法解析，使用原始方式
                multimedia_dir = base_multimedia_dir
                if hotzone_number:
                    filename = f"{hotzone_number}_{self.sanitize_filename(title)}.mp3"
                else:
                    filename = f"{index:02d}_{self.sanitize_filename(title)}.mp3"
        else:
            # 非音频资源或简单字符串标题
            multimedia_dir = base_multimedia_dir
            if isinstance(resource_info, dict):
                title = resource_info.get("title", f"资源_{index}")
                format_str = resource_info.get("format", "unknown")
            else:
                title = resource_info
                format_str = "unknown"
            
            clean_title = self.sanitize_filename(title)
            filename = f"{index:02d}_{clean_title}.{format_str}"
        
        return multimedia_dir / filename
    
    def download_multimedia_resources(self, task, multimedia_resources):
        """下载多媒体资源"""
        # 下载视频（跳过DRM加密的）
        for index, video in enumerate(multimedia_resources.get("videos", []), 1):
            if video.get("has_drm", False):
                self.logger.warning(f"跳过DRM加密视频: {video['title']}")
                self.stats["videos_skipped_drm"] += 1
                continue
                
            if video["format"] == "mp4":
                save_path = self.get_multimedia_save_path(
                    task, "assets_video", video, index
                )
                result = self.download_file_with_retry(video["url"], save_path, f"{task['id']}_video_{index}")
                if result == "success":
                    self.stats["videos_downloaded"] += 1
                elif result == "skipped":
                    self.stats["videos_downloaded"] += 1
        
        # 下载音频（包括MP3）
        for index, audio in enumerate(multimedia_resources.get("audios", []), 1):
            save_path = self.get_multimedia_save_path(
                task, "assets_audio", audio, index
            )
            result = self.download_file_with_retry(audio["url"], save_path, f"{task['id']}_audio_{index}")
            if result == "success":
                self.stats["audios_downloaded"] += 1
            elif result == "skipped":
                self.stats["audios_downloaded"] += 1
                
    def process_task(self, task):
        """处理单个下载任务"""
        task_id = task["id"]
        
        try:
            # 先构建保存路径
            original_path = Path(task["save_path"])
            if original_path.parts[0] == "教材库":
                save_path = self.output_dir / Path(*original_path.parts[1:])
            else:
                save_path = self.output_dir / original_path
            
            # 提前检查PDF文件是否已存在且完整
            if save_path.exists():
                # 对于smart和local模式，直接使用本地检查
                if self.integrity_mode in ['smart', 'local']:
                    is_complete, reason = self.integrity_checker.check_file_integrity(save_path)
                    if is_complete:
                        self.logger.info(f"PDF文件已存在且完整，跳过任务: {save_path.name} ({reason})")
                        
                        # 如果不需要下载多媒体，直接返回跳过
                        if not self.enable_multimedia:
                            return "skipped"
                        
                        # 如果需要多媒体但是专题课程，仍需要获取资源列表
                        if not self.is_thematic_course(task):
                            # 普通教材且PDF已存在，跳过整个任务
                            return "skipped"
            
            # 获取PDF URL（对于需要下载或检查多媒体的情况）
            pdf_url = self.get_pdf_url(task)
            if not pdf_url:
                # 检查是否是专题课程且有多媒体资源
                if self.is_thematic_course(task) and any(
                    mr["task"]["id"] == task_id for mr in self.multimedia_resources
                ):
                    self.stats["multimedia"] += 1
                    return "multimedia"
                else:
                    self.failed_tasks.append({
                        "task": task,
                        "error": "无法获取PDF URL"
                    })
                    return "failed"
            
            # 对于strict模式，在download_file_with_retry中会进行网络检查
            # 设置Referer
            self.session.headers["Referer"] = task["page_url"]
            
            # 下载文件
            result = self.download_file_with_retry(pdf_url, save_path, task_id)
            
            if result == "failed":
                self.failed_tasks.append({
                    "task": task,
                    "error": "下载失败",
                    "pdf_url": pdf_url
                })
                
            return result
            
        except Exception as e:
            self.logger.error(f"处理任务失败 [{task_id}]: {e}")
            self.failed_tasks.append({
                "task": task,
                "error": str(e)
            })
            return "failed"
            
    def download_batch(self, tasks_subset=None):
        """批量下载"""
        tasks_to_download = tasks_subset or self.tasks
        total_tasks = len(tasks_to_download)
        
        self.logger.info(f"开始下载 {total_tasks} 个文件，使用 {self.max_workers} 个线程")
        self.stats["start_time"] = datetime.now()
        
        # 创建进度条
        with tqdm(total=total_tasks, desc="下载进度", unit="个") as pbar:
            # 使用线程池下载
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交任务
                future_to_task = {
                    executor.submit(self.process_task, task): task 
                    for task in tasks_to_download
                }
                
                # 处理完成的任务
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result()
                        if result == "success":
                            self.stats["success"] += 1
                        elif result == "failed":
                            self.stats["failed"] += 1
                        elif result == "skipped":
                            self.stats["skipped"] += 1
                        elif result == "multimedia":
                            self.stats["multimedia"] += 1
                            
                    except Exception as e:
                        self.logger.error(f"任务执行异常: {e}")
                        self.stats["failed"] += 1
                        
                    # 更新进度条
                    pbar.update(1)
                    pbar.set_postfix({
                        "成功": self.stats["success"],
                        "失败": self.stats["failed"],
                        "跳过": self.stats["skipped"],
                        "多媒体": self.stats["multimedia"]
                    })
                    
        self.stats["end_time"] = datetime.now()
        
    def save_failed_tasks(self):
        """保存失败的任务"""
        if self.failed_tasks:
            failed_file = Path("failed_tasks.json")
            with open(failed_file, "w", encoding="utf-8") as f:
                json.dump(self.failed_tasks, f, ensure_ascii=False, indent=2)
            self.logger.info(f"失败任务已保存到: {failed_file}")
            
    def save_multimedia_resources(self):
        """保存多媒体资源列表"""
        if self.multimedia_resources:
            multimedia_file = Path("multimedia_resources.json")
            with open(multimedia_file, "w", encoding="utf-8") as f:
                json.dump(self.multimedia_resources, f, ensure_ascii=False, indent=2)
            self.logger.info(f"多媒体资源列表已保存到: {multimedia_file}")
            
    def print_summary(self):
        """打印下载摘要"""
        duration = self.stats["end_time"] - self.stats["start_time"]
        
        print("\n" + "="*50)
        print("下载完成！")
        print("="*50)
        print(f"完整性检查模式: {self.integrity_mode}")
        print(f"总任务数: {self.stats['total']}")
        print(f"成功: {self.stats['success']}")
        print(f"失败: {self.stats['failed']}")
        print(f"跳过: {self.stats['skipped']}")
        print(f"包含多媒体的教材: {self.stats['multimedia']}")
        if self.enable_multimedia:
            print(f"下载的视频: {self.stats['videos_downloaded']}")
            print(f"跳过的DRM视频: {self.stats['videos_skipped_drm']}")
            print(f"下载的音频: {self.stats['audios_downloaded']}")
        if self.enable_retry:
            print(f"重试次数: {self.stats['retry_count']}")
            print(f"CDN切换次数: {self.stats['cdn_switch_count']}")
        print(f"耗时: {duration}")
        print("="*50)
        
    def filter_tasks(self, stage=None, subject=None, version=None, limit=None, exclude_teacher_books=False):
        """过滤任务"""
        filtered_tasks = []
        
        for task in self.tasks:
            metadata = task["metadata"]
            
            # 排除教师用书
            if exclude_teacher_books:
                # 检查是否是教师用书（通过grade字段或save_path）
                if metadata.get("grade", "") == "教师用书" or "教师用书" in task.get("save_path", ""):
                    continue
            
            # 按条件过滤
            if stage:
                task_stage = metadata.get("stage", "")
                # 特殊处理教学指南
                if self.normalize_string(stage) == "教学指南" and task_stage == "":
                    pass  # 匹配
                elif self.normalize_string(task_stage) != self.normalize_string(stage):
                    continue
            if subject and self.normalize_string(metadata.get("subject", "")) != self.normalize_string(subject):
                continue
            if version and self.normalize_string(metadata.get("version", "")) != self.normalize_string(version):
                continue
                
            filtered_tasks.append(task)
            
            # 限制数量
            if limit and len(filtered_tasks) >= limit:
                break
                
        return filtered_tasks
        
    def normalize_string(self, s):
        """标准化字符串用于比较"""
        return s.strip().lower()
        
    def run(self, stage=None, subject=None, version=None, limit=None, exclude_teacher_books=False):
        """运行下载器"""
        # 加载任务
        self.load_tasks()
        
        # 过滤任务（重试模式下通常不需要过滤）
        if self.retry_failed:
            # 重试模式下，stage/subject/version过滤参数被忽略
            if stage or subject or version:
                self.logger.warning("重试模式下，过滤参数将被忽略")
            tasks_to_download = self.tasks[:limit] if limit else self.tasks
        elif stage or subject or version or limit or exclude_teacher_books:
            tasks_to_download = self.filter_tasks(stage, subject, version, limit, exclude_teacher_books)
            self.logger.info(f"过滤后剩余 {len(tasks_to_download)} 个任务")
        else:
            tasks_to_download = self.tasks
            
        if not tasks_to_download:
            self.logger.warning("没有符合条件的任务")
            return
            
        # 开始下载
        self.download_batch(tasks_to_download)
        
        # 保存失败任务
        self.save_failed_tasks()
        
        # 保存多媒体资源列表
        self.save_multimedia_resources()
        
        # 打印摘要
        self.print_summary()


def main():
    parser = argparse.ArgumentParser(
        description="整合版批量下载教材",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 仅下载PDF（最快）
  %(prog)s --token TOKEN --no-multimedia
  
  # 下载PDF和音频（默认）
  %(prog)s --token TOKEN
  
  # 按条件过滤下载
  %(prog)s --token TOKEN --stage 小学 --subject 英语
  
  # 下载小学教材但排除教师用书
  %(prog)s --token TOKEN --stage 小学 --no-teacher-books
  
  # 重试失败的任务
  %(prog)s --token TOKEN --retry-failed
  
  # 禁用高级功能（简单模式）
  %(prog)s --token TOKEN --no-retry --no-ratelimit
  
  # 使用不同的完整性检查模式
  %(prog)s --token TOKEN --integrity-mode local    # 最快，仅检查本地文件
  %(prog)s --token TOKEN --integrity-mode smart    # 默认，智能判断
  %(prog)s --token TOKEN --integrity-mode strict   # 最严格，进行网络验证
        """
    )
    
    # 基础参数
    parser.add_argument("--token", required=True, help="认证Token")
    parser.add_argument("--tasks", default="download_tasks.json", help="任务文件路径")
    parser.add_argument("--output", "-o", help="输出目录（默认：教材库）")
    parser.add_argument("--workers", type=int, default=3, help="并发下载数")
    
    # 任务过滤
    filter_group = parser.add_argument_group('任务过滤')
    filter_group.add_argument("--stage", help="只下载指定学段（如：小学、初中、高中）")
    filter_group.add_argument("--subject", help="只下载指定学科（如：语文、数学、英语）")
    filter_group.add_argument("--version", help="只下载指定版本（如：人教、北师、苏教）")
    filter_group.add_argument("--limit", type=int, help="限制下载数量")
    filter_group.add_argument("--retry-failed", action="store_true", 
                             help="重试失败的任务（从failed_tasks.json读取）")
    filter_group.add_argument("--no-teacher-books", action="store_true",
                             help="排除教师用书（当按学段过滤时很有用）")
    
    # 功能控制
    feature_group = parser.add_argument_group('功能控制')
    feature_group.add_argument("--no-multimedia", action="store_true", 
                              help="仅下载PDF，跳过所有多媒体资源")
    feature_group.add_argument("--no-retry", action="store_true", 
                              help="禁用失败重试机制")
    feature_group.add_argument("--no-ratelimit", action="store_true", 
                              help="禁用请求速率限制")
    feature_group.add_argument("--rate-limit", type=float, default=2.0, 
                              help="每秒最大请求数（默认: 2.0）")
    feature_group.add_argument("--integrity-mode", choices=['strict', 'smart', 'local'], 
                              default='smart', 
                              help="文件完整性检查模式: strict=网络验证, smart=智能判断(默认), local=仅本地检查")
    
    args = parser.parse_args()
    
    # 创建下载器
    downloader = IntegratedBatchDownloader(
        token=args.token,
        tasks_file=args.tasks,
        max_workers=args.workers,
        output_dir=args.output,
        retry_failed=args.retry_failed,
        enable_multimedia=not args.no_multimedia,
        enable_retry=not args.no_retry,
        rate_limit=args.rate_limit,
        enable_ratelimit=not args.no_ratelimit,
        integrity_mode=args.integrity_mode
    )
    
    # 运行下载
    downloader.run(
        stage=args.stage,
        subject=args.subject,
        version=args.version,
        limit=args.limit,
        exclude_teacher_books=args.no_teacher_books
    )


if __name__ == "__main__":
    main()
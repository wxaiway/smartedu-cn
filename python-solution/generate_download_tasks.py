#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成批量下载任务列表
从catalog_output目录读取教材数据，生成标准化的下载任务
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
import hashlib

class DownloadTaskGenerator:
    def __init__(self):
        self.catalog_dir = Path("catalog_output")
        self.output_file = Path("download_tasks.json")
        
        # 学段映射
        self.stage_map = {
            "小学": "小学",
            "初中": "初中",
            "高中": "高中",
            "小学（五•四学制）": "小学54",
            "初中（五•四学制）": "初中54",
            "特殊教育": "特教",
            "未知学段": "其他",
            "": "教学指南"
        }
        
        # 学科映射
        self.subject_map = {
            "语文": "语文",
            "数学": "数学",
            "英语": "英语",
            "物理": "物理",
            "化学": "化学",
            "生物学": "生物",
            "历史": "历史",
            "地理": "地理",
            "道德与法治": "道法",
            "思想政治": "政治",
            "体育与健康": "体育",
            "艺术": "艺术",
            "艺术·音乐": "音乐",
            "艺术·美术": "美术",
            "艺术·舞蹈/影视/戏剧": "艺术综合",
            "音乐": "音乐",
            "美术": "美术",
            "信息技术": "信息",
            "信息科技": "信息",
            "通用技术": "通技",
            "科学": "科学",
            "语文·书法练习指导": "书法",
            "地理图册": "地理图",
            # 特殊教育学科
            "生活语文": "生活语文",
            "生活数学": "生活数学",
            "生活适应": "生活适应",
            "沟通与交往": "沟通交往",
            # 小语种
            "日语": "日语",
            "俄语": "俄语",
            "法语": "法语",
            "德语": "德语",
            "西班牙语": "西语",
            "英语（三年级起点）": "英语"
        }
        
        # 版本映射
        self.version_map = {
            "人教版": "人教",
            "人民教育出版社": "人教",
            "北师大版": "北师",
            "北京师范大学出版社": "北师",
            "统编版": "统编",
            "部编版": "部编",
            "苏教版": "苏教",
            "江苏凤凰教育出版社": "苏教",
            "沪教版": "沪教",
            "上海教育出版社": "沪教",
            "冀教版": "冀教",
            "河北教育出版社": "冀教",
            "外研版": "外研",
            "外语教学与研究出版社": "外研",
            "华东师大版": "华师",
            "华东师范大学出版社": "华师",
            "华中师大版": "华中师",
            "华中师范大学出版社": "华中师",
            "教科版": "教科",
            "教育科学出版社": "教科",
            "北京版": "京版",
            "北京出版社": "京版",
            "粤教版": "粤教",
            "广东教育出版社": "粤教",
            "译林版": "译林",
            "译林出版社": "译林",
            "湘教版": "湘教",
            "湖南教育出版社": "湘教",
            "科学社版": "科学",
            "科学出版社": "科学",
            "地质社版": "地质",
            "地质出版社": "地质",
            "未来社版": "未来",
            "未来出版社": "未来",
            "智慧中小学": "智慧",
            "": "通用"
        }
        
        # 册次映射
        self.semester_map = {
            "上册": "上",
            "下册": "下",
            "全一册": "全",
            "必修": "必修",
            "选修": "选修",
            "选择性必修": "选必",
            "必修1": "必修1",
            "必修2": "必修2",
            "必修3": "必修3",
            "选修1": "选修1",
            "选修2": "选修2",
            "选修3": "选修3"
        }
        
        # 年级映射（中文数字转阿拉伯数字）
        self.grade_map = {
            "一年级": "1年级",
            "二年级": "2年级",
            "三年级": "3年级",
            "四年级": "4年级",
            "五年级": "5年级",
            "六年级": "6年级",
            "七年级": "7年级",
            "八年级": "8年级",
            "九年级": "9年级",
            "高一": "高1",
            "高二": "高2",
            "高三": "高3",
            "教师用书": "教师",
            "学生用书": "学生"
        }
        
        self.tasks = []
        self.task_counter = 0
        
    def generate_task_id(self):
        """生成任务ID"""
        self.task_counter += 1
        return f"task_{self.task_counter:04d}"
    
    def parse_catalog_path(self, path):
        """解析目录路径"""
        if not path:
            return {
                "stage": "",
                "subject": "",
                "version": "",
                "grade": "",
                "semester": ""
            }
        
        parts = [p.strip() for p in path.split(">")]
        metadata = {
            "stage": parts[0] if len(parts) > 0 else "",
            "subject": parts[1] if len(parts) > 1 else "",
            "version": parts[2] if len(parts) > 2 else "",
            "grade": parts[3] if len(parts) > 3 else "",
            "semester": parts[4] if len(parts) > 4 else ""
        }
        
        return metadata
    
    def standardize_path_component(self, component, mapping):
        """标准化路径组件"""
        return mapping.get(component, component) if component else ""
    
    def clean_title(self, title):
        """清理标题"""
        # 移除常见前缀
        prefixes = [
            "义务教育教科书",
            "义务教育",
            "教科书",
            "普通高中教科书",
            "普通高中",
            "高中教科书",
            "（根据2022年版课程标准修订）",
            "（根据2017年版课程标准修订）"
        ]
        
        cleaned = title
        for prefix in prefixes:
            cleaned = cleaned.replace(prefix, "")
        
        # 移除多余的符号和空格
        cleaned = re.sub(r'[·•]+', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    
    def generate_file_name(self, metadata, title):
        """生成标准化文件名"""
        # 获取标准化的组件
        subject = self.standardize_path_component(metadata["subject"], self.subject_map)
        grade = self.standardize_path_component(metadata["grade"], self.grade_map)
        semester = self.standardize_path_component(metadata["semester"], self.semester_map)
        version = self.standardize_path_component(metadata["version"], self.version_map)
        
        # 特殊处理教师用书
        if "教师" in metadata["grade"]:
            # 从cleaned title中提取专项名称
            cleaned_title = self.clean_title(title)
            # 尝试提取括号中的内容作为专项
            match = re.search(r'([^（]+)（(.+)）', cleaned_title)
            if match:
                special = match.group(2).replace("全一册", "")
            else:
                special = cleaned_title.replace(subject, "").strip()
            
            if special:
                file_name = f"{subject}_教师_{special}_{version}.pdf"
            else:
                file_name = f"{subject}_教师_{version}.pdf"
        else:
            # 普通教材
            parts = [subject, grade, semester, version]
            parts = [p for p in parts if p]  # 过滤空值
            file_name = "_".join(parts) + ".pdf"
        
        # 清理文件名中的非法字符
        file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)
        file_name = re.sub(r'_+', '_', file_name)
        file_name = file_name.strip('_')
        
        return file_name
    
    def generate_save_path(self, metadata, file_name):
        """生成保存路径"""
        # 获取标准化的组件
        stage = self.standardize_path_component(metadata["stage"], self.stage_map)
        subject = self.standardize_path_component(metadata["subject"], self.subject_map)
        version = self.standardize_path_component(metadata["version"], self.version_map)
        grade = self.standardize_path_component(metadata["grade"], self.grade_map)
        semester = self.standardize_path_component(metadata["semester"], self.semester_map)
        
        # 构建路径
        path_parts = ["教材库"]
        
        # 特殊处理教师用书
        if "教师" in grade:
            path_parts.extend(["教师用书", subject, version])
        elif not stage:  # 教学指南
            path_parts.append("教学指南")
        else:
            # 普通教材
            path_parts.extend([stage, subject, version])
            if grade and "教师" not in grade:
                path_parts.append(grade)
            if semester:
                path_parts.append(semester)
        
        save_path = os.path.join(*path_parts, file_name)
        return save_path
    
    def process_book(self, book, group_name):
        """处理单本教材"""
        # 解析目录路径
        catalog_path = book.get("path", "")
        metadata = self.parse_catalog_path(catalog_path)
        
        # 生成文件名
        title = book.get("title", "未知教材")
        file_name = self.generate_file_name(metadata, title)
        
        # 生成保存路径
        save_path = self.generate_save_path(metadata, file_name)
        
        # 构建任务
        task = {
            "id": self.generate_task_id(),
            "content_id": book["id"],
            "content_type": "assets_document",  # 默认类型
            "original_title": title,
            "file_name": file_name,
            "save_path": save_path,
            "page_url": book.get("url", ""),
            "api_url": f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{book['id']}.json",
            "catalog_path": catalog_path,
            "metadata": {
                "stage": metadata["stage"],
                "subject": metadata["subject"],
                "version": metadata["version"],
                "grade": metadata["grade"],
                "semester": metadata["semester"],
                "publisher": book.get("publisher", ""),
                "group": group_name
            }
        }
        
        return task
    
    def load_catalog_data(self):
        """加载目录数据"""
        print("正在加载目录数据...")
        
        # 遍历所有download_list文件
        for file_path in self.catalog_dir.glob("download_list_*.json"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            group_name = data.get("group", file_path.stem.replace("download_list_", ""))
            books = data.get("books", [])
            
            print(f"处理 {file_path.name}: {len(books)} 本教材")
            
            for book in books:
                task = self.process_book(book, group_name)
                self.tasks.append(task)
    
    def generate_statistics(self):
        """生成统计信息"""
        stats = {
            "total": len(self.tasks),
            "by_stage": {},
            "by_subject": {},
            "by_version": {},
            "by_group": {}
        }
        
        for task in self.tasks:
            metadata = task["metadata"]
            
            # 按学段统计
            stage = self.standardize_path_component(metadata["stage"], self.stage_map) or "其他"
            stats["by_stage"][stage] = stats["by_stage"].get(stage, 0) + 1
            
            # 按学科统计
            subject = self.standardize_path_component(metadata["subject"], self.subject_map) or "其他"
            stats["by_subject"][subject] = stats["by_subject"].get(subject, 0) + 1
            
            # 按版本统计
            version = self.standardize_path_component(metadata["version"], self.version_map) or "通用"
            stats["by_version"][version] = stats["by_version"].get(version, 0) + 1
            
            # 按分组统计
            group = metadata.get("group", "未知")
            stats["by_group"][group] = stats["by_group"].get(group, 0) + 1
        
        return stats
    
    def save_tasks(self):
        """保存任务列表"""
        print(f"\n生成了 {len(self.tasks)} 个下载任务")
        
        # 生成统计信息
        stats = self.generate_statistics()
        
        # 构建输出数据
        output = {
            "total": len(self.tasks),
            "generated_at": datetime.now().isoformat(),
            "statistics": stats,
            "tasks": self.tasks
        }
        
        # 保存文件
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"任务列表已保存到: {self.output_file}")
        
        # 打印统计信息
        print("\n=== 统计信息 ===")
        print(f"总任务数: {stats['total']}")
        
        print("\n按学段分布:")
        for stage, count in sorted(stats["by_stage"].items(), key=lambda x: x[1], reverse=True):
            print(f"  {stage}: {count}")
        
        print("\n按学科分布 (前10):")
        for subject, count in sorted(stats["by_subject"].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {subject}: {count}")
        
        print("\n按版本分布 (前10):")
        for version, count in sorted(stats["by_version"].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {version}: {count}")
    
    def generate_directory_preview(self):
        """生成目录结构预览"""
        print("\n生成目录结构预览...")
        
        # 收集所有目录
        directories = set()
        for task in self.tasks:
            path = Path(task["save_path"]).parent
            while path and str(path) != ".":
                directories.add(str(path))
                path = path.parent
        
        # 保存目录结构
        preview_file = Path("directory_structure.txt")
        with open(preview_file, "w", encoding="utf-8") as f:
            f.write("教材库目录结构预览\n")
            f.write("=" * 50 + "\n\n")
            
            for directory in sorted(directories):
                level = directory.count(os.sep)
                indent = "  " * level
                name = os.path.basename(directory) or directory
                f.write(f"{indent}{name}/\n")
        
        print(f"目录结构预览已保存到: {preview_file}")
    
    def run(self):
        """运行任务生成器"""
        print("开始生成下载任务列表...")
        
        # 检查目录
        if not self.catalog_dir.exists():
            print(f"错误: 找不到目录 {self.catalog_dir}")
            return
        
        # 加载数据
        self.load_catalog_data()
        
        # 保存任务
        self.save_tasks()
        
        # 生成目录预览
        self.generate_directory_preview()
        
        print("\n任务生成完成！")


def main():
    generator = DownloadTaskGenerator()
    generator.run()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
国家中小学智慧教育平台API分析工具 - 简化版
直接从教材的tag_list提取信息
"""

import json
import requests
from typing import Dict, List, Any, Tuple
from pathlib import Path
import time
from collections import defaultdict

class SmartEduAnalyzerSimple:
    def __init__(self):
        self.base_urls = {
            'version': 'https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/resources/tch_material/version/data_version.json',
        }
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 创建输出目录
        self.output_dir = Path('catalog_output')
        self.output_dir.mkdir(exist_ok=True)
        
        self.books = []
        self.tree = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))))
        
        # 维度ID到目录字段的映射
        self.dimension_map = {
            'zxxxd': 'stage',    # 学段
            'zxxxk': 'subject',  # 学科
            'zxxbb': 'version',  # 版本
            'zxxnj': 'grade',    # 年级
            'zxxcc': 'semester'  # 册次
        }
    
    def fetch_json(self, url: str, save_name: str = None) -> Any:
        """获取JSON数据"""
        print(f"正在获取: {url}")
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # 保存到本地
            if save_name:
                save_path = self.output_dir / save_name
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"已保存到: {save_path}")
            
            return data
        except Exception as e:
            print(f"获取失败: {e}")
            return {}
    
    def extract_catalog_from_tags(self, book: Dict) -> Dict[str, str]:
        """从教材的tag_list中提取目录信息"""
        catalog = {
            'stage': '',
            'subject': '',
            'version': '',
            'grade': '',
            'semester': ''
        }
        
        # 从tag_list中提取
        tag_list = book.get('tag_list', [])
        for tag in tag_list:
            dimension_id = tag.get('tag_dimension_id')
            tag_name = tag.get('tag_name')
            
            if dimension_id in self.dimension_map and tag_name:
                field = self.dimension_map[dimension_id]
                catalog[field] = tag_name
        
        return catalog
    
    def process_books(self):
        """处理教材数据"""
        print("\n=== 获取教材数据 ===")
        
        # 获取版本信息
        version_data = self.fetch_json(self.base_urls['version'], 'version.json')
        if not version_data:
            print("无法获取版本数据")
            return
        
        print(f"数据版本: {version_data.get('version')}")
        
        # 获取数据源URL
        urls = version_data.get('urls', '').split(',')
        print(f"数据源数量: {len(urls)}")
        
        # 获取每个数据源的教材
        total_books = 0
        for i, url in enumerate(urls):
            if not url.strip():
                continue
                
            print(f"\n获取数据源 {i+1}/{len(urls)}")
            books_data = self.fetch_json(url)
            
            if books_data and isinstance(books_data, list):
                print(f"  教材数量: {len(books_data)}")
                total_books += len(books_data)
                
                # 处理教材数据
                for book in books_data:
                    self.process_single_book(book)
            
            time.sleep(0.5)  # 避免请求过快
        
        print(f"\n总教材数量: {total_books}")
    
    def process_single_book(self, book: Dict):
        """处理单本教材"""
        # 从tag_list提取目录信息
        catalog = self.extract_catalog_from_tags(book)
        
        # 提取出版社信息
        publisher = ''
        provider_list = book.get('provider_list', [])
        if provider_list:
            publisher = provider_list[0].get('name', '')
        
        # 构建教材信息
        book_info = {
            'id': book.get('id'),
            'title': book.get('title') or book.get('ti_title'),
            'catalog': catalog,
            'publisher': publisher,
            'create_time': book.get('create_time'),
            'resource_type': book.get('resource_type_code', 'assets_document')
        }
        
        self.books.append(book_info)
        
        # 添加到树形结构
        stage = catalog['stage'] or '未知学段'
        subject = catalog['subject'] or '未知学科'
        version = catalog['version'] or '未知版本'
        grade = catalog['grade'] or '未知年级'
        semester = catalog['semester'] or '未分册'
        
        self.tree[stage][subject][version][grade][semester].append(book_info)
    
    def sort_grade(self, grade: str) -> int:
        """年级排序辅助函数"""
        grade_order = {
            '一年级': 1, '二年级': 2, '三年级': 3, 
            '四年级': 4, '五年级': 5, '六年级': 6,
            '七年级': 7, '八年级': 8, '九年级': 9,
            '高一': 10, '高二': 11, '高三': 12,
            '学生读本': 20
        }
        return grade_order.get(grade, 99)
    
    def build_tree_structure(self):
        """构建树形结构并生成统计"""
        print("\n=== 构建目录结构 ===")
        
        tree_output = []
        stats = {
            'total': len(self.books),
            'by_stage': {},
            'by_subject': {},
            'by_publisher': {}
        }
        
        # 构建树形结构
        for stage, subjects in sorted(self.tree.items()):
            stage_count = 0
            stage_node = {
                'name': stage,
                'type': 'stage',
                'children': []
            }
            
            for subject, versions in sorted(subjects.items()):
                subject_count = 0
                subject_node = {
                    'name': subject,
                    'type': 'subject',
                    'children': []
                }
                
                for version, grades in sorted(versions.items()):
                    version_count = 0
                    version_node = {
                        'name': version,
                        'type': 'version',
                        'children': []
                    }
                    
                    for grade, semesters in sorted(grades.items(), key=lambda x: self.sort_grade(x[0])):
                        grade_count = 0
                        grade_node = {
                            'name': grade,
                            'type': 'grade',
                            'children': []
                        }
                        
                        for semester, books in sorted(semesters.items()):
                            semester_node = {
                                'name': semester,
                                'type': 'semester',
                                'count': len(books),
                                'books': [{'id': b['id'], 'title': b['title'], 'publisher': b['publisher']} for b in books]
                            }
                            grade_node['children'].append(semester_node)
                            grade_count += len(books)
                        
                        grade_node['count'] = grade_count
                        version_node['children'].append(grade_node)
                        version_count += grade_count
                    
                    version_node['count'] = version_count
                    subject_node['children'].append(version_node)
                    subject_count += version_count
                
                subject_node['count'] = subject_count
                stage_node['children'].append(subject_node)
                stage_count += subject_count
                
                # 统计
                stats['by_subject'][subject] = stats['by_subject'].get(subject, 0) + subject_count
            
            stage_node['count'] = stage_count
            tree_output.append(stage_node)
            stats['by_stage'][stage] = stage_count
        
        # 统计出版社
        for book in self.books:
            publisher = book.get('publisher', '未知出版社')
            stats['by_publisher'][publisher] = stats['by_publisher'].get(publisher, 0) + 1
        
        # 保存树形结构
        tree_path = self.output_dir / 'catalog_tree.json'
        with open(tree_path, 'w', encoding='utf-8') as f:
            json.dump({
                'stats': stats,
                'tree': tree_output,
                'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }, f, ensure_ascii=False, indent=2)
        
        print(f"目录结构已保存到: {tree_path}")
        
        # 打印统计信息
        self.print_statistics(stats)
    
    def print_statistics(self, stats):
        """打印统计信息"""
        print(f"\n=== 统计信息 ===")
        print(f"总教材数: {stats['total']}")
        
        print("\n按学段统计:")
        for stage, count in sorted(stats['by_stage'].items()):
            print(f"  {stage}: {count}本")
        
        print("\n按学科统计（前15）:")
        subject_sorted = sorted(stats['by_subject'].items(), key=lambda x: x[1], reverse=True)[:15]
        for subject, count in subject_sorted:
            print(f"  {subject}: {count}本")
        
        print("\n按出版社统计（前10）:")
        publisher_sorted = sorted(stats['by_publisher'].items(), key=lambda x: x[1], reverse=True)[:10]
        for publisher, count in publisher_sorted:
            print(f"  {publisher}: {count}本")
    
    def generate_catalog_by_path(self):
        """生成按路径组织的目录"""
        print("\n=== 生成路径目录 ===")
        
        catalog_by_path = defaultdict(list)
        
        for book in self.books:
            catalog = book['catalog']
            
            # 构建路径
            path_parts = []
            for field in ['stage', 'subject', 'version', 'grade', 'semester']:
                if catalog[field]:
                    path_parts.append(catalog[field])
            
            path = ' > '.join(path_parts)
            
            catalog_by_path[path].append({
                'id': book['id'],
                'title': book['title'],
                'publisher': book['publisher'],
                'url': f"https://basic.smartedu.cn/tchMaterial/detail?contentType={book['resource_type']}&contentId={book['id']}&catalogType=tchMaterial&subCatalog=tchMaterial"
            })
        
        # 保存路径目录
        catalog_path = self.output_dir / 'catalog_by_path.json'
        with open(catalog_path, 'w', encoding='utf-8') as f:
            json.dump({
                'total': len(self.books),
                'paths': len(catalog_by_path),
                'catalog': dict(sorted(catalog_by_path.items())),
                'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }, f, ensure_ascii=False, indent=2)
        
        print(f"路径目录已保存到: {catalog_path}")
        print(f"共 {len(catalog_by_path)} 个不同路径")
    
    def generate_download_list(self):
        """生成下载列表"""
        print("\n=== 生成下载列表 ===")
        
        # 按学段-学科分组
        download_groups = defaultdict(list)
        
        for book in self.books:
            catalog = book['catalog']
            # 清理文件名中的特殊字符
            stage = catalog['stage'].replace('/', '_').replace('·', '_')
            subject = catalog['subject'].replace('/', '_').replace('·', '_')
            group_key = f"{stage}_{subject}"
            
            download_groups[group_key].append({
                'id': book['id'],
                'title': book['title'],
                'path': ' > '.join(filter(None, [
                    catalog['stage'],
                    catalog['subject'], 
                    catalog['version'],
                    catalog['grade'],
                    catalog['semester']
                ])),
                'url': f"https://basic.smartedu.cn/tchMaterial/detail?contentType={book['resource_type']}&contentId={book['id']}&catalogType=tchMaterial&subCatalog=tchMaterial"
            })
        
        # 保存下载列表
        for group_key, books in download_groups.items():
            if books:
                # 进一步清理文件名
                safe_filename = group_key.replace(' ', '_').replace('（', '(').replace('）', ')')
                filename = f"download_list_{safe_filename}.json"
                filepath = self.output_dir / filename
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump({
                        'group': group_key,
                        'count': len(books),
                        'books': books
                    }, f, ensure_ascii=False, indent=2)
        
        print(f"下载列表已生成到: {self.output_dir}")
        print(f"共 {len(download_groups)} 个分组")
    
    def run(self):
        """运行分析"""
        print("=== 国家中小学智慧教育平台目录生成工具 ===")
        print(f"输出目录: {self.output_dir}")
        
        # 1. 获取并处理教材数据
        self.process_books()
        
        # 2. 构建树形结构
        self.build_tree_structure()
        
        # 3. 生成路径目录
        self.generate_catalog_by_path()
        
        # 4. 生成下载列表
        self.generate_download_list()
        
        print("\n=== 完成 ===")
        print(f"所有文件已保存到: {self.output_dir}")
        print("\n文件说明:")
        print("- catalog_tree.json: 树形目录结构")
        print("- catalog_by_path.json: 按路径组织的目录")
        print("- download_list_*.json: 分组下载列表")


if __name__ == "__main__":
    analyzer = SmartEduAnalyzerSimple()
    analyzer.run()
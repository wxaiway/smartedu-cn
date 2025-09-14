#!/usr/bin/env python3
"""
从download_tasks.json生成前端textbooks.js文件
"""

import json
from datetime import datetime

def generate_frontend_data():
    """生成前端所需的教材数据"""
    
    # 读取下载任务
    with open('download_tasks.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 百度网盘分享信息（实际链接）
    baidu_shares = {
        "小学": {
            "link": "https://pan.baidu.com/s/1RwgeLrJ8U7x1Pg0PrwS15g?pwd=sd2g",
            "pwd": "sd2g"
        },
        "初中": {
            "link": "https://pan.baidu.com/s/1hodX8Fej65IRIhA0a_nudg?pwd=956v",
            "pwd": "956v"
        },
        "高中": {
            "link": "https://pan.baidu.com/s/1OY-f2nFD3uTKv23AY_BcNA?pwd=tars",
            "pwd": "tars"
        },
        "特教": {
            "link": "https://pan.baidu.com/s/1o0ISWapr3fiqn5cZM0IQEw?pwd=tq4d",
            "pwd": "tq4d"
        },
        "教师用书": {
            "link": "https://pan.baidu.com/s/13LaRQ0QypzJDJfsLf7YINg?pwd=eiua",
            "pwd": "eiua"
        },
        "小学54": {
            "link": "https://pan.baidu.com/s/1BgEK1XzEZBRvRNarhnmH2A?pwd=md5q",
            "pwd": "md5q"
        },
        "初中54": {
            "link": "https://pan.baidu.com/s/1ouYCt1pBosgiXDRVIJk8GA?pwd=ynpr",
            "pwd": "ynpr"
        }
    }
    
    # 转换任务为前端格式（只处理PDF任务）
    textbooks = []
    pdf_tasks = [t for t in data['tasks'] if t['file_name'].endswith('.pdf')]
    
    for idx, task in enumerate(pdf_tasks, 1):
        metadata = task['metadata']
        stage = metadata.get('stage', '')
        
        # 确定百度网盘链接
        if '五•四学制' in stage:
            if '小学' in stage:
                share_key = '小学54'
            elif '初中' in stage:
                share_key = '初中54'
            else:
                share_key = stage.replace('（五•四学制）', '')
        elif stage == '特殊教育':
            share_key = '特教'
        else:
            share_key = stage
        
        share_info = baidu_shares.get(share_key, baidu_shares.get('小学'))
        
        # 获取年级字符串
        grade_str = metadata.get('grade', '')
        
        # 确定文件大小范围
        size_map = {
            '小学': '10-50MB',
            '初中': '20-80MB',
            '高中': '50-100MB',
            '特殊教育': '10-30MB'
        }
        size = size_map.get(stage.split('（')[0], '10-50MB')
        
        # 获取文件大小（字节）
        size_bytes = task.get('size_bytes', 0)
        if size_bytes > 0:
            # 转换为MB
            size_mb = size_bytes / (1024 * 1024)
            size = f"{size_mb:.1f} MB"
        else:
            # 使用默认大小
            size = size_map.get(stage.split('（')[0], '10-50MB')
        
        textbook = {
            "id": idx,
            "name": task.get('original_title', task.get('file_name', '')),
            "stage": stage,
            "subject": metadata.get('subject', ''),
            "gradeStr": grade_str,
            "term": metadata.get('term', ''),
            "publisher": metadata.get('version', ''),
            "size": size,
            "pathInDisk": task['save_path'],
            "fileName": task['file_name'],
            "sizeBytes": size_bytes
        }
        
        textbooks.append(textbook)
    
    # 生成元数据
    stages = list(set(t['stage'] for t in textbooks if t['stage']))
    subjects = list(set(t['subject'] for t in textbooks if t['subject']))
    publishers = list(set(t['publisher'] for t in textbooks if t['publisher']))
    grades = list(set(t['gradeStr'] for t in textbooks if t['gradeStr']))
    
    meta = {
        "total": len(textbooks),
        "stages": sorted(stages),
        "subjects": sorted(subjects),
        "publishers": sorted(publishers),
        "grades": sorted(grades)
    }
    
    # 生成JavaScript文件
    js_content = f'''// 教材数据 - 自动生成
// 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
// 数据总数: {len(textbooks)}

// 百度网盘分享信息（按根目录）
const BAIDU_DISK_SHARES = {json.dumps(baidu_shares, ensure_ascii=False, indent=2)};

// 教材数据
const TEXTBOOKS = {json.dumps(textbooks, ensure_ascii=False, indent=2)};
'''
    
    # 写入文件
    output_path = '../frontend/textbooks.js'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print(f"前端数据生成完成：")
    print(f"- 教材总数：{len(textbooks)}")
    print(f"- 输出文件：{output_path}")
    print(f"\n统计信息：")
    
    # 按学段统计
    stage_count = {}
    for t in textbooks:
        stage = t['stage']
        stage_count[stage] = stage_count.get(stage, 0) + 1
    
    for stage, count in sorted(stage_count.items()):
        print(f"  - {stage}：{count}本")

if __name__ == "__main__":
    generate_frontend_data()
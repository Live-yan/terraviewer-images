#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片文件列表生成器
扫描当前目录下的所有图片文件并将文件名写入JSON文件
"""

import os
import json
import glob
from pathlib import Path

def get_image_files(directory="."):
    """
    获取指定目录下的所有图片文件
    
    Args:
        directory (str): 要扫描的目录路径，默认为当前目录
    
    Returns:
        list: 图片文件名列表
    """
    # 支持的图片格式
    image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.tiff', '*.webp', '*.ico']
    
    image_files = []
    
    # 遍历所有支持的图片格式
    for extension in image_extensions:
        # 使用glob查找匹配的文件（不区分大小写）
        pattern = os.path.join(directory, extension)
        files = glob.glob(pattern)
        
        # 也查找大写扩展名
        pattern_upper = os.path.join(directory, extension.upper())
        files.extend(glob.glob(pattern_upper))
        
        # 只保留文件名，不包含路径
        for file_path in files:
            filename = os.path.basename(file_path)
            if filename not in image_files:  # 避免重复
                image_files.append(filename)
    
    # 按文件名排序
    image_files.sort()
    return image_files

def save_to_json(image_files, output_file="files_list.json"):
    """
    将图片文件列表保存到JSON文件
    
    Args:
        image_files (list): 图片文件名列表
        output_file (str): 输出的JSON文件名
    """
    data = {
        "image_files": image_files,
        "total_count": len(image_files),
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"成功生成 {output_file}")
    print(f"找到 {len(image_files)} 个图片文件")

def main():
    """主函数"""
    print("开始扫描图片文件...")
    
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 获取图片文件列表
    image_files = get_image_files(current_dir)
    
    if image_files:
        print(f"找到以下图片文件：")
        for i, filename in enumerate(image_files, 1):
            print(f"{i:3d}. {filename}")
        
        # 保存到JSON文件
        output_file = os.path.join(current_dir, "files_list.json")
        save_to_json(image_files, output_file)
    else:
        print("未找到任何图片文件")

if __name__ == "__main__":
    main()

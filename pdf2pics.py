import configparser
import os
from pathlib import Path
from typing import Any, List, Union

from PIL import Image
import fitz 
from loguru import logger

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("pdf2pics")

# 读取系统配置
config = configparser.ConfigParser()
config.read('config.ini')
PDF_ROOT = Path(config.get('PATHS', 'pdf_root', fallback='.'))
OUTPUT_ROOT = Path(config.get('PATHS', 'output_root', fallback='output'))


# 添加配置验证逻辑
def validate_config():
    if not PDF_ROOT.exists():
        raise FileNotFoundError(f"PDF根目录不存在：{PDF_ROOT}")
    if not OUTPUT_ROOT.exists():
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

# 在程序初始化时调用
validate_config()

# 新增loguru配置（添加到配置验证之后）
logger.add(
    OUTPUT_ROOT / 'conversion.log',
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    rotation="10 MB",
    encoding='utf-8'
)

def convert_pdfs_to_images(input_dir: Union[str, Path], output_dir: Union[str, Path], pages: List[int] = None) -> dict[str, Any]:
    """
    Convert all PDF files in a directory (including subdirectories) to images
    while preserving relative paths.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_to_image_map = {}

    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = Path(root) / file
                relative_path = pdf_path.relative_to(input_dir)
                output_subdir = output_dir / relative_path.parent / pdf_path.stem
                output_subdir.mkdir(parents=True, exist_ok=True)

                image_paths = convert_pdf_to_images(pdf_path, output_subdir, pages)
                pdf_to_image_map[str(relative_path)] = image_paths
                
    return pdf_to_image_map

def convert_pdf_to_images(pdf: Union[str, Path], output_dir: Union[str, Path]) -> List[str]:
    """
    Convert a single PDF file to images with the same name as the PDF file
    and save the images to a specified directory.
    """
    doc = fitz.open(pdf)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []
    
    # 提升分辨率参数（原2倍提升改为4倍）
    zoom = 4  # 矩阵缩放因子从2改为4
    mat = fitz.Matrix(zoom, zoom)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat)  # 使用更高清参数
        output_path = output_dir / f"{page_num+1}.png"
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(output_path, format="PNG")
        image_paths.append(str(output_path.relative_to(OUTPUT_ROOT)))

    doc.close()
    return image_paths


@mcp.tool()
def convert_pdfs(pdfs: Union[str, List[str], Path], output_dir: str) -> dict:
    """
    将多个 PDF 文件转换为与 PDF 同名的图片，并将这些图片保存到指定目录。
    参数:
        pdfs (Union[str, List[str], Path]): PDF 文件的路径或 PDF 文件路径列表。
        output_dir (str): 输出目录的相对路径。
    返回:
        dict: 包含输出目录相对路径的字典。
    """
    result = {}
    
    # 统一输入处理
    if isinstance(pdfs, (str, Path)):
        pdfs = Path(pdfs)
        if pdfs.is_dir():
            # 扫描目录下的PDF文件
            pdf_list = list(pdfs.glob('**/*.pdf'))
        else:
            pdf_list = [pdfs]
    
    # 添加异常处理
    try:
        for pdf in pdf_list:
            pdf_path = PDF_ROOT / pdf
            output_subdir = OUTPUT_ROOT / output_dir / Path(pdf).stem
            result[str(pdf)] = convert_pdf_to_images(pdf_path, output_subdir)
    except Exception as e:
        # 原代码中的日志调用（约55行）
        logger.error(f"Conversion failed: {str(e)}")
        
        # 改为loguru方式（自动包含上下文信息）
        logger.error(f"Conversion failed: {e}")
    return result

@mcp.tool()
def convert_pdf(pdf_name, output_path) -> dict[str, Any]:
    """
    将单个 PDF 文件转换为与该 PDF 同名的图片，并将这些图片保存到指定目录。
    参数:
        pdf_name (str): 要转换的 PDF 文件的名称。
        output_path (str): 输出目录的相对路径。
    返回:
        dict[str, Any]: 包含输出目录相对路径的字典。
    """
    return convert_pdf_to_images(PDF_ROOT / pdf_name, OUTPUT_ROOT / output_path)

if __name__ == "__main__":
    mcp.run(transport='stdio')
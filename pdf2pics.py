import configparser
import os
import hashlib
from pathlib import Path
from typing import Any, List, Union

from PIL import Image
import fitz 
from loguru import logger

from http_file import concurrent_upload, upload_file

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("pdf2pics")

# 读取系统配置
config = configparser.ConfigParser()
config.read('config.ini')
PDF_ROOT = Path(config.get('PATHS', 'pdf_root', fallback='.'))
OUTPUT_ROOT = Path(config.get('PATHS', 'output_root', fallback='output'))
HTTP_FILE_SERVER_URL = config.get('HTTP_FILE_SERVER', 'endpoint', fallback='http://127.0.0.1')
HTTP_FILE_UPLOAD_CONCURRENCY = int(config.get('HTTP_FILE_SERVER', 'concurrency', fallback='5'))

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

def convert_pdf_to_images(pdf: Union[str, Path], output_dir: Union[str, Path], return_pic_url: bool = True) -> List[str]:
    """
    Convert a single PDF file to images with the same name as the PDF file
    and save the images to a specified directory.
    """
    doc = fitz.open(pdf)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Converting {pdf} to {output_dir}")
    image_paths = []
    
    # 提升分辨率参数（原2倍提升改为4倍）
    zoom = 4  # 矩阵缩放因子从2改为4
    mat = fitz.Matrix(zoom, zoom)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat)  # 使用更高清参数
        output_path = output_dir / f"{pdf.stem}_{page_num+1}.png"
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(output_path, format="PNG")
        image_paths.append(str(output_path.relative_to(OUTPUT_ROOT)))

    doc.close()

    if return_pic_url:
        # 上传图片到HTTP文件服务器
        image_paths = [str(OUTPUT_ROOT / image) for image in image_paths]
        image_paths = concurrent_upload(image_paths, HTTP_FILE_SERVER_URL, max_workers = HTTP_FILE_UPLOAD_CONCURRENCY)
    return image_paths


@mcp.tool()
def convert_pdfs(pdfs_dir: str, return_pic_url: bool = True) -> dict[str, Any]:
    """
    将多个 PDF 文件转换为图片。
    参数:
        pdfs_dir str: PDF 文件夹路径
        return_pic_url bool: 是否上传图片到http 文件服务器，并返回图片的URL。默认为True。
    返回:
        dict: 包含输出目录相对路径的字典。
    """
    result = {}
    pdfs = PDF_ROOT / pdfs_dir
    if pdfs.is_dir():
        # 扫描目录下的PDF文件
        pdf_list = list(pdfs.glob('**/*.pdf'))
        logger.info(f"Found {len(pdf_list)} PDF files in {pdfs}: {pdf_list}")
    else:
        raise ValueError("输入路径不是有效的目录")
    
    # 添加异常处理
    try:
        for pdf in pdf_list:
            pdf_path = pdf
            output_subdir = OUTPUT_ROOT / pdfs_dir / Path(pdf).stem
            logger.info(f"Converting {pdf}(path:{pdf_path}) to {output_subdir}")
            result[str(pdf.relative_to(PDF_ROOT))] = convert_pdf_to_images(pdf_path, output_subdir)
    except Exception as e:
        # 改为loguru方式（自动包含上下文信息）
        logger.error(f"Conversion failed: {e}")
    return result

@mcp.tool()
def convert_pdf(pdf_name: str, return_pic_url: bool = True) -> dict[str, Any]:
    """
    将单个 PDF 文件转换为与该 PDF 同名的图片，并将这些图片保存到指定目录。
    参数:
        pdf_name (str): 要转换的 PDF 文件的名称。
        return_pic_url (bool): 是否上传图片到http 文件服务器，并返回图片的URL。默认为True。
    返回:
        dict[str, Any]: 包含输出目录相对路径的字典。
    """
    # 生成文件名的 MD5 哈希值
    output_path = hashlib.md5(pdf_name.encode('utf-8')).hexdigest()
    return {pdf_name: convert_pdf_to_images(PDF_ROOT / pdf_name, OUTPUT_ROOT / output_path, return_pic_url)}


if __name__ == "__main__":
    mcp.run(transport='stdio')
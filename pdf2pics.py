import configparser
import re
import hashlib
import shutil
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

def convert_pdf_to_images(pdf: Union[str, Path], output_dir: Union[str, Path], return_pic_url: bool = True) -> List[str]:
    """
    将单个 PDF 文件转换为与该 PDF 文件同名的图片，并将这些图片保存到指定目录。
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
        output_path = output_dir / f"{pdf.stem}-{page_num+1}.png"
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(output_path, format="PNG")
        image_paths.append(str(output_path.relative_to(OUTPUT_ROOT)))

    doc.close()

    if return_pic_url:
        # 上传图片到HTTP文件服务器
        upload_paths = []
        for image in image_paths:
            original_file = OUTPUT_ROOT / image
            upload_file = OUTPUT_ROOT / re.sub(r'[\\/]', '_', image)
            logger.info(f"Preparing {original_file} to {upload_file}")
            shutil.move(original_file, upload_file)
            upload_paths.append(str(upload_file))
        logger.info(f"Uploading {upload_paths} images to {HTTP_FILE_SERVER_URL}")
        image_paths = concurrent_upload(upload_paths, HTTP_FILE_SERVER_URL, max_workers = HTTP_FILE_UPLOAD_CONCURRENCY)
    return image_paths


@mcp.tool()
def convert_pdfs(pdfs_dir: str, return_pic_url: bool = True) -> dict[str, Any]:
    """
    将文件夹下（包括子文件夹）的所有 PDF 文件转换为图片。
    参数:
        pdfs_dir str: PDF 文件夹路径，不包含子文件下的文件
        return_pic_url bool: 是否上传图片到http 文件服务器，并返回图片的URL。默认为True。
    返回:
        dict: 包含输出目录相对路径的字典。其中上传后，文件名会转为`相对路径_文件名-页码.png`的格式。例如，路径为`a/b/c.pdf`，则会生成`/a_b_c-1.png`、`/a_b_c-2.png`等文件。
    """
    result = {}
    pdfs = PDF_ROOT / pdfs_dir
    if pdfs.is_dir():
        # 扫描目录下的PDF文件
        pdf_list = list(pdfs.glob('**/*.pdf'))
        logger.info(f"Found {len(pdf_list)} PDF files in {pdfs.absolute()}: {pdf_list}")
    else:
        raise ValueError("输入路径不是有效的目录")
    
    # 添加异常处理
    try:
        for pdf in pdf_list:
            pdf_path = pdf
            output_subdir = OUTPUT_ROOT / pdf.relative_to(PDF_ROOT).parent
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
    return {pdf_name: convert_pdf_to_images(PDF_ROOT / pdf_name, OUTPUT_ROOT, return_pic_url)}

def format_output(data: Union[str, dict[str, Any]]) -> str:
    """
    格式化输出 JSON 数据, 将文件->图片的映射关系 格式化为 [{文件名: [图片URL, 图片URL, ...]}]
    参数:
        json_data (dict[str, Any]): 要格式化的 JSON 数据。
    返回:
        str: 格式化后的 JSON 字符串。
    """
    if isinstance(data, str):
        data = json.loads(data)
    d = [ {"doc": k, "pics": v} for k,v  in data.items()]
    return json.dumps(r, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport='stdio')
    # print(convert_pdf('x.pdf'))
    # print(convert_pdfs('.', return_pic_url=True))
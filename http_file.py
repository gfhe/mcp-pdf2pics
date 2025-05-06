import requests
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from pathlib import Path

def upload_file(file_path, url):
    """
    上传单个文件到指定的 URL。
    Args:
        file_path (str): 要上传的文件路径。
        url (str): 目标 URL。
    Returns:
        str: 上传成功后返回的 URL。
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"文件 {file_path} 不存在")
            return None
        logger.info(f"上传文件 {file_path} 到 {url}")
        with open(file_path, 'rb') as file:
            files = {'file': file}
            response = requests.post(url, files=files)
            response.raise_for_status()
            logger.info(f"文件 {file_path} 上传成功，响应状态码: {response.status_code}")
            return url + '/' + file_path.name
    except requests.RequestException as e:
        logger.error(f"文件 {file_path} 上传失败: {e}")
    except Exception as e:
        logger.error(f"处理文件 {file_path} 时发生未知错误: {e}")
    return None

def concurrent_upload(file_list, url, max_workers=5):
    """
    并发上传文件列表到指定的 URL。
    Args:
        file_list (list): 要上传的文件路径列表。
        url (str): 目标 URL。
        max_workers (int): 最大并发线程数。
    Returns:
        list: 成功上传的文件的 URL 列表。
    """
    urls = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(upload_file, file, url) for file in file_list]
        for future in futures:
            result = future.result()
            if result:
                urls.append(result)
    return urls

if __name__ == "__main__":
    file_list = ['app.jar', 'another_file.jar']  # 替换为实际的文件列表
    url = 'http://8.219.74.228'
    uploaded_urls = concurrent_upload(file_list, url)
    logger.info(f"上传成功的文件 URL 列表: {uploaded_urls}")
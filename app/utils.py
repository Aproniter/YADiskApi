import os
import tempfile
import aiohttp
from typing import List, Tuple, Dict, Any
from app.logger import get_logger

logger = get_logger("utils")


yandex_api_link = "https://cloud-api.yandex.net/v1/disk/public/resources"


async def fetch_files(public_key: str) -> Tuple[Any, bool]:
    """
    Извлекает файлы из публичного диска Яндекс по указанному публичному ключу.
    Args:
        public_key (str): Публичный ключ для доступа к ресурсам.
    Returns:
        Tuple[Any, bool]: Кортеж, содержащий либо ошибку (если есть), либо список файлов, и булево значение,
                          указывающее на успешность операции.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{yandex_api_link}?public_key={public_key}") as resp:
            data = await resp.json()
            if "error" in data:
                return data["error"], False
            return data["_embedded"]["items"], True


async def get_files_recursive(public_key: str) -> Tuple[List[Dict[str, str]], bool]:
    """
    Рекурсивно извлекает файлы и папки с публичного диска Яндекс по указанному ключу.
    Args:
        public_key (str): Публичный ключ для доступа к ресурсам.
    Returns:
        Tuple[List[Dict[str, str]], bool]: Кортеж, содержащий список файлов (если найдены) и булево значение,
                                              указывающее на успешность операции.
    """
    folder_url = f"{yandex_api_link}?public_key={public_key}"
    files = []

    async def fetch_folder_contents(url: str) -> None:
        """
        Извлекает содержимое папки по указанному URL и добавляет файлы в общий список.
        Args:
            url (str): URL для извлечения содержимого папки.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if "error" in data:
                    return data["error"], False
                for item in data["_embedded"]["items"]:
                    if item["type"] == "file":
                        files.append(
                            {
                                "name": item["name"],
                                "download_url": item["file"].replace("&", "|"),
                                "path": item["path"][1:],
                            }
                        )
                    elif item["type"] == "dir":
                        dir_url = folder_url + f'&path={item["path"]}'
                        await fetch_folder_contents(dir_url)

    await fetch_folder_contents(folder_url)
    return files, True


async def download_file(download_url: str, file_name: str) -> str:
    """
    Загружает файл по указанному URL и сохраняет его во временную директорию.
    Args:
        download_url (str): URL для загрузки файла.
        file_name (str): Имя файла для сохранения.
    Returns:
        str: Путь к загруженному файлу.
    """
    temp_dir = tempfile.gettempdir()

    file_name = os.path.join(temp_dir, file_name)

    async with aiohttp.ClientSession() as session:
        async with session.get(download_url) as resp:
            with open(file_name, "wb") as f:
                f.write(await resp.read())

    return file_name

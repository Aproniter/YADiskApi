import os
import zipfile
import tempfile
from flask import Blueprint, render_template, request, send_file
from cachetools import TTLCache

from app.utils import download_file, get_files_recursive
from app.logger import get_logger

logger = get_logger(__file__)

main = Blueprint("main", __name__)

file_cache = TTLCache(maxsize=100, ttl=600)


@main.route("/")
def index() -> str:
    """
    Отображает главную страницу.
    Returns:
        str: HTML-шаблон главной страницы.
    """
    return render_template("index.html")


@main.route("/list_files", methods=["POST"])
async def list_files() -> dict:
    """
    Получает список файлов для заданного публичного ключа.
    Если ключ уже имеется в кэше, возвращает закэшированные файлы.
    В противном случае запрашивает файловую систему.
    Returns:
        dict: Словарь с файлами или сообщением об ошибке.
    """
    public_key = request.form["public_key"]
    if public_key in file_cache:
        return {"files": file_cache[public_key]}
    result, ok = await get_files_recursive(public_key)
    if ok:
        file_cache[public_key] = result
        return {"files": result}
    return {"error": result}


@main.route("/download/", methods=["GET"])
async def download() -> dict:
    """
    Обрабатывает запрос на загрузку файла.
    Извлекает путь и имя файла из аргументов запроса и отправляет файл пользователю.
    Returns:
        dict: Словарь с сообщением об ошибке или отправляемый файл.
    """
    file_path = request.args.get("file_path")

    try:
        file_path = file_path.split("|")
        file_name = next(
            (f.split("=")[1] for f in file_path if f.startswith("filename")), None
        )
        file_path = await download_file("&".join(file_path), file_name)
        return send_file(file_path, as_attachment=True)
    except KeyError as e:
        logger.error(e)
    return {"error": "Файл не найден"}, 404


@main.route("/multiple-download", methods=["POST", "GET"])
async def multiple_download() -> dict:
    """
    Обрабатывает запрос на загрузку нескольких файлов и отправляет их как ZIP-архив.
    Получает список URL файлов из запроса, загружает их и упаковывает в ZIP.
    Returns:
        dict: Словарь с сообщением об ошибке или отправляемый ZIP-файл.
    """
    file_urls = request.json.get("file_urls", [])

    if not file_urls:
        return {"error": "No files provided"}, 400

    downloaded_files = []
    for file_path in file_urls:
        try:
            file_path = file_path.split("|")
            file_name = next(
                (f.split("=")[1] for f in file_path if f.startswith("filename")), None
            )
            file_path = await download_file("&".join(file_path), file_name)
            downloaded_files.append(file_path)
        except KeyError as e:
            logger.error(e)

    if not downloaded_files:
        return {"error": "No valid files found"}, 404

    zip_file_path = "downloaded_files.zip"

    temp_dir = tempfile.gettempdir()

    zip_file_path = os.path.join(temp_dir, zip_file_path)
    with zipfile.ZipFile(zip_file_path, "w") as zipf:
        for file in downloaded_files:
            zipf.write(file, os.path.basename(file))

    return send_file(zip_file_path, as_attachment=True)

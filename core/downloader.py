import yt_dlp
import os
import threading
import requests
import sys
from PIL import Image
from io import BytesIO
from typing import Optional, Callable, Dict, Any, Tuple, List


class Downloader:
    """
    Класс для загрузки видео и аудио с различных платформ с использованием yt-dlp.

    Предоставляет функциональность для получения информации о видео, загрузки
    видео и аудио, а также обработки прогресса и отмены загрузки.
    """

    def __init__(self, progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                 status_callback: Optional[Callable[[str, Optional[str]], None]] = None) -> None:
        """
        Инициализирует Downloader.

        Args:
            progress_callback: Функция обратного вызова для обновления прогресса загрузки.
                               Принимает словарь с данными о прогрессе.
            status_callback: Функция обратного вызова для обновления статуса загрузки.
                             Принимает строку статуса и опциональный цвет.
        """
        self.progress_callback: Optional[Callable[[Dict[str, Any]], None]] = progress_callback
        self.status_callback: Optional[Callable[[str, Optional[str]], None]] = status_callback
        self.formats_dict: Dict[str, str] = {}
        self.is_running: threading.Event = threading.Event()
        self._cancel_download: threading.Event = threading.Event()

    def _get_ffmpeg_path(self) -> str:
        """
        Определяет путь к исполняемому файлу FFmpeg.

        Проверяет, запущено ли приложение из PyInstaller (в этом случае FFmpeg
        находится во временной папке sys._MEIPASS) или из исходников (ищет в папке проекта).

        Returns:
            Абсолютный путь к исполняемому файлу FFmpeg.
        """
        # Если запущено из .exe (PyInstaller), ffmpeg будет во временной папке sys._MEIPASS
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, "ffmpeg.exe")
        # Если запущено из исходников, ищем в папке проекта
        return os.path.abspath("ffmpeg.exe")

    def get_info(self, url: str) -> Tuple[List[str], bool, bool, Optional[str]]:
        """
        Получает информацию о видео по заданному URL.

        Пытается извлечь информацию о доступных форматах, наличии видео/аудио потоков
        и URL миниатюры. Обрабатывает ошибки, связанные с cookies, переключаясь
        в анонимный режим при необходимости.

        Args:
            url: URL видео.

        Returns:
            Кортеж, содержащий:
            - Список отсортированных строк, описывающих доступные форматы.
            - Булево значение, указывающее, есть ли видеопотоки.
            - Булево значение, указывающее, есть ли аудиопотоки.
            - Опциональный URL миниатюры видео.

        Raises:
            Exception: Если URL указывает на страницу авторизации.
            yt_dlp.utils.DownloadError: В случае других ошибок загрузки информации.
        """
        if 'login' in url.lower() or 'auth' in url.lower() or 'required=true' in url.lower():
            raise Exception("Вы указали ссылку на страницу авторизации...")

        opts: Dict[str, Any] = {'quiet': True, 'no_warnings': True, 'cookiesfrombrowser': ('chrome',),
                                'noplaylist': True, 'ignore_no_cookies_error': True}

        info: Dict[str, Any]
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            # Расширенная проверка ошибок cookies, включая PermissionError
            if 'cookie' in str(e).lower() or 'permission' in str(e).lower() or 'copy' in str(e).lower():
                if self.status_callback: self.status_callback("Cookies недоступны, анонимный режим...", "gray")
                opts.pop('cookiesfrombrowser')
                with yt_dlp.YoutubeDL(opts) as ydl_fallback:
                    info = ydl_fallback.extract_info(url, download=False)
            else:
                raise

        formats: List[Dict[str, Any]] = info.get('formats', [])
        has_video_stream: bool = any(f.get('vcodec') != 'none' for f in formats)
        has_audio_stream: bool = any(f.get('acodec') != 'none' for f in formats)
        thumbnail_url: Optional[str] = info.get('thumbnail')

        extractor: str = info.get('extractor', '').lower() if 'extractor' in info else ''
        is_rutube: bool = 'rutube' in extractor

        video_formats: List[Dict[str, Any]] = [f for f in formats if f.get('vcodec') != 'none']
        self.formats_dict = {}

        heights: List[int] = sorted(list(set(f.get('height') for f in video_formats if f.get('height'))), reverse=True)

        for h in heights:
            label: str = f"{h}p"

            if is_rutube:
                fmt: str = f"best[height<={h}][ext=mp4][vcodec^=avc]/best[height<={h}][ext=mp4]/best[height<={h}]"
            else:
                fmt: str = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"

            self.formats_dict[label] = fmt

        if not self.formats_dict and has_video_stream:
            if is_rutube:
                self.formats_dict = {"Лучшее качество": "best[ext=mp4][vcodec^=avc]/best[ext=mp4]/best"}
            else:
                self.formats_dict = {"Лучшее качество": "bestvideo+bestaudio/best"}

        sorted_formats: List[str] = list(self.formats_dict.keys())

        return sorted_formats, has_video_stream, has_audio_stream, thumbnail_url

    def get_thumbnail_image(self, url: str) -> Optional[Image.Image]:
        """
        Загружает изображение миниатюры по URL.

        Args:
            url: URL изображения миниатюры.

        Returns:
            Объект PIL.Image.Image, если загрузка прошла успешно, иначе None.
        """
        try:
            response: requests.Response = requests.get(url, stream=True)
            response.raise_for_status()
            image: Image.Image = Image.open(BytesIO(response.content))
            return image
        except Exception:
            return None

    def _download(self, url: str, opts: Dict[str, Any]) -> None:
        """
        Внутренний метод для выполнения загрузки с использованием yt-dlp.

        Устанавливает хук прогресса, обрабатывает отмену загрузки и ошибки,
        связанные с cookies.

        Args:
            url: URL для загрузки.
            opts: Словарь опций для yt-dlp.

        Raises:
            yt_dlp.utils.DownloadError: В случае ошибок загрузки, не связанных с cookies.
        """
        self._cancel_download.clear()
        self.is_running.set()

        def progress_hook(d: Dict[str, Any]) -> None:
            if self._cancel_download.is_set():
                raise yt_dlp.utils.DownloadCancelled()
            if self.progress_callback:
                self.progress_callback(d)

        opts['progress_hooks'] = [progress_hook]

        # Используем умный путь к ffmpeg, который работает и в .exe
        ffmpeg_path: str = self._get_ffmpeg_path()
        if os.path.exists(ffmpeg_path):
            opts['ffmpeg_location'] = ffmpeg_path

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            # Расширенная проверка ошибок cookies для второго этапа
            if ('cookie' in str(e).lower() or 'permission' in str(e).lower() or 'copy' in str(
                    e).lower()) and 'cookiesfrombrowser' in opts:
                if self.status_callback: self.status_callback("Cookies недоступны, анонимный режим...", "gray")
                opts.pop('cookiesfrombrowser')
                try:
                    self._download(url, opts)
                except yt_dlp.utils.DownloadCancelled:
                    pass
                except Exception as inner_e:
                    raise inner_e
            else:
                raise e
        except yt_dlp.utils.DownloadCancelled:
            pass
        finally:
            self.is_running.clear()

    def download_video(self, url: str, format_str: str, path: str) -> None:
        """
        Загружает видео с заданного URL в указанном формате.

        Args:
            url: URL видео для загрузки.
            format_str: Строка формата yt-dlp для видео (например, "bestvideo+bestaudio").
            path: Путь для сохранения загруженного видео.
        """
        opts: Dict[str, Any] = {
            'format': format_str,
            'outtmpl': os.path.join(path, '%(title)s.%(ext)s'),
            'cookiesfrombrowser': ('chrome',),
        }

        if '+' in format_str:
            opts['merge_output_format'] = 'mp4'
            opts['postprocessors'] = [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': 'mp4',
            }]

        self._download(url, opts)

    def download_audio(self, url: str, path: str, audio_quality: str = '192K') -> None:
        """
        Загружает аудио с заданного URL в формате MP3.

        Args:
            url: URL аудио для загрузки.
            path: Путь для сохранения загруженного аудио.
            audio_quality: Качество аудио (например, "192K", "320K"). По умолчанию "192K".
        """
        format_str: str = 'bestaudio/worst'
        opts: Dict[str, Any] = {
            'format': format_str,
            'outtmpl': os.path.join(path, '%(title)s.mp3'),
            'extract_audio': True,
            'audio_format': 'mp3',
            'postprocessor_args': ['-b:a', audio_quality],
            'cookiesfrombrowser': ('chrome',),
            'keepvideo': False,
        }
        self._download(url, opts)

    def cancel(self) -> None:
        """
        Устанавливает флаг отмены загрузки.

        Это сигнализирует активной загрузке о необходимости прекратить работу.
        """
        self._cancel_download.set()

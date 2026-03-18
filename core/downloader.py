import yt_dlp
import os
import threading
import requests
import re
import sys
from PIL import Image
from io import BytesIO

class Downloader:
    def __init__(self, progress_callback=None, status_callback=None):
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.formats_dict = {}
        self.is_running = threading.Event()
        self._cancel_download = threading.Event()

    def _get_ffmpeg_path(self):
        # Если запущено из .exe (PyInstaller), ffmpeg будет во временной папке sys._MEIPASS
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, "ffmpeg.exe")
        # Если запущено из исходников, ищем в папке проекта
        return os.path.abspath("ffmpeg.exe")

    def get_info(self, url):
        if 'login' in url.lower() or 'auth' in url.lower() or 'required=true' in url.lower():
            raise Exception("Вы указали ссылку на страницу авторизации...")

        opts = {'quiet': True, 'no_warnings': True, 'cookiesfrombrowser': ('chrome',), 'noplaylist': True, 'ignore_no_cookies_error': True}
        
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

        formats = info.get('formats', [])
        has_video_stream = any(f.get('vcodec') != 'none' for f in formats)
        has_audio_stream = any(f.get('acodec') != 'none' for f in formats)
        thumbnail_url = info.get('thumbnail')
        
        extractor = info.get('extractor', '').lower() if 'extractor' in info else ''
        is_rutube = 'rutube' in extractor

        video_formats = [f for f in formats if f.get('vcodec') != 'none']
        self.formats_dict = {}
        
        heights = sorted(list(set(f.get('height') for f in video_formats if f.get('height'))), reverse=True)

        for h in heights:
            label = f"{h}p"
            
            if is_rutube:
                fmt = f"best[height<={h}][ext=mp4][vcodec^=avc]/best[height<={h}][ext=mp4]/best[height<={h}]" 
            else:
                fmt = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
                
            self.formats_dict[label] = fmt
            
        if not self.formats_dict and has_video_stream:
            if is_rutube:
                self.formats_dict = {"Лучшее качество": "best[ext=mp4][vcodec^=avc]/best[ext=mp4]/best"}
            else:
                self.formats_dict = {"Лучшее качество": "bestvideo+bestaudio/best"}

        sorted_formats = list(self.formats_dict.keys())
        
        return sorted_formats, has_video_stream, has_audio_stream, thumbnail_url

    def get_thumbnail_image(self, url):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            return image
        except Exception:
            return None

    def _download(self, url, opts):
        self._cancel_download.clear()
        self.is_running.set()

        def progress_hook(d):
            if self._cancel_download.is_set():
                raise yt_dlp.utils.DownloadCancelled()
            if self.progress_callback:
                self.progress_callback(d)
        
        opts['progress_hooks'] = [progress_hook]
        
        # Используем умный путь к ffmpeg, который работает и в .exe
        ffmpeg_path = self._get_ffmpeg_path()
        if os.path.exists(ffmpeg_path):
            opts['ffmpeg_location'] = ffmpeg_path

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            # Расширенная проверка ошибок cookies для второго этапа
            if ('cookie' in str(e).lower() or 'permission' in str(e).lower() or 'copy' in str(e).lower()) and 'cookiesfrombrowser' in opts:
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

    def download_video(self, url, format_str, path):
        opts = {
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

    def download_audio(self, url, path, audio_quality='192K'):
        format_str = 'bestaudio/worst'
        opts = {
            'format': format_str,
            'outtmpl': os.path.join(path, '%(title)s.mp3'),
            'extract_audio': True,
            'audio_format': 'mp3',
            'postprocessor_args': ['-b:a', audio_quality],
            'cookiesfrombrowser': ('chrome',),
            'keepvideo': False,
        }
        self._download(url, opts)

    def cancel(self):
        self._cancel_download.set()

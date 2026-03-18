import yt_dlp
import os

class VideoDownloader:
    def __init__(self, progress_callback=None, status_callback=None):
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.formats_dict = {}

    def get_info(self, url):
        if 'login' in url.lower() or 'auth' in url.lower() or 'required=true' in url.lower():
            raise Exception("Вы указали ссылку на страницу авторизации.\nПожалуйста, авторизуйтесь в браузере, перейдите на страницу самого видео и скопируйте ссылку оттуда.")

        opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'cookiesfrombrowser': ('chrome',), 
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            },
            'noplaylist': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:
            opts.pop('cookiesfrombrowser', None)
            with yt_dlp.YoutubeDL(opts) as ydl_fallback:
                info = ydl_fallback.extract_info(url, download=False)
        
        formats = info.get('formats', [])
        
        if not formats and info.get('url'):
            self.formats_dict = {"Прямая ссылка (Best)": "best"}
        else:
            self.formats_dict = {f"{f.get('height', 'unknown')}p ({f.get('ext', 'unknown')})": f.get('format_id', 'best')
                                 for f in formats if f.get('vcodec') != 'none'}
        
        if not self.formats_dict:
            self.formats_dict = {"Лучшее качество": "best"}
        
        unique_dict = {}
        for k, v in self.formats_dict.items():
            if k not in unique_dict:
                unique_dict[k] = v
        self.formats_dict = unique_dict
        
        return sorted(self.formats_dict.keys(), 
                     key=lambda x: int(x.split('p')[0]) if 'p' in x and x.split('p')[0].isdigit() else 0, 
                     reverse=True)

    def download_video(self, url, format_id, path):
        format_str = f'{format_id}+bestaudio[ext=m4a]/bestaudio/best' if format_id != 'best' else 'best'
        
        opts = {
            'format': format_str,
            'outtmpl': os.path.join(path, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'cookiesfrombrowser': ('chrome',),
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            }
        }
        
        if self.progress_callback:
            opts['progress_hooks'] = [self._internal_progress_hook]

        if os.path.exists("ffmpeg.exe"):
            opts['ffmpeg_location'] = os.path.abspath("ffmpeg.exe")
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            if 'ffmpeg' in str(e).lower() or 'ffprobe' in str(e).lower() or 'merge' in str(e).lower():
                if self.status_callback:
                    self.status_callback("FFmpeg не найден. Качаем обычное качество...", "orange")
                
                opts_no_ffmpeg = opts.copy()
                opts_no_ffmpeg['format'] = 'best' 
                opts_no_ffmpeg.pop('merge_output_format', None) 
                
                with yt_dlp.YoutubeDL(opts_no_ffmpeg) as ydl_fallback_no_ffmpeg:
                    ydl_fallback_no_ffmpeg.download([url])
            else:
                opts.pop('cookiesfrombrowser', None)
                with yt_dlp.YoutubeDL(opts) as ydl_fallback:
                    ydl_fallback.download([url])

    def download_audio(self, url, path, filename):
        # If a filename is provided, use it. Otherwise, yt-dlp will use the video title.
        outtmpl = os.path.join(path, filename) if filename else os.path.join(path, '%(title)s.%(ext)s')

        opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'outtmpl': outtmpl,
            'extract_audio': True,
            'audio_format': 'mp3',
            'audio_quality': '192K', # Standard quality
            'postprocessor_args': [
                '-ar', '44100'
            ],
            'cookiesfrombrowser': ('chrome',),
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            }
        }

        if self.progress_callback:
            opts['progress_hooks'] = [self._internal_progress_hook]

        if os.path.exists("ffmpeg.exe"):
            opts['ffmpeg_location'] = os.path.abspath("ffmpeg.exe")

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception:
            opts.pop('cookiesfrombrowser', None)
            with yt_dlp.YoutubeDL(opts) as ydl_fallback:
                ydl_fallback.download([url])


    def _internal_progress_hook(self, d):
        if self.progress_callback:
            self.progress_callback(d)

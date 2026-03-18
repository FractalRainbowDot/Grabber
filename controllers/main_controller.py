import threading
import re
import os
from core.downloader import VideoDownloader
from ui.app_window import AppWindow

class MainController:
    def __init__(self):
        self.view = AppWindow(self)
        self.downloader = VideoDownloader(
            progress_callback=self.handle_progress,
            status_callback=self.view.set_status
        )

    def handle_get_info(self, url):
        threading.Thread(target=self._get_info_task, args=(url,), daemon=True).start()

    def _get_info_task(self, url):
        try:
            formats = self.downloader.get_info(url)
            self.view.after(0, self._on_info_success, formats)
        except Exception as e:
            error_msg = str(e)
            if 'Unsupported URL' in error_msg:
                error_msg = ("Неподдерживаемый сайт или ссылка ведет на закрытую страницу.\n\n"
                             "1. Убедитесь, что скопировали ссылку именно на видео, а не на страницу входа.\n"
                             "2. Если видео доступно только после покупки/входа, авторизуйтесь на сайте через браузер Chrome.")
            elif 'HTTP Error 403' in error_msg:
                error_msg = "Доступ запрещен (HTTP 403).\nСкорее всего, требуется авторизация в браузере Chrome."
            
            self.view.after(0, self.view.show_error, error_msg)
        finally:
            self.view.after(0, self.view.reset_check_ui)

    def _on_info_success(self, formats):
        self.view.set_formats(formats)
        self.view.enable_download()

    def handle_download(self, url, quality, path, download_type, filename=None):
        threading.Thread(target=self._download_task, args=(url, quality, path, download_type, filename), daemon=True).start()

    def _download_task(self, url, quality, path, download_type, filename=None):
        try:
            if download_type == "Видео":
                format_id = self.downloader.formats_dict.get(quality, 'best')
                self.downloader.download_video(url, format_id, path)
                self.view.after(0, self.view.show_info, "Готово", "Видео скачано!")
            elif download_type == "Аудио (mp3)":
                self.downloader.download_audio(url, path, filename)
                self.view.after(0, self.view.show_info, "Готово", "Аудио скачано!")

        except Exception as e:
            error_msg = str(e)
            if 'ffmpeg' in error_msg.lower() or 'ffprobe' in error_msg.lower():
                error_msg = ("ОШИБКА: FFmpeg не найден.\n\n"
                             "Для конвертации в MP3 требуется FFmpeg. Убедитесь, что он "
                             "установлен и доступен в системном PATH.\n\n"
                             "РЕШЕНИЕ:\n"
                             "1. Скачайте FFmpeg и добавьте его в PATH.\n"
                             "2. Перезапустите программу или компьютер.\n"
                             "3. Поместите ffmpeg.exe в папку с проектом.")
            self.view.after(0, self.view.show_error, error_msg)
        finally:
            self.view.after(0, self.view.reset_download_ui)

    def handle_progress(self, d):
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%')
            clean_p = re.sub(r'\x1b\[[0-9;]*m', '', p).replace('%', '')

            try:
                float_p = float(clean_p) / 100
                self.view.after(0, self.view.update_progress_ui, float_p, p)
            except Exception:
                pass

        if d['status'] == 'finished':
            # For audio, the next step is converting, not just processing
            if d.get('info_dict', {}).get('extractor') == 'audio':
                 self.view.after(0, self.view.set_status, "Конвертация в MP3...", "orange")
            else:
                 self.view.after(0, self.view.set_status, "Обработка (FFmpeg)...", "orange")


    def run(self):
        self.view.mainloop()

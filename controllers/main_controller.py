import threading
import re
import os
import sys
import traceback
import glob
import time
from yt_dlp.utils import DownloadCancelled
from core.downloader import Downloader
from ui.app_window import AppWindow

class MainController:
    def __init__(self):
        self.view = AppWindow(self)
        self.downloader = Downloader(
            progress_callback=self.handle_progress,
            status_callback=self.view.set_status
        )
        self.download_path = None

    def handle_get_info(self, url):
        threading.Thread(target=self._get_info_task, args=(url,), daemon=True).start()

    def _get_info_task(self, url):
        try:
            formats, has_video, has_audio, thumbnail_url = self.downloader.get_info(url)
            self.view.after(0, self._on_info_success, formats, has_video, has_audio)
            if thumbnail_url:
                threading.Thread(target=self._fetch_thumbnail_task, args=(thumbnail_url,), daemon=True).start()
        except Exception:
            error_msg = f"Ошибка при получении информации о видео:\n\n{traceback.format_exc()}"
            self.view.after(0, self.view.show_error, error_msg)
            self.view.after(0, self.view.set_download_options, False, False)
        finally:
            self.view.after(0, self.view.reset_check_ui)

    def _fetch_thumbnail_task(self, url):
        image_data = self.downloader.get_thumbnail_image(url)
        if image_data:
            self.view.after(0, self.view.set_thumbnail, image_data)

    def _on_info_success(self, formats, has_video, has_audio):
        self.view.set_formats(formats)
        self.view.set_download_options(has_video, has_audio)
        if has_video or has_audio:
            self.view.enable_download()

    def handle_download(self, url, quality, path, download_type, audio_quality=None):
        self.download_path = path
        threading.Thread(target=self._download_task, args=(url, quality, path, download_type, audio_quality), daemon=True).start()

    def _download_task(self, url, quality, path, download_type, audio_quality):
        try:
            if download_type == "Видео":
                format_id = self.downloader.formats_dict.get(quality, 'best')
                self.downloader.download_video(url, format_id, path)
            elif download_type == "Аудио (mp3)":
                self.downloader.download_audio(url, path, audio_quality)
            
            if not self.downloader._cancel_download.is_set():
                 self.view.after(0, self.view.set_status, "Готово!", "green")

        except Exception:
            if not self.downloader._cancel_download.is_set():
                error_msg = f"Ошибка во время скачивания:\n\n{traceback.format_exc()}"
                self.view.after(0, self.view.show_error, error_msg)
        finally:
            if self.downloader._cancel_download.is_set():
                self.view.after(0, self.view.set_status, "Остановка загрузки...", "orange")
                self.view.after(1000, self._cleanup_with_retries, 30)
            self.view.after(0, self.view.reset_download_ui)

    def cancel_download(self):
        self.downloader.cancel()

    def _cleanup_with_retries(self, retries_left):
        if not self.download_path: return

        try:
            import gc
            gc.collect() 

            files_to_delete = glob.glob(os.path.join(self.download_path, "*.part")) + \
                              glob.glob(os.path.join(self.download_path, "*.ytdl"))
            
            if not files_to_delete:
                return 

            all_deleted = True
            for f in files_to_delete:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except PermissionError:
                        all_deleted = False 
            
            if all_deleted:
                self.view.set_status("Временные файлы удалены", "gray")
            else:
                if retries_left > 0:
                    self.view.set_status(f"Ожидание освобождения файла... ({retries_left} сек)", "orange")
                    self.view.after(1000, self._cleanup_with_retries, retries_left - 1)
                else:
                    error_msg = ("Не удалось удалить временный файл.\n\n"
                                 "Процесс загрузки (yt-dlp) завис и не отпускает файл.\n"
                                 "Файл будет освобожден операционной системой при закрытии приложения, "
                                 "после чего вы сможете удалить его вручную.")
                    self.view.show_error(error_msg)
                    self.view.set_status("Ошибка удаления файлов", "red")

        except Exception as e:
            error_msg = f"Непредвиденная ошибка при очистке:\n\n{traceback.format_exc()}"
            self.view.show_error(error_msg)

    def handle_progress(self, d):
        if self.downloader._cancel_download.is_set(): return
        status = d.get('status')
        if status == 'downloading':
            percent_str = d.get('_percent_str', '0.0%').strip()
            size = d.get('total_bytes_str') or d.get('_total_bytes_estimate_str')
            speed = d.get('_speed_str')
            eta = d.get('_eta_str')
            details_parts = []
            if size: details_parts.append(f"of {size}")
            if speed: details_parts.append(f"at {speed}")
            if eta: details_parts.append(f"ETA {eta}")
            details_str = " ".join(details_parts)
            clean_p = re.sub(r'\x1b\[[0-9;]*m', '', percent_str).replace('%', '')
            try:
                progress = float(clean_p) / 100
                progress_data = {'progress': progress, 'percent_str': percent_str, 'details_str': details_str}
                self.view.after(0, self.view.update_progress_ui, progress_data)
            except (ValueError, TypeError): pass
        elif status == 'finished': self.view.after(0, self.view.set_status, "Завершение загрузки...", "gray")
        elif status == 'postprocessing': 
            self.view.after(0, self.view.set_status, "Конвертация видео (ожидайте)...", "orange")

    def restart_app(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def run(self):
        self.view.mainloop()

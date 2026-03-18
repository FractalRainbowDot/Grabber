import threading
import re
import os
import sys
import traceback
import glob
from typing import Optional, List, Dict, Any, Tuple

from core.downloader import Downloader
from ui.app_window import AppWindow


class MainController:
    """
    Контроллер для управления логикой приложения Grabber.

    Отвечает за взаимодействие между пользовательским интерфейсом (AppWindow)
    и логикой загрузки (Downloader), а также за обработку потоков и ошибок.
    """

    def __init__(self) -> None:
        """
        Инициализирует MainController, создавая экземпляр AppWindow и Downloader.
        """
        self.view: AppWindow = AppWindow(self)
        self.downloader: Downloader = Downloader(
            progress_callback=self.handle_progress,
            status_callback=self.view.set_status
        )
        self.download_path: Optional[str] = None

    def handle_get_info(self, url: str) -> None:
        """
        Обрабатывает запрос на получение информации о видео по URL.

        Запускает отдельный поток для выполнения задачи получения информации,
        чтобы не блокировать основной поток пользовательского интерфейса.

        Args:
            url: URL видео, информацию о котором нужно получить.
        """
        threading.Thread(target=self._get_info_task, args=(url,), daemon=True).start()

    def _get_info_task(self, url: str) -> None:
        """
        Фоновая задача для получения информации о видео.

        Выполняет запрос к Downloader для получения форматов, наличия видео/аудио
        и URL миниатюры. Обновляет UI после получения информации или в случае ошибки.

        Args:
            url: URL видео.
        """
        try:
            formats: List[Dict[str, Any]]
            has_video: bool
            has_audio: bool
            thumbnail_url: Optional[str]

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

    def _fetch_thumbnail_task(self, url: str) -> None:
        """
        Фоновая задача для загрузки миниатюры видео.

        Загружает изображение миниатюры по URL и передает его в UI для отображения.

        Args:
            url: URL миниатюры.
        """
        image_data: Optional[bytes] = self.downloader.get_thumbnail_image(url)
        if image_data:
            self.view.after(0, self.view.set_thumbnail, image_data)

    def _on_info_success(self, formats: List[Dict[str, Any]], has_video: bool, has_audio: bool) -> None:
        """
        Обновляет пользовательский интерфейс после успешного получения информации о видео.

        Args:
            formats: Список доступных форматов видео.
            has_video: Флаг, указывающий, есть ли видеопотоки.
            has_audio: Флаг, указывающий, есть ли аудиопотоки.
        """
        self.view.set_formats(formats)
        self.view.set_download_options(has_video, has_audio)
        if has_video or has_audio:
            self.view.enable_download()

    def handle_download(self, url: str, quality: str, path: str, download_type: str,
                        audio_quality: Optional[str] = None) -> None:
        """
        Обрабатывает запрос на скачивание видео или аудио.

        Запускает отдельный поток для выполнения задачи скачивания,
        чтобы не блокировать основной поток пользовательского интерфейса.

        Args:
            url: URL видео/аудио для скачивания.
            quality: Выбранное качество видео (например, "best", "1080p") или аудио.
            path: Путь для сохранения файла.
            download_type: Тип загрузки ("Видео" или "Аудио (mp3)").
            audio_quality: Опциональное качество аудио для загрузки аудио.
        """
        self.download_path = path
        threading.Thread(target=self._download_task, args=(url, quality, path, download_type, audio_quality),
                         daemon=True).start()

    def _download_task(self, url: str, quality: str, path: str, download_type: str,
                       audio_quality: Optional[str]) -> None:
        """
        Фоновая задача для скачивания видео или аудио.

        Выполняет загрузку файла с использованием Downloader и обновляет статус в UI.
        Обрабатывает ошибки и отмену загрузки.

        Args:
            url: URL видео/аудио для скачивания.
            quality: Выбранное качество видео или аудио.
            path: Путь для сохранения файла.
            download_type: Тип загрузки ("Видео" или "Аудио (mp3)").
            audio_quality: Опциональное качество аудио для загрузки аудио.
        """
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

    def cancel_download(self) -> None:
        """
        Отменяет текущую загрузку, вызывая метод отмены у Downloader.
        """
        self.downloader.cancel()

    def _cleanup_with_retries(self, retries_left: int) -> None:
        """
        Попытки очистки временных файлов после отмены загрузки.

        Использует повторные попытки с задержкой, если файлы заняты,
        и уведомляет пользователя в случае неудачи.

        Args:
            retries_left: Количество оставшихся попыток очистки.
        """
        if not self.download_path: return

        try:
            import gc
            gc.collect()

            files_to_delete: List[str] = glob.glob(os.path.join(self.download_path, "*.part")) + \
                                         glob.glob(os.path.join(self.download_path, "*.ytdl"))

            if not files_to_delete:
                return

            all_deleted: bool = True
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

    def handle_progress(self, d: Dict[str, Any]) -> None:
        """
        Обрабатывает данные о прогрессе загрузки и обновляет UI.

        Args:
            d: Словарь с данными о прогрессе от yt-dlp.
               Пример: {'status': 'downloading', '_percent_str': '10.5%', ...}
        """
        if self.downloader._cancel_download.is_set(): return
        status: Optional[str] = d.get('status')
        if status == 'downloading':
            percent_str: str = d.get('_percent_str', '0.0%').strip()
            size: Optional[str] = d.get('total_bytes_str') or d.get('_total_bytes_estimate_str')
            speed: Optional[str] = d.get('_speed_str')
            eta: Optional[str] = d.get('_eta_str')
            details_parts: List[str] = []
            if size: details_parts.append(f"of {size}")
            if speed: details_parts.append(f"at {speed}")
            if eta: details_parts.append(f"ETA {eta}")
            details_str: str = " ".join(details_parts)
            clean_p: str = re.sub(r'\x1b\[[0-9;]*m', '', percent_str).replace('%', '')
            try:
                progress: float = float(clean_p) / 100
                progress_data: Dict[str, Any] = {'progress': progress, 'percent_str': percent_str,
                                                 'details_str': details_str}
                self.view.after(0, self.view.update_progress_ui, progress_data)
            except (ValueError, TypeError):
                pass
        elif status == 'finished':
            self.view.after(0, self.view.set_status, "Завершение загрузки...", "gray")
        elif status == 'postprocessing':
            self.view.after(0, self.view.set_status, "Конвертация видео (ожидайте)...", "orange")

    def restart_app(self) -> None:
        """
        Перезапускает приложение.

        Использует sys.executable и os.execl для повторного запуска текущего скрипта,
        чтобы обеспечить чистое состояние приложения.
        """
        python: str = sys.executable
        os.execl(python, python, *sys.argv)

    def run(self) -> None:
        """
        Запускает основной цикл обработки событий пользовательского интерфейса.
        """
        self.view.mainloop()

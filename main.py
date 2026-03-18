import customtkinter as ctk
from tkinter import filedialog, messagebox
import yt_dlp
import threading
import re

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ProVideoGrabber(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Ultimate Video Grabber + Progress")
        self.geometry("600x500")

        self.formats_dict = {}

        # --- Интерфейс ---
        self.label = ctk.CTkLabel(self, text="Вставьте ссылку:", font=("Arial", 16))
        self.label.pack(pady=(20, 5))

        self.url_entry = ctk.CTkEntry(self, width=450)
        self.url_entry.pack(pady=10)

        self.check_button = ctk.CTkButton(self, text="Найти форматы", command=self.start_info_thread)
        self.check_button.pack(pady=5)

        self.quality_menu = ctk.CTkOptionMenu(self, values=["Сначала проверьте ссылку"], width=250)
        self.quality_menu.pack(pady=15)

        # Полоса прогресса
        self.progress_label = ctk.CTkLabel(self, text="Прогресс: 0%", font=("Arial", 12))
        self.progress_label.pack(pady=(10, 0))

        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.set(0)  # Устанавливаем в 0
        self.progress_bar.pack(pady=10)

        self.download_button = ctk.CTkButton(self, text="Скачать видео", command=self.start_download_thread,
                                             state="disabled", fg_color="green")
        self.download_button.pack(pady=20)

        self.status_label = ctk.CTkLabel(self, text="Готов к работе", text_color="gray")
        self.status_label.pack(pady=10)

    # --- Обработчик прогресса ---
    def progress_hook(self, d):
        if d['status'] == 'downloading':
            # Извлекаем процент из строки (удаляем лишние символы ANSI)
            p = d.get('_percent_str', '0%')
            clean_p = re.sub(r'\x1b\[[0-9;]*m', '', p).replace('%', '')

            try:
                float_p = float(clean_p) / 100
                # Обновляем UI через .after(), чтобы избежать конфликтов потоков
                self.after(0, self.update_progress_ui, float_p, p)
            except Exception:
                pass

        if d['status'] == 'finished':
            self.after(0, self._set_processing_status)

    def _set_processing_status(self, *args):
        self.status_label.configure(text="Обработка (FFmpeg)...", text_color="orange")

    def update_progress_ui(self, val, text_val):
        self.progress_bar.set(val)
        self.progress_label.configure(text=f"Загрузка: {text_val.strip()}")

    # --- Логика работы (потоки) ---
    def start_info_thread(self):
        url = self.url_entry.get().strip()
        if not url: return
        self.check_button.configure(state="disabled", text="Поиск...")
        threading.Thread(target=self.get_info, args=(url,), daemon=True).start()

    def _reset_check_button(self, *args):
        self.check_button.configure(state="normal", text="Найти форматы")

    def _show_error(self, err_msg):
        messagebox.showerror("Ошибка", err_msg)

    def get_info(self, url):
        try:
            # Проверка, что пользователь не скопировал ссылку на страницу входа
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
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception:
                    # Если с cookies не вышло, пробуем без них
                    opts.pop('cookiesfrombrowser', None)
                    with yt_dlp.YoutubeDL(opts) as ydl_fallback:
                        info = ydl_fallback.extract_info(url, download=False)
                
                formats = info.get('formats', [])
                
                # Проверяем прямые ссылки
                if not formats and info.get('url'):
                    self.formats_dict = {"Прямая ссылка (Best)": "best"}
                else:
                    self.formats_dict = {f"{f.get('height', 'unknown')}p ({f.get('ext', 'unknown')})": f.get('format_id', 'best')
                                         for f in formats if f.get('vcodec') != 'none'}
                
                if not self.formats_dict:
                    self.formats_dict = {"Лучшее качество": "best"}
                
                # Удаляем дубликаты
                unique_dict = {}
                for k, v in self.formats_dict.items():
                    if k not in unique_dict:
                        unique_dict[k] = v
                self.formats_dict = unique_dict
                
                res = sorted(self.formats_dict.keys(), 
                             key=lambda x: int(x.split('p')[0]) if 'p' in x and x.split('p')[0].isdigit() else 0, 
                             reverse=True)
                self.after(0, self.show_formats, res)
                
        except Exception as e:
            error_msg = str(e)
            if 'Unsupported URL' in error_msg:
                error_msg = ("Неподдерживаемый сайт или ссылка ведет на закрытую страницу.\n\n"
                             "1. Убедитесь, что скопировали ссылку именно на видео, а не на страницу входа.\n"
                             "2. Если видео доступно только после покупки/входа, авторизуйтесь на сайте через браузер Chrome.")
            elif 'HTTP Error 403' in error_msg:
                error_msg = "Доступ запрещен (HTTP 403).\nСкорее всего, требуется авторизация в браузере Chrome."
                             
            self.after(0, self._show_error, error_msg)
            self.after(0, self._reset_check_button)

    def show_formats(self, res):
        self.quality_menu.configure(values=res)
        if res:
            self.quality_menu.set(res[0])
        self.download_button.configure(state="normal")
        self.check_button.configure(state="normal", text="Обновить")

    def start_download_thread(self):
        url = self.url_entry.get().strip()
        format_id = self.formats_dict.get(self.quality_menu.get())
        path = filedialog.askdirectory()
        if path:
            threading.Thread(target=self.download, args=(url, format_id, path), daemon=True).start()

    def _show_info(self, *args):
        messagebox.showinfo("Готово", "Видео скачано!")

    def _reset_download_ui(self, *args):
        self.download_button.configure(state="normal")
        self.progress_bar.set(0)
        self.status_label.configure(text="Готов к работе", text_color="gray")

    def download(self, url, f_id, path):
        self.download_button.configure(state="disabled")
        
        format_str = f'{f_id}+bestaudio/best' if f_id != 'best' else 'best'
        
        opts = {
            'format': format_str,
            'outtmpl': f'{path}/%(title)s.%(ext)s',
            'progress_hooks': [self.progress_hook],
            'merge_output_format': 'mp4',
            'cookiesfrombrowser': ('chrome',),
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            }
        }
        
        try:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
            except Exception:
                opts.pop('cookiesfrombrowser', None)
                with yt_dlp.YoutubeDL(opts) as ydl_fallback:
                    ydl_fallback.download([url])
                    
            self.after(0, self._show_info)
        except Exception as e:
            self.after(0, self._show_error, str(e))
        finally:
            self.after(0, self._reset_download_ui)


if __name__ == "__main__":
    app = ProVideoGrabber()
    app.mainloop()
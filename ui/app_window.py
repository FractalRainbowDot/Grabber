import customtkinter as ctk
from tkinter import filedialog
from PIL import Image
import os
import sys
import traceback

class AppWindow(ctk.CTk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.is_downloading = False
        self.thumbnail_image = None

        self.title("Ultimate Video Grabber")
        self.geometry("600x800")

        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(pady=(10, 5), fill="x", padx=20)
        self.label = ctk.CTkLabel(top_frame, text="Вставьте ссылку:", font=("Arial", 16))
        self.label.pack(side="left", padx=(0, 10))
        self.url_entry = ctk.CTkEntry(top_frame, width=350)
        self.url_entry.pack(side="left", expand=True, fill="x")
        self.url_entry.insert(0, "https://rutube.ru/video/530acaeb3c278cd471871fd2971e46e2/")
        
        self.check_button = ctk.CTkButton(self, text="Найти форматы", command=self.on_check_clicked)
        self.check_button.pack(pady=5)
        
        self.thumbnail_label = ctk.CTkLabel(self, text="", height=180)
        self.thumbnail_label.pack(pady=(10, 5), padx=20, fill="x")
        
        self.availability_label = ctk.CTkLabel(self, text="", font=("Arial", 12), text_color="gray")
        self.availability_label.pack(pady=(5,0))
        
        self.download_type_var = ctk.StringVar(value="Видео")
        self.download_type_selector = ctk.CTkSegmentedButton(self, values=["Видео"], variable=self.download_type_var, command=self.on_download_type_change)
        self.download_type_selector.pack(pady=10)

        self.quality_menus_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.quality_menus_frame.pack(pady=15)
        
        self.quality_menu = ctk.CTkOptionMenu(self.quality_menus_frame, values=["Сначала проверьте ссылку"], width=300, state="disabled")
        self.quality_menu.pack()

        self.audio_quality_menu = ctk.CTkOptionMenu(self.quality_menus_frame, values=["Высокое (192k)", "Среднее (128k)", "Низкое (96k)"], width=300)
        
        self.progress_label = ctk.CTkLabel(self, text="Прогресс: 0%", font=("Arial", 12))
        self.progress_label.pack(pady=(5, 0))
        
        self.detailed_progress_label = ctk.CTkLabel(self, text="", font=("Arial", 10), text_color="gray")
        self.detailed_progress_label.pack(pady=(0, 5))

        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5)

        self.download_button = ctk.CTkButton(self, text="Скачать", command=self.on_download_clicked, state="disabled", fg_color="green")
        self.download_button.pack(pady=15)

        self.status_label = ctk.CTkLabel(self, text="Готов к работе", text_color="gray")
        self.status_label.pack(pady=10)
        
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=20, pady=10)
        self.restart_button = ctk.CTkButton(bottom_frame, text="Перезапуск", command=self.controller.restart_app, fg_color="#C00000", width=100)
        self.restart_button.pack(side="right")

        self.set_download_options(has_video=False, has_audio=False)
        self.url_entry.bind("<KeyPress>", self._handle_keypress)
        self.on_download_type_change("Видео")

    def show_error(self, msg):
        error_win = ctk.CTkToplevel(self)
        error_win.title("Ошибка")
        error_win.geometry("800x450")
        error_win.transient(self)
        error_win.grab_set()

        label = ctk.CTkLabel(error_win, text="Произошла непредвиденная ошибка:", font=("Arial", 16))
        label.pack(pady=(10, 5), padx=20, anchor="w")

        textbox = ctk.CTkTextbox(error_win, wrap="word", font=("Courier New", 12))
        textbox.pack(pady=10, padx=20, expand=True, fill="both")
        textbox.insert("1.0", msg)
        textbox.configure(state="disabled")

        button_frame = ctk.CTkFrame(error_win, fg_color="transparent")
        button_frame.pack(pady=10)

        def copy_to_clipboard():
            self.clipboard_clear()
            self.clipboard_append(msg)
            copy_button.configure(text="Скопировано!")
            
            def reset_text():
                try:
                    if copy_button.winfo_exists():
                        copy_button.configure(text="Скопировать лог")
                except Exception:
                    pass # Window was probably destroyed
            self.after(2000, reset_text)

        copy_button = ctk.CTkButton(button_frame, text="Скопировать лог", command=copy_to_clipboard)
        copy_button.pack(side="left", padx=10)
        
        close_button = ctk.CTkButton(button_frame, text="Закрыть", command=error_win.destroy)
        close_button.pack(side="left", padx=10)

    # ... (rest of the methods are the same)
    def set_thumbnail(self, image_data):
        if image_data:
            target_size = (320, 180)
            image_data.thumbnail(target_size, Image.Resampling.LANCZOS)
            self.thumbnail_image = ctk.CTkImage(light_image=image_data, dark_image=image_data, size=image_data.size)
            self.thumbnail_label.configure(image=self.thumbnail_image, text="")
        else:
            self.thumbnail_label.configure(image=None, text="Превью недоступно")
    def on_download_type_change(self, value):
        is_audio = value == "Аудио (mp3)"
        if is_audio:
            self.quality_menu.pack_forget()
            self.audio_quality_menu.pack()
        else:
            self.audio_quality_menu.pack_forget()
            self.quality_menu.pack()
        self.download_button.configure(text="Скачать аудио" if is_audio else "Скачать видео")
    def get_audio_quality(self):
        quality_map = { "Высокое (192k)": "192K", "Среднее (128k)": "128K", "Низкое (96k)": "96K" }
        return quality_map.get(self.audio_quality_menu.get(), "192K")
    def on_download_clicked(self):
        if self.is_downloading: self.controller.cancel_download(); return
        path = filedialog.askdirectory(title="Выберите папку для сохранения")
        if not path: return
        self.toggle_ui_for_download(True)
        audio_quality = self.get_audio_quality() if self.get_download_type() == "Аудио (mp3)" else None
        self.controller.handle_download(self.get_url(), self.get_selected_quality(), path, self.get_download_type(), audio_quality)
    def _handle_keypress(self, event):
        if event.state & 4: 
            if event.keycode == 67: event.widget.event_generate("<<Copy>>"); return "break"
            elif event.keycode == 86: event.widget.event_generate("<<Paste>>"); return "break"
            elif event.keycode == 88: event.widget.event_generate("<<Cut>>"); return "break"
            elif event.keycode == 65: event.widget.event_generate("<<SelectAll>>"); return "break"
    def toggle_ui_for_download(self, is_downloading):
        self.is_downloading = is_downloading
        if is_downloading:
            self.download_button.configure(text="Отмена", fg_color="red"); self.check_button.configure(state="disabled")
            self.url_entry.configure(state="disabled"); self.download_type_selector.configure(state="disabled")
            self.quality_menu.configure(state="disabled"); self.audio_quality_menu.configure(state="disabled")
        else:
            self.download_button.configure(text="Скачать", fg_color="green", state="normal"); self.check_button.configure(state="normal")
            self.url_entry.configure(state="normal"); self.download_type_selector.configure(state="normal")
            self.audio_quality_menu.configure(state="normal")
            self.on_download_type_change(self.download_type_var.get()); self.progress_bar.set(0)
            self.progress_label.configure(text="Прогресс: 0%"); self.detailed_progress_label.configure(text="")
    def update_progress_ui(self, data):
        self.progress_bar.set(data['progress']); self.progress_label.configure(text=f"Загрузка: {data['percent_str']}")
        self.detailed_progress_label.configure(text=data['details_str'])
    def set_download_options(self, has_video, has_audio):
        options, availability_text = [], []
        if has_video: options.append("Видео"); availability_text.append("Видео"); self.quality_menu.configure(state="normal")
        else: self.quality_menu.configure(state="disabled", values=["N/A"])
        if has_audio: options.append("Аудио (mp3)"); availability_text.append("Аудио")
        if not options:
            self.download_type_selector.configure(values=["-"], state="disabled"); self.download_type_selector.set("-")
            self.availability_label.configure(text="Ничего не найдено"); self.download_button.configure(state="disabled")
            return
        self.availability_label.configure(text=f"Доступно: {', '.join(availability_text)}")
        self.download_type_selector.configure(values=options, state="normal"); self.download_type_selector.set(options[0])
        self.on_download_type_change(options[0])
    def get_url(self): return self.url_entry.get().strip()
    def get_selected_quality(self): return self.quality_menu.get()
    def get_download_type(self): return self.download_type_var.get()
    def set_formats(self, formats):
        self.quality_menu.configure(values=formats if formats else ["N/A"])
        if formats: self.quality_menu.set(formats[0])
    def on_check_clicked(self):
        url = self.get_url()
        if not url: return
        self.check_button.configure(state="disabled", text="Поиск..."); self.availability_label.configure(text="Идет поиск...")
        self.thumbnail_label.configure(image=None, text="Загрузка превью...")
        self.controller.handle_get_info(url)
    def set_status(self, text, color="gray"): self.status_label.configure(text=text, text_color=color)
    def reset_check_ui(self): self.check_button.configure(state="normal", text="Найти форматы")
    def reset_download_ui(self): self.toggle_ui_for_download(False); self.set_status("Готов к работе")
    def enable_download(self): self.download_button.configure(state="normal"); self.check_button.configure(state="normal", text="Обновить")

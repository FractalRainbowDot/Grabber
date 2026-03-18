import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppWindow(ctk.CTk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.title("Ultimate Video Grabber + Progress")
        self.geometry("600x550") # Increased height for the new widget

        self.label = ctk.CTkLabel(self, text="Вставьте ссылку:", font=("Arial", 16))
        self.label.pack(pady=(20, 5))

        self.url_entry = ctk.CTkEntry(self, width=450)
        self.url_entry.pack(pady=10)

        self.check_button = ctk.CTkButton(self, text="Найти форматы", command=self.on_check_clicked)
        self.check_button.pack(pady=5)

        self.quality_menu = ctk.CTkOptionMenu(self, values=["Сначала проверьте ссылку"], width=250)
        self.quality_menu.pack(pady=15)

        # --- Download Type Selector ---
        self.download_type_var = ctk.StringVar(value="Видео")
        self.download_type_selector = ctk.CTkSegmentedButton(
            self, values=["Видео", "Аудио (mp3)"],
            variable=self.download_type_var,
            command=self.on_download_type_change
        )
        self.download_type_selector.pack(pady=10)

        self.progress_label = ctk.CTkLabel(self, text="Прогресс: 0%", font=("Arial", 12))
        self.progress_label.pack(pady=(10, 0))

        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=10)

        self.download_button = ctk.CTkButton(self, text="Скачать", command=self.on_download_clicked,
                                             state="disabled", fg_color="green")
        self.download_button.pack(pady=20)

        self.status_label = ctk.CTkLabel(self, text="Готов к работе", text_color="gray")
        self.status_label.pack(pady=10)

    def on_download_type_change(self, value):
        if value == "Аудио (mp3)":
            self.quality_menu.configure(state="disabled")
            self.download_button.configure(text="Скачать аудио")
        else: # "Видео"
            self.quality_menu.configure(state="normal")
            self.download_button.configure(text="Скачать видео")

    def get_url(self):
        return self.url_entry.get().strip()

    def get_selected_quality(self):
        return self.quality_menu.get()

    def get_download_type(self):
        return self.download_type_var.get()

    def set_formats(self, formats):
        self.quality_menu.configure(values=formats)
        if formats:
            self.quality_menu.set(formats[0])

    def show_error(self, msg):
        messagebox.showerror("Ошибка", msg)

    def show_info(self, title, msg):
        messagebox.showinfo(title, msg)

    def on_check_clicked(self):
        url = self.get_url()
        if not url: return
        self.check_button.configure(state="disabled", text="Поиск...")
        self.controller.handle_get_info(url)

    def on_download_clicked(self):
        url = self.get_url()
        quality = self.get_selected_quality()
        download_type = self.get_download_type()
        
        # For audio, we don't need to ask for a folder, we can ask to save a file
        if download_type == "Аудио (mp3)":
            path = filedialog.asksaveasfilename(
                defaultextension=".mp3",
                filetypes=[("MP3 Audio", "*.mp3")],
                title="Сохранить аудио как..."
            )
            # askaveasfilename returns the full path including the filename
            # we need to separate them for the downloader
            if path:
                save_path, filename = os.path.split(path)
                self.download_button.configure(state="disabled")
                self.controller.handle_download(url, quality, save_path, download_type, filename)
        else:
            path = filedialog.askdirectory(title="Выберите папку для сохранения видео")
            if path:
                self.download_button.configure(state="disabled")
                self.controller.handle_download(url, quality, path, download_type)


    def update_progress_ui(self, val, text_val):
        self.progress_bar.set(val)
        self.progress_label.configure(text=f"Загрузка: {text_val.strip()}")

    def set_status(self, text, color="gray"):
        self.status_label.configure(text=text, text_color=color)

    def reset_check_ui(self):
        self.check_button.configure(state="normal", text="Найти форматы")

    def reset_download_ui(self):
        self.download_button.configure(state="normal")
        self.progress_bar.set(0)
        self.set_status("Готов к работе")

    def enable_download(self):
        self.download_button.configure(state="normal")
        self.check_button.configure(state="normal", text="Обновить")

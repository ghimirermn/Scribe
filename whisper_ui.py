import flet as ft
from faster_whisper import WhisperModel, download_model
import threading
import json
import datetime
import os

LIGHT_PALETTE = {
    "bg": "#F2F4F6", "card": "#FFFFFF", "text": "#333333", "text_muted": "#999999",
    "subtle_bg": "#F7F9FA", "input_bg": "#FFFFFF", "border": "#E0E0E0"
}

DARK_PALETTE = {
    "bg": "#1A1D21", "card": "#24282E", "text": "#EBEBEB", "text_muted": "#8B9BA8",
    "subtle_bg": "#2C323A", "input_bg": "#1F2329", "border": "#3D4654"
}

ACCENT_COLOR = "#5D737E"
STOP_COLOR = "#E57373"
SUCCESS_COLOR = "#8DA399"
BLOSSOM_PINK = "#FFB7C5"

COMMON_LANGUAGES = {
    "en": "English", "zh": "Chinese", "es": "Spanish", "fr": "French", 
    "de": "German", "ja": "Japanese", "ru": "Russian", "ko": "Korean", 
    "pt": "Portuguese", "it": "Italian", "hi": "Hindi", "ar": "Arabic",
    "sv": "Swedish", "ne": "Nepali", "km": "Khmer", "id": "Indonesian"
}

class ScribeApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Scribe"
        self.page.window.width = 520
        self.page.window.height = 870
        self.page.horizontal_alignment = "center"
        self.page.vertical_alignment = "center"
        self.page.theme = ft.Theme(font_family="Segoe UI", color_scheme_seed=ACCENT_COLOR)
        self.page.scroll = ft.ScrollMode.ADAPTIVE

        self.is_dark_mode = False
        self.selected_file = None
        self.current_segments = []
        self.stop_event = threading.Event()
        self.processing = False

        self._init_components()
        self._apply_theme()

    def _init_components(self):
        """Initialize all UI elements and store them as class attributes"""
        
        self.title_text = ft.Text("Whisper", size=32, weight=ft.FontWeight.W_300)
        self.theme_icon = ft.IconButton(
            icon=ft.Icons.NIGHTLIGHT_ROUND,
            on_click=self.toggle_theme,
            tooltip="Toggle Theme"
        )
        
        self.file_picker = ft.FilePicker(on_result=self.on_file_picked)
        self.page.overlay.append(self.file_picker)
        
        self.path_text = ft.Text("No file selected", color=LIGHT_PALETTE["text_muted"])
        self.file_card = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.Icons.AUDIO_FILE, color=ACCENT_COLOR), self.path_text],
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=15,
            border_radius=10,
            on_click=lambda _: self.file_picker.pick_files(allow_multiple=False),
            animate=ft.Animation(300, "easeOut")
        )

        self.dd_model = ft.Dropdown(
            options=[ft.dropdown.Option(m) for m in ["tiny", "base", "small", "medium", "large-v2"]],
            value="base", label="Model", dense=True, expand=True
        )
        
        self.dd_mode = ft.Dropdown(
            options=[
                ft.dropdown.Option("transcribe", "Transcribe"),
                ft.dropdown.Option("translate", "Translate (to En)"),
            ],
            value="transcribe", label="Mode", dense=True, expand=True
        )

        self.switch_gpu = ft.Switch(active_color=ACCENT_COLOR, value=False, scale=0.8)
        self.gpu_container = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.MEMORY, size=16, color=ACCENT_COLOR),
                ft.Column([
                    ft.Text("GPU Acceleration", size=11, color=ACCENT_COLOR, weight="bold"),
                    ft.Text("Requires CUDA/Drivers", size=10)
                ], spacing=0, expand=True),
                self.switch_gpu
            ]),
            padding=12, border_radius=8,
            animate=ft.Animation(300, "easeOut")
        )

        self.settings_box = ft.Container(
            content=ft.Column([
                ft.Row([self.dd_model, ft.Container(width=10), self.dd_mode], spacing=0),
                self.gpu_container
            ], spacing=12),
            padding=20, border_radius=10,
            animate=ft.Animation(300, "easeOut")
        )

        self.btn_start = ft.ElevatedButton(
            "Start Processing", 
            on_click=self.run_transcription,
            style=ft.ButtonStyle(color="white", bgcolor=ACCENT_COLOR, padding=20),
            expand=True
        )
        
        self.btn_stop = ft.ElevatedButton(
            "Stop", icon=ft.Icons.STOP, icon_color="white",
            on_click=self.stop_transcription,
            disabled=True,
            style=ft.ButtonStyle(color="white", bgcolor=STOP_COLOR, padding=20),
            width=120
        )

        self.progress_bar = ft.ProgressBar(width=340, color=ACCENT_COLOR, bgcolor="#E0E0E0", visible=False)
        self.progress_label = ft.Text("", size=12, color=ACCENT_COLOR, visible=False)
        self.status_text = ft.Text("", size=12)
        
        self.result_area = ft.TextField(
            multiline=True, min_lines=6, max_lines=10,
            read_only=True, hint_text="Result will appear here...",
            border_color="transparent", text_size=14
        )

        self.save_picker = ft.FilePicker(on_result=self.save_result)
        self.page.overlay.append(self.save_picker)
        
        self.btn_save = ft.OutlinedButton(
            "Save Result", icon=ft.Icons.SAVE_ALT, disabled=True,
            on_click=lambda _: self.save_picker.save_file(allowed_extensions=["txt", "srt", "json"], file_name="transcript.txt"),
            style=ft.ButtonStyle(color=ACCENT_COLOR), width=200
        )

        self.main_card = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Row([self.title_text, ft.Icon(ft.Icons.FILTER_VINTAGE, color=BLOSSOM_PINK)]),
                    self.theme_icon
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=15, color="transparent"),
                self.file_card,
                ft.Divider(height=15, color="transparent"),
                self.settings_box,
                ft.Divider(height=15, color="transparent"),
                ft.Row([self.btn_start, self.btn_stop], spacing=10),
                ft.Divider(height=15, color="transparent"),
                ft.Column([self.progress_label, self.progress_bar], horizontal_alignment="center", spacing=5),
                self.status_text,
                self.result_area,
                ft.Divider(height=15, color="transparent"),
                self.btn_save
            ], horizontal_alignment="center"),
            padding=40, border_radius=20, width=460,
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=15, color=ft.Colors.with_opacity(0.05, "black")),
            animate=ft.Animation(300, "easeOut")
        )
        
        self.page.add(self.main_card)

    def _apply_theme(self):
        p = DARK_PALETTE if self.is_dark_mode else LIGHT_PALETTE
        
        self.page.bgcolor = p["bg"]
        self.page.theme_mode = ft.ThemeMode.DARK if self.is_dark_mode else ft.ThemeMode.LIGHT
        
        self.main_card.bgcolor = p["card"]
        self.file_card.bgcolor = p["bg"]
        self.settings_box.bgcolor = p["subtle_bg"]
        
        self.gpu_container.bgcolor = p["card"]
        self.gpu_container.border = ft.border.all(1, p["border"])
        
        self.title_text.color = p["text"]
        self.title_text.weight = ft.FontWeight.W_400 if self.is_dark_mode else ft.FontWeight.W_300
        
        self.theme_icon.icon = ft.Icons.WB_SUNNY_OUTLINED if self.is_dark_mode else ft.Icons.NIGHTLIGHT_ROUND
        self.theme_icon.icon_color = p["text"]
        
        self.path_text.color = p["text"] if self.selected_file else p["text_muted"]
        
        for dd in [self.dd_model, self.dd_mode]:
            dd.border_color = p["border"]
            dd.text_style = ft.TextStyle(color=p["text"])
            dd.label_style = ft.TextStyle(color=ACCENT_COLOR)

        self.result_area.bgcolor = p["bg"]
        self.result_area.text_style = ft.TextStyle(color=p["text"])
        self.page.update()

    def toggle_theme(self, e):
        self.is_dark_mode = not self.is_dark_mode
        self._apply_theme()

    def on_file_picked(self, e: ft.FilePickerResultEvent):
        if e.files:
            self.selected_file = e.files[0].path
            self.path_text.value = e.files[0].name
            self.status_text.value = "Ready."
            self.status_text.color = LIGHT_PALETTE["text_muted"]
            self.result_area.value = ""
            self.current_segments = []
            self.btn_save.disabled = True
            self._apply_theme() 

    def run_transcription(self, e):
        if not self.selected_file:
            self.status_text.value = "Please select a file first."
            self.status_text.color = STOP_COLOR
            self.page.update()
            return

        self.stop_event.clear()
        self.processing = True
        self.btn_start.disabled = True
        self.btn_stop.disabled = False
        self.btn_save.disabled = True
        self.progress_bar.visible = True
        self.progress_label.visible = True
        self.current_segments = []
        self.result_area.value = ""
        
        threading.Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        try:
            model_size = self.dd_model.value
            task_type = self.dd_mode.value
            device = "cuda" if self.switch_gpu.value else "cpu"

            self.progress_label.value = f"Loading {model_size} model..."
            self.progress_bar.value = None 
            self.status_text.value = "Downloading model if needed..."
            self.page.update()

            model_path = download_model(model_size)
            model = WhisperModel(model_path, device=device, compute_type="int8")

            self.progress_label.value = "Detecting language..."
            self.page.update()
            
            segments, info = model.transcribe(
                self.selected_file, 
                beam_size=5, 
                task=task_type
            )
            
            lang_name = COMMON_LANGUAGES.get(info.language, info.language.upper())
            self.status_text.value = f"Detected: {lang_name} ({int(info.language_probability * 100)}%)"
            self.status_text.color = ACCENT_COLOR
            self.progress_bar.value = 0
            self.page.update()

            text_buffer = ""
            for segment in segments:
                if self.stop_event.is_set():
                    break
                
                self.current_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                
                text_buffer += segment.text
                self.result_area.value = text_buffer
                
                if info.duration > 0:
                    progress = min(segment.end / info.duration, 1.0)
                    self.progress_bar.value = progress
                    self.progress_label.value = f"Processing... {int(progress * 100)}%"
                
                self.page.update()

            if self.stop_event.is_set():
                self.status_text.value = "Stopped by user."
                self.status_text.color = STOP_COLOR
                self.progress_label.value = "Stopped"
            else:
                self.status_text.value = "Done!"
                self.status_text.color = SUCCESS_COLOR
                self.progress_bar.value = 1.0
                self.progress_label.value = "100%"
                self.btn_save.disabled = False

        except Exception as e:
            err = str(e)
            self.status_text.value = "Error: GPU not found" if "CUDA" in err else f"Error: {err}"
            self.status_text.color = STOP_COLOR
            self.progress_bar.visible = False

        finally:
            self.processing = False
            self.btn_start.disabled = False
            self.btn_stop.disabled = True
            self.page.update()

    def stop_transcription(self, e):
        if self.processing:
            self.stop_event.set()
            self.status_text.value = "Stopping..."
            self.page.update()

    def save_result(self, e: ft.FilePickerResultEvent):
        if not e.path or not self.current_segments:
            return
            
        try:
            ext = e.path.split('.')[-1].lower()
            
            with open(e.path, "w", encoding="utf-8") as f:
                if ext == "json":
                    json.dump(self.current_segments, f, indent=4)
                elif ext == "srt":
                    for i, seg in enumerate(self.current_segments, 1):
                        start = self._fmt_time(seg['start'])
                        end = self._fmt_time(seg['end'])
                        f.write(f"{i}\n{start} --> {end}\n{seg['text']}\n\n")
                else:
                    f.write(self.result_area.value)
                    
            self.status_text.value = f"Saved to {e.name}"
            self.status_text.color = ACCENT_COLOR
            self.page.update()
            
        except Exception as ex:
            self.status_text.value = f"Save failed: {ex}"
            self.status_text.color = STOP_COLOR
            self.page.update()

    def _fmt_time(self, seconds):
        td = datetime.timedelta(seconds=float(seconds))
        # Hack to get comma for milliseconds
        s = str(td)[:-3] 
        if '.' in s:
            return s.replace('.', ',')
        return f"{s},000"

def main(page: ft.Page):
    page.window.icon = "icon.ico"
    app = ScribeApp(page)

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
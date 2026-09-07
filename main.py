import tkinter as tk
import json
import ctypes
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from PIL import Image, ImageTk
import pystray


MAX_PACKS = 500
APP_VERSION = "26.9.0.6"
PROJECT_URL = "https://github.com/YuuLuoLuo/Apex-Pack-Counter"
LATEST_RELEASE_API = "https://api.github.com/repos/YuuLuoLuo/Apex-Pack-Counter/releases/latest"
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
ICON_DIR = RESOURCE_DIR / "assets" / "icon"
DATA_FILE = APP_DIR / "pack_counter_data.json"


def mix_color(start, end, progress):
	start_rgb = tuple(int(start[index:index + 2], 16) for index in (1, 3, 5))
	end_rgb = tuple(int(end[index:index + 2], 16) for index in (1, 3, 5))
	channels = tuple(round(start_rgb[index] + (end_rgb[index] - start_rgb[index]) * progress) for index in range(3))
	return "#%02x%02x%02x" % channels


def normalize_hex_color(value):
	if not isinstance(value, str):
		return None
	value = value.strip().lstrip("#")
	if len(value) != 6:
		return None
	try:
		int(value, 16)
	except ValueError:
		return None
	return "#" + value.lower()


def contrast_text_color(color):
	rgb = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
	luminance = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000
	return "#1f2937" if luminance >= 155 else "#ffffff"


def version_tuple(version):
	try:
		return tuple(int(part) for part in version.lstrip("vV").split("."))
	except ValueError:
		return ()


class SquareButton(tk.Canvas):
	def __init__(self, master, text, command, width=180, height=60, font=("Microsoft YaHei UI", 22)):
		super().__init__(master, width=width, height=height, bd=0, highlightthickness=0, relief="flat")
		self.button_text = text
		self.command = command
		self.button_width = width
		self.button_height = height
		self.font = font
		self.normal_bg = master.cget("bg")
		self.normal_fg = "#1f2937"
		self.base_bg = self.normal_bg
		self.base_fg = self.normal_fg
		self.active = False
		self.active_line = "#e11d48"
		self.emphasis = False
		self.glow = False
		self.line_progress = 1.0
		self.hover_bg = self.normal_bg
		self.hover_fg = self.normal_fg
		self.selection_outline = None
		self.bind("<Button-1>", lambda _event: self.command())
		self.bind("<Enter>", lambda _event: self._set_hover(True))
		self.bind("<Leave>", lambda _event: self._set_hover(False))
		self._draw()

	def _draw(self):
		self.delete("all")
		if self.glow:
			for inset, color in ((2, "#fb7185"), (4, "#fda4af"), (6, "#fecdd3")):
				self.create_rectangle(inset, inset, self.button_width - inset, self.button_height - inset, outline=color, width=2)
		self.create_rectangle(7 if self.glow else 0, 7 if self.glow else 0, self.button_width - (7 if self.glow else 0), self.button_height - (7 if self.glow else 0), fill=self.normal_bg, outline="")
		if self.selection_outline:
			self.create_rectangle(1, 1, self.button_width - 1, self.button_height - 1, outline=self.selection_outline, width=2)
		self.create_text(self.button_width / 2, self.button_height / 2, text=self.button_text, fill=self.normal_fg, font=self.font, anchor="center", justify="center")
		if self.active:
			line_width = (self.button_width - 16) * self.line_progress
			line_start = (self.button_width - line_width) / 2
			self.create_line(line_start, self.button_height - 3, line_start + line_width, self.button_height - 3, fill=self.active_line, width=6 if self.emphasis else 4)

	def _set_hover(self, hovered):
		self.normal_bg = self.hover_bg if hovered else self.base_bg
		self.normal_fg = self.hover_fg if hovered else self.base_fg
		self.glow = hovered
		self._draw()

	def set_style(self, background, foreground, hover_background, hover_foreground, active=False, active_line="#e11d48"):
		self.base_bg = background
		self.base_fg = foreground
		self.hover_bg = hover_background
		self.hover_fg = hover_foreground
		self.active = active
		self.active_line = active_line
		self.glow = False
		self.line_progress = 1.0
		self.normal_bg = background
		self.normal_fg = foreground
		self.configure(bg=background)
		self._draw()

	def emphasize(self, enabled=True):
		self.emphasis = enabled
		self.glow = enabled
		self._draw()

	def set_selection(self, selected, color):
		self.selection_outline = color if selected else None
		self._draw()

	def animate_line(self, progress):
		self.line_progress = progress
		self.glow = progress < 1.0
		self._draw()

	def animate_fade(self, progress, start_background, start_foreground):
		self.normal_bg = mix_color(start_background, self.base_bg, progress)
		self.normal_fg = mix_color(start_foreground, self.base_fg, progress)
		self._draw()


class WindowButton(tk.Canvas):
	def __init__(self, master, base_icon, inside_icon, command):
		super().__init__(master, width=28, height=28, bd=0, highlightthickness=0, relief="flat", bg=master.cget("bg"))
		self.base_image = ImageTk.PhotoImage(Image.open(base_icon).convert("RGBA").resize((28, 28), Image.Resampling.LANCZOS))
		inside = Image.open(inside_icon).convert("RGBA")
		alpha_bounds = inside.getchannel("A").getbbox()
		if alpha_bounds:
			inside = inside.crop(alpha_bounds)
		inside.thumbnail((16, 16), Image.Resampling.LANCZOS)
		inside_canvas = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
		inside_canvas.paste(inside, ((16 - inside.width) // 2, (16 - inside.height) // 2), inside)
		self.inside_image = ImageTk.PhotoImage(inside_canvas)
		self.command = command
		self.hovered = False
		self.bind("<Button-1>", lambda _event: self.command())
		self.bind("<Enter>", lambda _event: self._set_hover(True))
		self.bind("<Leave>", lambda _event: self._set_hover(False))
		self._draw()

	def _set_hover(self, hovered):
		self.hovered = hovered
		self._draw()

	def _draw(self):
		self.delete("all")
		self.create_image(14, 14, image=self.base_image)
		if self.hovered:
			self.create_image(14, 14, image=self.inside_image)

	def apply_background(self, background):
		self.configure(bg=background)


def icon_path(name):
	return ICON_DIR / name


def enable_high_dpi():
	"""让 Windows 按显示器原生 DPI 绘制 Tk 界面，避免文字被系统放大后模糊。"""
	if hasattr(ctypes, "windll"):
		try:
			ctypes.windll.shcore.SetProcessDpiAwareness(2)
		except (AttributeError, OSError):
			try:
				ctypes.windll.user32.SetProcessDPIAware()
			except (AttributeError, OSError):
				pass


class PackCounterApp:
	def __init__(self, root):
		self.root = root
		if not hasattr(ctypes, "windll"):
			self.root.overrideredirect(True)
		self.root.title("APEX 组合包保底计数器")
		self.window_icon = tk.PhotoImage(file=ICON_DIR / "apex-legends-icon.png")
		self.root.iconphoto(True, self.window_icon)
		try:
			self.root.iconbitmap(default=ICON_DIR / "apex-legends-icon.ico")
		except tk.TclError:
			pass
		self.root.minsize(1000, 760)
		self.packs, self.heirlooms, saved_theme, saved_geometry, saved_button_theme, saved_custom_button_color = self._load_data()
		self.dark_mode = saved_theme == "dark"
		self.button_theme = saved_button_theme
		self.custom_button_color = saved_custom_button_color
		self.theme_override = None
		self.current_page = "counter"
		self.drag_start = None
		self.tray_icon = None
		self.tray_thread = None
		self.saved_geometry = saved_geometry
		self.root.geometry(saved_geometry or "1200x900")
		if not saved_geometry:
			self.root.update_idletasks()
			window_x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
			window_y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
			self.root.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+{window_x}+{window_y}")

		self.colors = {
			"light": {
				"background": "#f7f8fa", "surface": "#ffffff", "text": "#1f2937",
				"muted": "#6b7280", "border": "#e5e7eb", "nav_border": "#d5dbe2", "nav_fill": "#e1e5ea", "accent": "#e11d48",
				"button": "#fff1f2", "hover": "#fecdd3", "hover_text": "#9f1239", "entry": "#ffffff",
			},
			"dark": {
				"background": "#17191d", "surface": "#22262d", "text": "#f3f4f6",
				"muted": "#a3aab7", "border": "#383e49", "nav_border": "#8f3b4b", "nav_fill": "#51232d", "accent": "#fb7185",
				"button": "#3f2028", "hover": "#7f1d2d", "hover_text": "#ffffff", "entry": "#2b3038",
			},
		}
		self._build_ui()
		self._apply_theme()
		self._update_display()
		self._set_taskbar_window_style()
		self.root.after(100, self._set_taskbar_window_style)
		self.root.protocol("WM_DELETE_WINDOW", self._on_close)
		self.root.bind("<Map>", self._restore_borderless, add="+")
		self.root.after(250, self._restore_borderless_window)
		self.root.after(750, self._restore_borderless_window)
		self._bind_window_drag()
		self._start_fade_in()
		self._start_tray_icon()

	def _start_fade_in(self):
		self.fade_alpha = 0.0
		try:
			self.root.attributes("-alpha", self.fade_alpha)
		except tk.TclError:
			return
		self.root.after(16, self._fade_in_step)

	def _fade_in_step(self):
		self.fade_alpha = min(1.0, self.fade_alpha + 0.08)
		try:
			self.root.attributes("-alpha", self.fade_alpha)
		except tk.TclError:
			return
		if self.fade_alpha < 1.0:
			self.root.after(16, self._fade_in_step)

	def _load_data(self):
		try:
			with DATA_FILE.open("r", encoding="utf-8") as data_file:
				data = json.load(data_file)
				packs = int(data.get("packs", 0))
				heirlooms = int(data.get("heirlooms", 0))
				theme = data.get("theme", "light")
				geometry = data.get("geometry", "")
				button_theme = data.get("button_theme", "red")
				custom_button_color = normalize_hex_color(data.get("custom_button_color", "#fff1f2")) or "#fff1f2"
		except (OSError, ValueError, TypeError, json.JSONDecodeError):
			packs, heirlooms, theme, geometry, button_theme, custom_button_color = 0, 0, "light", "", "red", "#fff1f2"
		if theme not in ("light", "dark"):
			theme = "light"
		if button_theme not in ("red", "blue", "green", "custom"):
			button_theme = "red"
		return max(0, min(MAX_PACKS, packs)), max(0, heirlooms), theme, geometry if isinstance(geometry, str) else "", button_theme, custom_button_color

	def _save_packs(self):
		try:
			with DATA_FILE.open("w", encoding="utf-8") as data_file:
				json.dump({"packs": self.packs, "heirlooms": self.heirlooms, "theme": "dark" if self.dark_mode else "light", "geometry": self.root.geometry(), "button_theme": self.button_theme, "custom_button_color": self.custom_button_color}, data_file)
		except OSError:
			pass

	def _on_close(self):
		self._exit_application()

	def _exit_application(self):
		self._save_packs()
		if self.tray_icon is not None:
			self.tray_icon.stop()
		self.tray_icon = None
		self.root.destroy()

	def _hide_to_tray(self):
		self._start_tray_icon()
		self.root.withdraw()

	def _show_window(self):
		self.root.deiconify()
		self.root.after(50, self._restore_borderless_window)
		self.root.lift()
		self.root.focus_force()

	def _start_tray_icon(self):
		if self.tray_icon is not None:
			return
		tray_image = Image.open(ICON_DIR / "apex-legends-icon.png").convert("RGBA")
		menu = pystray.Menu(
			pystray.MenuItem("切换到窗口", lambda _icon, _item: self.root.after(0, self._show_window), default=True),
			pystray.MenuItem("退出", lambda _icon, _item: self.root.after(0, self._exit_application)),
		)
		self.tray_icon = pystray.Icon("APEXPackCounter", tray_image, "APEX 组合包保底计数器", menu)
		self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
		self.tray_thread.start()

	def _show_tray_prompt(self):
		if getattr(self, "tray_prompt", None) is not None:
			return
		colors = self.theme
		prompt = tk.Toplevel(self.root)
		self.tray_prompt = prompt
		prompt.overrideredirect(True)
		prompt.transient(self.root)
		prompt.attributes("-topmost", True)
		prompt.grab_set()
		prompt.resizable(False, False)
		prompt.configure(bg=colors["text"])
		prompt_content = tk.Frame(prompt, bg=colors["background"], bd=0, highlightthickness=0)
		prompt_content.pack(padx=2, pady=2)
		message = "程序将最小化到系统托盘并继续运行"
		message_label = tk.Label(prompt_content, text=message, bg=colors["background"], fg=colors["text"], font=("Microsoft YaHei UI", 14, "bold"), anchor="center", justify="center")
		message_label.pack(padx=28, pady=(24, 18))
		buttons = tk.Frame(prompt_content, bg=colors["background"])
		buttons.pack(pady=(0, 24))
		def confirm():
			prompt.grab_release()
			prompt.destroy()
			self.tray_prompt = None
			self._hide_to_tray()
		confirm_button = SquareButton(buttons, "确认", confirm, width=150, height=48, font=("Microsoft YaHei UI", 16))
		prompt_button_colors = self.button_colors
		confirm_button.set_style(prompt_button_colors["background"], prompt_button_colors["text"], prompt_button_colors["hover"], prompt_button_colors["hover_text"])
		confirm_button.pack(side="left", padx=6)
		prompt.protocol("WM_DELETE_WINDOW", confirm)

		def center_prompt():
			if not prompt.winfo_exists():
				return
			self.root.update_idletasks()
			prompt.update_idletasks()
			root_x = self.root.winfo_rootx()
			root_y = self.root.winfo_rooty()
			prompt_x = root_x + (self.root.winfo_width() - prompt.winfo_width()) // 2
			prompt_y = root_y + (self.root.winfo_height() - prompt.winfo_height()) // 2
			prompt.geometry(f"{prompt.winfo_width()}x{prompt.winfo_height()}+{prompt_x}+{prompt_y}")
			prompt.lift()
			prompt.focus_force()

		for delay in (30, 120, 300, 900):
			self.root.after(delay, center_prompt)

	def _set_taskbar_window_style(self):
		if not hasattr(ctypes, "windll"):
			return
		try:
			self.root.update_idletasks()
			hwnd = self.root.winfo_id()
			user32 = ctypes.windll.user32
			kernel32 = ctypes.windll.kernel32
			try:
				app_id = ctypes.c_wchar_p("YuLuo.APEXPackCounter")
				kernel32.SetCurrentProcessExplicitAppUserModelID(app_id)
			except AttributeError:
				pass
			icon_path_value = str(ICON_DIR / "apex-legends-icon.ico")
			LR_LOADFROMFILE = 0x00000010
			LR_DEFAULTSIZE = 0x00000040
			IMAGE_ICON = 1
			load_image = user32.LoadImageW
			load_image.restype = ctypes.c_void_p
			icon_handle = load_image(None, icon_path_value, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
			if icon_handle:
				WM_SETICON = 0x0080
				ICON_SMALL = 0
				ICON_BIG = 1
				user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, icon_handle)
				user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, icon_handle)
				self.taskbar_icon_handle = icon_handle
			get_window_long = user32.GetWindowLongPtrW
			set_window_long = user32.SetWindowLongPtrW
			get_window_long.restype = ctypes.c_longlong
			set_window_long.restype = ctypes.c_longlong
			GWL_EXSTYLE = -20
			GWL_STYLE = -16
			WS_CAPTION = 0x00C00000
			WS_THICKFRAME = 0x00040000
			WS_EX_APPWINDOW = 0x00040000
			WS_EX_TOOLWINDOW = 0x00000080
			ex_style = get_window_long(hwnd, GWL_EXSTYLE)
			set_window_long(hwnd, GWL_EXSTYLE, (ex_style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW)
			window_style = get_window_long(hwnd, GWL_STYLE)
			set_window_long(hwnd, GWL_STYLE, window_style & ~(WS_CAPTION | WS_THICKFRAME))
			SWP_NOSIZE = 0x0001
			SWP_NOMOVE = 0x0002
			SWP_NOZORDER = 0x0004
			SWP_NOACTIVATE = 0x0010
			SWP_FRAMECHANGED = 0x0020
			user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
		except (AttributeError, OSError, tk.TclError):
			pass

	def _bind_window_drag(self):
		self.root.bind_all("<ButtonPress-1>", self._start_window_drag, add="+")
		self.root.bind_all("<B1-Motion>", self._drag_window, add="+")
		self.root.bind_all("<ButtonRelease-1>", self._end_window_drag, add="+")

	def _is_interactive_widget(self, widget):
		while widget is not None:
			if isinstance(widget, (SquareButton, WindowButton, tk.Entry)):
				return True
			widget = widget.master
		return False

	def _start_window_drag(self, event):
		if self._is_interactive_widget(event.widget):
			self.drag_start = None
			return
		self.drag_start = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

	def _drag_window(self, event):
		if self.drag_start is None:
			return
		start_x, start_y, window_x, window_y = self.drag_start
		self.root.geometry(f"+{window_x + event.x_root - start_x}+{window_y + event.y_root - start_y}")

	def _end_window_drag(self, _event):
		self.drag_start = None

	def _minimize_window(self):
		self._show_tray_prompt()

	def _restore_borderless(self, _event=None):
		if self.root.state() != "iconic":
			self.root.after(50, self._restore_borderless_window)

	def _restore_borderless_window(self):
		if hasattr(ctypes, "windll"):
			self.root.overrideredirect(True)
		self._set_taskbar_window_style()

	def _toggle_maximize(self):
		if self.root.state() == "zoomed":
			self.root.state("normal")
			self.root.geometry(self.saved_geometry)
		else:
			self.saved_geometry = self.root.geometry()
			self.root.state("zoomed")
			self.root.after(50, self._restore_borderless_window)

	@property
	def theme(self):
		if self.theme_override is not None:
			return self.theme_override
		return self.colors["dark" if self.dark_mode else "light"]

	@property
	def button_colors(self):
		return self._button_colors_for(self.button_theme)

	def _button_colors_for(self, theme_name):
		presets = {
			"red": ("#fff1f2", "#1f2937", "#fecdd3", "#9f1239", "#e11d48", "#3f2028", "#ffffff", "#7f1d2d", "#ffffff", "#fb7185"),
			"blue": ("#eff6ff", "#1f2937", "#bfdbfe", "#1d4ed8", "#2563eb", "#1e3a5f", "#ffffff", "#1d4ed8", "#ffffff", "#60a5fa"),
			"green": ("#f0fdf4", "#1f2937", "#bbf7d0", "#166534", "#16a34a", "#1f4d35", "#ffffff", "#166534", "#ffffff", "#4ade80"),
		}
		if theme_name == "custom":
			base = self.custom_button_color
			if self.dark_mode:
				background = mix_color(base, "#111827", 0.58)
				hover = mix_color(base, "#374151", 0.38)
				accent = mix_color(base, "#ffffff", 0.15)
			else:
				background = base
				hover = mix_color(base, "#ffffff", 0.25)
				accent = mix_color(base, "#111827", 0.25)
			text = contrast_text_color(background)
			hover_text = contrast_text_color(hover)
		else:
			light_background, light_text, light_hover, light_hover_text, light_accent, dark_background, dark_text, dark_hover, dark_hover_text, dark_accent = presets[theme_name]
			background, text, hover, hover_text, accent = (dark_background, dark_text, dark_hover, dark_hover_text, dark_accent) if self.dark_mode else (light_background, light_text, light_hover, light_hover_text, light_accent)
		return {
			"background": background,
			"hover": hover,
			"text": text,
			"hover_text": hover_text,
			"accent": accent,
		}

	@property
	def danger_button_colors(self):
		colors = self.theme
		return {
			"background": colors["accent"],
			"text": "#ffffff",
			"hover": colors["hover"],
			"hover_text": colors["hover_text"],
		}

	def _build_ui(self):
		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(1, weight=1)
		self.title_bar = tk.Frame(self.root, height=48)
		self.title_bar.grid(row=0, column=0, sticky="ew")
		self.title_bar.grid_propagate(False)
		self.title_bar.columnconfigure(0, weight=1)
		self.window_title = tk.Label(self.title_bar, text="APEX 组合包保底计数器", font=("Microsoft YaHei UI", 15, "bold"), anchor="w")
		self.window_title.grid(row=0, column=0, sticky="w", padx=18, pady=(8, 0))
		window_buttons = tk.Frame(self.title_bar, bd=0, highlightthickness=0)
		self.window_buttons = window_buttons
		window_buttons.grid(row=0, column=1, sticky="e", padx=18, pady=(8, 0))
		self.close_button = WindowButton(window_buttons, icon_path("close.ico"), icon_path("close_inside.ico"), self._on_close)
		self.close_button.grid(row=0, column=2, padx=4)
		self.maximize_button = WindowButton(window_buttons, icon_path("maximize.ico"), icon_path("maximize_inside.ico"), self._toggle_maximize)
		self.maximize_button.grid(row=0, column=1, padx=4)
		self.minimize_button = WindowButton(window_buttons, icon_path("minimize.ico"), icon_path("minimize_inside.ico"), self._minimize_window)
		self.minimize_button.grid(row=0, column=0, padx=4)
		self.main = tk.Frame(self.root)
		self.main.grid(row=1, column=0, sticky="nsew", padx=34, pady=28)
		self.main.columnconfigure(1, weight=1)
		self.main.rowconfigure(1, weight=1)

		self.left_controls = self._create_controls(self.main, 0, "减少", -1)
		self.right_controls = self._create_controls(self.main, 2, "增加", 1)

		card = tk.Frame(self.main, bd=0, highlightthickness=1)
		self.card = card
		card.grid(row=1, column=1, sticky="nsew", padx=24)
		card.columnconfigure(0, weight=1)
		card.rowconfigure(0, weight=1)
		content = tk.Frame(card)
		self.content = content
		content.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
		content.columnconfigure(0, weight=1)
		content.rowconfigure(0, weight=1)
		content.rowconfigure(2, weight=1)
		self.status_label = tk.Label(content, text="当前进度", font=("Microsoft YaHei UI", 22), anchor="center")
		self.status_label.grid(row=1, column=0, sticky="ew", pady=(0, 18))
		progress_group = tk.Frame(content)
		self.progress_group = progress_group
		progress_group.grid(row=1, column=0, sticky="ew")
		progress_group.columnconfigure(0, weight=1)
		progress_group.rowconfigure(0, weight=1)
		progress_group.rowconfigure(3, weight=1)
		self.counter_label = tk.Label(progress_group, font=("Microsoft YaHei UI", 30, "bold"))
		self.counter_label.grid(row=1, column=0, pady=(0, 2))
		self.progress = tk.Canvas(progress_group, height=26, bd=0, highlightthickness=0)
		self.progress.grid(row=2, column=0, sticky="ew", padx=34, pady=(2, 0))
		self.progress.bind("<Configure>", lambda _event: self._draw_progress(self.display_percent))
		self.display_percent = 0.0
		self.progress_job = None

		footer = tk.Frame(self.main)
		footer.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(22, 0))
		footer.columnconfigure(1, weight=1)
		self.input_label = tk.Label(footer, text="已抽包数", font=("Microsoft YaHei UI", 22))
		self.input_label.grid(row=0, column=0, padx=(0, 12))
		self.entry_var = tk.StringVar(value="0")
		self.entry = tk.Entry(footer, textvariable=self.entry_var, justify="center", font=("Microsoft YaHei UI", 22), relief="flat", bd=0)
		self.entry.grid(row=0, column=1, sticky="ew", ipady=8)
		self.entry.bind("<Return>", lambda _event: self._set_from_entry())
		self.entry.bind("<FocusOut>", lambda _event: self._set_from_entry())
		self.apply_button = SquareButton(footer, "应用", self._set_from_entry, width=112, height=58, font=("Microsoft YaHei UI", 22))
		self.apply_button.grid(row=0, column=2, padx=(10, 0))
		self.reset_button = SquareButton(footer, "出传家宝，重置计数", self._record_heirloom, width=350, height=62, font=("Microsoft YaHei UI", 22))
		self.reset_button.grid(row=1, column=0, columnspan=3, pady=(18, 0))
		self.input_label.grid_remove()
		self.entry.grid_remove()
		self.apply_button.grid_remove()

		self.navigation = tk.Frame(self.main, width=730, height=74, bd=0, highlightthickness=1, padx=4, pady=3)
		self.navigation.grid_propagate(False)
		navigation = self.navigation
		navigation.grid(row=3, column=0, columnspan=3, pady=(22, 0))
		self.counter_nav = SquareButton(navigation, "组合包计数", lambda: self._show_page("counter"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.counter_nav.grid(row=0, column=0)
		self.heirloom_nav = SquareButton(navigation, "传家宝记录", lambda: self._show_page("heirloom"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.heirloom_nav.grid(row=0, column=1)
		self.settings_nav = SquareButton(navigation, "设置", lambda: self._show_page("settings"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.settings_nav.grid(row=0, column=2)
		self.about_nav = SquareButton(navigation, "关于", lambda: self._show_page("about"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.about_nav.grid(row=0, column=3)

		self.heirloom_page = tk.Frame(self.root)
		self.heirloom_page.grid(row=1, column=0, sticky="nsew", padx=34, pady=28)
		self.heirloom_page.columnconfigure(0, weight=1)
		self.heirloom_page.rowconfigure(0, weight=1)
		self.heirloom_page.rowconfigure(3, weight=1)
		self.heirloom_title_label = tk.Label(self.heirloom_page, text="传家宝数量", font=("Microsoft YaHei UI", 30, "bold"))
		self.heirloom_title_label.grid(row=1, column=0, pady=(20, 0))
		self.heirloom_count_label = tk.Label(self.heirloom_page, font=("Microsoft YaHei UI", 30, "bold"))
		self.heirloom_count_label.grid(row=2, column=0, sticky="nsew")
		self.heirloom_navigation = tk.Frame(self.heirloom_page, width=730, height=74, bd=0, highlightthickness=1, padx=4, pady=3)
		self.heirloom_navigation.grid_propagate(False)
		heirloom_navigation = self.heirloom_navigation
		heirloom_navigation.grid(row=4, column=0, pady=(22, 0))
		self.heirloom_counter_nav = SquareButton(heirloom_navigation, "组合包计数", lambda: self._show_page("counter"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.heirloom_counter_nav.grid(row=0, column=0)
		self.heirloom_page_nav = SquareButton(heirloom_navigation, "传家宝记录", lambda: self._show_page("heirloom"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.heirloom_page_nav.grid(row=0, column=1)
		self.heirloom_settings_nav = SquareButton(heirloom_navigation, "设置", lambda: self._show_page("settings"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.heirloom_settings_nav.grid(row=0, column=2)
		self.heirloom_about_nav = SquareButton(heirloom_navigation, "关于", lambda: self._show_page("about"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.heirloom_about_nav.grid(row=0, column=3)
		self.heirloom_page.grid_remove()

		self.settings_page = tk.Frame(self.root)
		self.settings_page.grid(row=1, column=0, sticky="nsew", padx=34, pady=28)
		self.settings_page.columnconfigure(0, weight=1)
		self.settings_page.rowconfigure(1, weight=1)
		self.settings_page.rowconfigure(4, weight=0)
		self.settings_title = tk.Label(self.settings_page, text="设置", font=("Microsoft YaHei UI", 30, "bold"))
		self.settings_title.grid(row=0, column=0, pady=(20, 28))
		self.settings_body = tk.Frame(self.settings_page)
		self.settings_body.grid(row=1, column=0, sticky="nsew")
		self.settings_body.columnconfigure(0, weight=1)
		self.settings_body.rowconfigure(0, weight=1)
		self.settings_body.rowconfigure(4, weight=1)
		self.theme_title = tk.Label(self.settings_body, text="背景主题", font=("Microsoft YaHei UI", 22, "bold"))
		self.theme_title.grid(row=1, column=0, pady=(0, 8))
		self.theme_choices = tk.Frame(self.settings_body)
		self.theme_choices.grid(row=2, column=0)
		self.light_theme_button = SquareButton(self.theme_choices, "白色", lambda: self._set_theme("light"), width=220, height=62, font=("Microsoft YaHei UI", 20))
		self.light_theme_button.grid(row=0, column=0, padx=8)
		self.dark_theme_button = SquareButton(self.theme_choices, "黑色", lambda: self._set_theme("dark"), width=220, height=62, font=("Microsoft YaHei UI", 20))
		self.dark_theme_button.grid(row=0, column=1, padx=8)
		self.button_theme_title = tk.Label(self.settings_body, text="按键主题", font=("Microsoft YaHei UI", 22, "bold"))
		self.button_theme_title.grid(row=3, column=0, pady=(24, 8))
		self.button_theme_choices = tk.Frame(self.settings_body)
		self.button_theme_choices.grid(row=4, column=0)
		self.red_button_theme = SquareButton(self.button_theme_choices, "红色", lambda: self._set_button_theme("red"), width=170, height=54, font=("Microsoft YaHei UI", 18))
		self.red_button_theme.grid(row=0, column=0, padx=5)
		self.green_button_theme = SquareButton(self.button_theme_choices, "绿色", lambda: self._set_button_theme("green"), width=170, height=54, font=("Microsoft YaHei UI", 18))
		self.green_button_theme.grid(row=0, column=1, padx=5)
		self.blue_button_theme = SquareButton(self.button_theme_choices, "蓝色", lambda: self._set_button_theme("blue"), width=170, height=54, font=("Microsoft YaHei UI", 18))
		self.blue_button_theme.grid(row=0, column=2, padx=5)
		self.custom_button_theme = SquareButton(self.button_theme_choices, "自定义", lambda: self._set_button_theme("custom"), width=170, height=54, font=("Microsoft YaHei UI", 18))
		self.custom_button_theme.grid(row=0, column=3, padx=5)
		self.custom_color_label = tk.Label(self.settings_body, text="自定义色号（6位十六进制）", font=("Microsoft YaHei UI", 16))
		self.custom_color_label.grid(row=5, column=0, pady=(10, 0))
		self.custom_color_var = tk.StringVar(value=self.custom_button_color)
		self.custom_color_entry = tk.Entry(self.settings_body, textvariable=self.custom_color_var, justify="center", font=("Microsoft YaHei UI", 18), relief="flat", bd=0, width=12)
		self.custom_color_entry.grid(row=6, column=0, pady=(6, 0))
		self.custom_color_entry.bind("<Return>", lambda _event: self._apply_custom_button_color())
		self.custom_color_button = SquareButton(self.settings_body, "应用自定义颜色", self._apply_custom_button_color, width=220, height=48, font=("Microsoft YaHei UI", 16))
		self.custom_color_button.grid(row=7, column=0, pady=(8, 0))
		self.custom_color_warning = tk.Label(self.settings_body, text="提示：自定义颜色不保证文本可读", font=("Microsoft YaHei UI", 14))
		self.custom_color_warning.grid(row=8, column=0, pady=(6, 0))
		self.settings_content = tk.Frame(self.settings_body)
		self.settings_content.grid(row=9, column=0, pady=(18, 0))
		self.settings_hint = tk.Label(self.settings_content, text="已抽包数和传家宝记录", font=("Microsoft YaHei UI", 22, "bold"))
		self.settings_hint.grid(row=0, column=0, pady=(0, 12))
		self.settings_form = tk.Frame(self.settings_content)
		self.settings_form.grid(row=1, column=0)
		self.settings_pack_label = tk.Label(self.settings_form, text="已抽包数", font=("Microsoft YaHei UI", 20))
		self.settings_pack_label.grid(row=0, column=0, padx=8)
		self.settings_entry_var = tk.StringVar(value="0")
		self.settings_entry = tk.Entry(self.settings_form, textvariable=self.settings_entry_var, justify="center", font=("Microsoft YaHei UI", 20), relief="flat", bd=0, width=10)
		self.settings_entry.grid(row=0, column=1, ipady=6, padx=8)
		self.settings_apply_button = SquareButton(self.settings_form, "应用", self._set_from_settings, width=110, height=54, font=("Microsoft YaHei UI", 20))
		self.settings_apply_button.grid(row=0, column=2, padx=8)
		self.settings_undo_button = SquareButton(self.settings_form, "传家宝误操作 -1", self._undo_heirloom, width=250, height=54, font=("Microsoft YaHei UI", 20))
		self.settings_undo_button.grid(row=1, column=0, columnspan=3, pady=(18, 0))
		self.settings_navigation = tk.Frame(self.settings_page, width=730, height=74, bd=0, highlightthickness=1, padx=4, pady=3)
		self.settings_navigation.grid_propagate(False)
		self.settings_navigation.grid(row=4, column=0, sticky="s", pady=(12, 0))
		self.settings_counter_nav = SquareButton(self.settings_navigation, "组合包计数", lambda: self._show_page("counter"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.settings_counter_nav.grid(row=0, column=0)
		self.settings_heirloom_nav = SquareButton(self.settings_navigation, "传家宝记录", lambda: self._show_page("heirloom"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.settings_heirloom_nav.grid(row=0, column=1)
		self.settings_page_nav = SquareButton(self.settings_navigation, "设置", lambda: self._show_page("settings"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.settings_page_nav.grid(row=0, column=2)
		self.settings_about_nav = SquareButton(self.settings_navigation, "关于", lambda: self._show_page("about"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.settings_about_nav.grid(row=0, column=3)
		self.settings_page.grid_remove()

		self.about_page = tk.Frame(self.root)
		self.about_page.grid(row=1, column=0, sticky="nsew", padx=34, pady=28)
		self.about_page.columnconfigure(0, weight=1)
		self.about_page.rowconfigure(0, weight=1)
		self.about_page.rowconfigure(2, weight=1)
		self.about_content = tk.Frame(self.about_page)
		self.about_content.grid(row=1, column=0)
		self.about_title = tk.Label(self.about_content, text="关于", font=("Microsoft YaHei UI", 30, "bold"))
		self.about_title.grid(row=0, column=0, columnspan=2, pady=(0, 24))
		self.about_creator_label = tk.Label(self.about_content, text="创作者：羽洛洛", font=("Microsoft YaHei UI", 20), anchor="w")
		self.about_creator_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)
		self.about_current_version_label = tk.Label(self.about_content, text=f"当前版本：{APP_VERSION}", font=("Microsoft YaHei UI", 20), anchor="w")
		self.about_current_version_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
		self.about_latest_version_label = tk.Label(self.about_content, text="最新版本：检查中...", font=("Microsoft YaHei UI", 20), anchor="w")
		self.about_latest_version_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=4)
		self.about_update_label = tk.Label(self.about_content, text="", font=("Microsoft YaHei UI", 18), anchor="w")
		self.about_update_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 18))
		self.about_project_button = SquareButton(self.about_content, "打开项目网址", lambda: webbrowser.open(PROJECT_URL), width=240, height=54, font=("Microsoft YaHei UI", 18))
		self.about_project_button.grid(row=5, column=0, columnspan=2, pady=(8, 0))
		self.about_navigation = tk.Frame(self.about_page, width=730, height=74, bd=0, highlightthickness=1, padx=4, pady=3)
		self.about_navigation.grid_propagate(False)
		self.about_navigation.grid(row=3, column=0, sticky="s", pady=(12, 0))
		self.about_counter_nav = SquareButton(self.about_navigation, "组合包计数", lambda: self._show_page("counter"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.about_counter_nav.grid(row=0, column=0)
		self.about_heirloom_nav = SquareButton(self.about_navigation, "传家宝记录", lambda: self._show_page("heirloom"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.about_heirloom_nav.grid(row=0, column=1)
		self.about_settings_nav = SquareButton(self.about_navigation, "设置", lambda: self._show_page("settings"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.about_settings_nav.grid(row=0, column=2)
		self.about_page_nav = SquareButton(self.about_navigation, "关于", lambda: self._show_page("about"), width=180, height=66, font=("Microsoft YaHei UI", 22))
		self.about_page_nav.grid(row=0, column=3)
		self.about_page.grid_remove()
		self._check_latest_version()
		self._update_custom_color_visibility()

	def _record_heirloom(self):
		self.heirlooms += 1
		self.packs = 0
		self._save_packs()
		self._update_display()

	def _undo_heirloom(self):
		self.heirlooms = max(0, self.heirlooms - 1)
		self._save_packs()
		self.heirloom_count_label.configure(text=str(self.heirlooms))

	def _set_from_settings(self):
		try:
			value = int(self.settings_entry_var.get().strip())
		except ValueError:
			value = self.packs
		self.packs = max(0, min(MAX_PACKS, value))
		self.settings_entry_var.set(str(self.packs))
		self._save_packs()
		self._update_display()

	def _set_button_theme(self, theme_name):
		self.button_theme = theme_name
		self._save_packs()
		self._apply_theme()

	def _update_custom_color_visibility(self):
		custom_widgets = (self.custom_color_label, self.custom_color_entry, self.custom_color_button, self.custom_color_warning)
		if self.button_theme == "custom":
			for widget in custom_widgets:
				widget.grid()
		else:
			for widget in custom_widgets:
				widget.grid_remove()

	def _apply_custom_button_color(self):
		color = normalize_hex_color(self.custom_color_var.get())
		if color is None:
			self.custom_color_var.set(self.custom_button_color)
			return
		self.custom_button_color = color
		self.button_theme = "custom"
		self.custom_color_var.set(color)
		self._save_packs()
		self._apply_theme()

	def _check_latest_version(self):
		def fetch_latest():
			try:
				request = urllib.request.Request(LATEST_RELEASE_API, headers={"User-Agent": "APEX-Pack-Counter"})
				with urllib.request.urlopen(request, timeout=6) as response:
					latest_data = json.loads(response.read().decode("utf-8"))
				latest_version = latest_data.get("tag_name", "").strip()
				if not latest_version:
					raise ValueError("GitHub release tag is empty")
			except (OSError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError):
				self.root.after(0, lambda: self._set_latest_version_result(None))
				return
			self.root.after(0, lambda: self._set_latest_version_result(latest_version))

		threading.Thread(target=fetch_latest, daemon=True).start()

	def _set_latest_version_result(self, latest_version):
		if latest_version is None:
			self.about_latest_version_label.configure(text="最新版本：获取失败")
			self.about_update_label.configure(text="")
			return
		latest_version = latest_version.lstrip("vV")
		self.about_latest_version_label.configure(text=f"最新版本：{latest_version}")
		if version_tuple(latest_version) and version_tuple(latest_version) > version_tuple(APP_VERSION):
			self.about_update_label.configure(text="　　　　　有新版本")
		else:
			self.about_update_label.configure(text="")

	def _set_theme(self, theme_name):
		if theme_name == ("dark" if self.dark_mode else "light"):
			return
		self._toggle_theme(theme_name)

	def _show_page(self, page):
		previous_page = self.current_page
		if previous_page == page:
			return
		self.current_page = page
		if page == "heirloom":
			self.main.grid_remove()
			self.settings_page.grid_remove()
			self.about_page.grid_remove()
			self.heirloom_page.grid()
			self.heirloom_count_label.configure(text=str(self.heirlooms))
		elif page == "settings":
			self.main.grid_remove()
			self.heirloom_page.grid_remove()
			self.about_page.grid_remove()
			self.settings_page.grid()
			self.settings_entry_var.set(str(self.packs))
		elif page == "about":
			self.main.grid_remove()
			self.heirloom_page.grid_remove()
			self.settings_page.grid_remove()
			self.about_page.grid()
		else:
			self.heirloom_page.grid_remove()
			self.settings_page.grid_remove()
			self.about_page.grid_remove()
			self.main.grid()
			if previous_page == "heirloom":
				self.display_percent = 0.0
				self._animate_progress(self.packs / MAX_PACKS)
		self._update_navigation(page, reset_active=True)
		self._animate_page_content(page)
		self._animate_page_highlight()

	def _animate_page_content(self, page):
		page_root = {"counter": self.main, "heirloom": self.heirloom_page, "settings": self.settings_page, "about": self.about_page}[page]
		labels = []
		buttons = []

		def collect_widgets(widget):
			for child in widget.winfo_children():
				if isinstance(child, tk.Label):
					labels.append(child)
				elif isinstance(child, SquareButton):
					buttons.append(child)
				collect_widgets(child)

		collect_widgets(page_root)
		page_background = self.theme["background"]
		for label in labels:
			label.configure(fg=page_background)

		step = 0

		def animate():
			nonlocal step
			step += 1
			progress = min(1.0, step / 12)
			for label in labels:
				label.configure(fg=mix_color(page_background, self.theme["text"], progress))
			for button in buttons:
				button.animate_fade(progress, page_background, page_background)
			if step < 12:
				self.root.after(18, animate)
			else:
				self._apply_theme()

		animate()

	def _update_navigation(self, page, reset_active=False):
		colors = self.theme
		button_colors = self.button_colors
		for button, active in (
			(self.counter_nav, page == "counter"), (self.heirloom_nav, page == "heirloom"), (self.settings_nav, page == "settings"), (self.about_nav, page == "about"),
			(self.heirloom_counter_nav, page == "counter"), (self.heirloom_page_nav, page == "heirloom"), (self.heirloom_settings_nav, page == "settings"), (self.heirloom_about_nav, page == "about"),
			(self.settings_counter_nav, page == "counter"), (self.settings_heirloom_nav, page == "heirloom"), (self.settings_page_nav, page == "settings"), (self.settings_about_nav, page == "about"),
			(self.about_counter_nav, page == "counter"), (self.about_heirloom_nav, page == "heirloom"), (self.about_settings_nav, page == "settings"), (self.about_page_nav, page == "about"),
		):
			line_progress = button.line_progress if active and not reset_active else 0.0 if active else 1.0
			inactive_background = mix_color(button_colors["background"], colors["nav_fill"], 0.35)
			button.set_style(button_colors["background"] if active else inactive_background, button_colors["text"], button_colors["hover"], button_colors["hover_text"], active, button_colors["accent"])
			button.animate_line(line_progress)

	def _animate_page_highlight(self):
		buttons = {
			"counter": (self.counter_nav, self.heirloom_nav, self.settings_nav),
			"heirloom": (self.heirloom_counter_nav, self.heirloom_page_nav, self.heirloom_settings_nav),
			"settings": (self.settings_counter_nav, self.settings_heirloom_nav, self.settings_page_nav),
			"about": (self.about_counter_nav, self.about_heirloom_nav, self.about_settings_nav, self.about_page_nav),
		}[self.current_page]
		active_index = {"counter": 0, "heirloom": 1, "settings": 2, "about": 3}[self.current_page]
		self._animate_button_line(buttons[active_index])

	def _animate_button_line(self, active_button):
		active_button.emphasize(True)
		step = 0

		def animate():
			nonlocal step
			step += 1
			active_button.animate_line(min(1.0, step / 10))
			if step < 10:
				self.root.after(18, animate)
			else:
				active_button.emphasize(False)
		animate()

	def _create_controls(self, parent, column, label, direction):
		frame = tk.Frame(parent)
		frame.grid(row=1, column=column, sticky="ns")
		frame.rowconfigure(1, weight=1)
		heading = tk.Label(frame, text=label, font=("Microsoft YaHei UI", 22, "bold"))
		heading.grid(row=0, column=0, pady=(5, 12))
		buttons = tk.Frame(frame)
		buttons.grid(row=1, column=0)
		for row, amount in enumerate((1, 5, 10, 100)):
			button = SquareButton(buttons, f"{'+' if direction > 0 else '-'}{amount} 包", lambda value=direction * amount: self._change(value), width=190, height=58, font=("Microsoft YaHei UI", 22))
			button.grid(row=row, column=0, pady=4)
		return frame

	def _change(self, amount):
		self.packs = max(0, min(MAX_PACKS, self.packs + amount))
		self._save_packs()
		self._update_display()

	def _set_from_entry(self):
		try:
			value = int(self.entry_var.get().strip())
		except ValueError:
			value = self.packs
		self.packs = max(0, min(MAX_PACKS, value))
		self._save_packs()
		self._update_display()

	def _update_display(self):
		percent = self.packs / MAX_PACKS
		self.counter_label.configure(text=f"{self.packs} / {MAX_PACKS}")
		self.entry_var.set(str(self.packs))
		self._animate_progress(percent)

	def _animate_progress(self, target):
		if self.progress_job is not None:
			self.root.after_cancel(self.progress_job)
		self.progress_job = None
		start = self.display_percent
		self._draw_progress(start)
		steps = 12
		step = 0

		def advance():
			nonlocal step
			step += 1
			amount = step / steps
			self.display_percent = start + (target - start) * amount
			self._draw_progress(self.display_percent)
			if step < steps:
				self.progress_job = self.root.after(16, advance)
			else:
				self.progress_job = None
		self.progress_job = self.root.after(16, advance)

	def _draw_progress(self, percent):
		self.progress.delete("all")
		width = max(self.progress.winfo_width(), 100)
		height = max(self.progress.winfo_height(), 28)
		self.progress.create_rectangle(0, 0, width, height, fill=self.theme["border"], outline="")
		if percent > 0:
			red, green = (239, 68, 68), (34, 197, 94)
			channels = tuple(round(red[i] + (green[i] - red[i]) * percent) for i in range(3))
			color = "#%02x%02x%02x" % channels
			self.progress.create_rectangle(0, 0, width * percent, height, fill=color, outline="")
		outline = "#000000" if self.dark_mode else "#ffffff"
		text_color = "#ffffff" if self.dark_mode else "#000000"
		text = f"{percent:.1%}"
		center_x, center_y = width / 2, height / 2
		for offset_x, offset_y in ((-1, 0), (1, 0), (0, -1), (0, 1)):
			self.progress.create_text(center_x + offset_x, center_y + offset_y, text=text, fill=outline, font=("Microsoft YaHei UI", 12, "bold"))
		self.progress.create_text(center_x, center_y, text=text, fill=text_color, font=("Microsoft YaHei UI", 12, "bold"), anchor="center")

	def _toggle_theme(self, theme_name):
		if getattr(self, "theme_job", None) is not None:
			self.root.after_cancel(self.theme_job)
		self.theme_job = None
		start_theme = dict(self.theme)
		self.dark_mode = theme_name == "dark"
		end_theme = dict(self.theme)
		self.theme_override = start_theme
		active_theme_button = self.dark_theme_button if self.dark_mode else self.light_theme_button
		active_theme_button.line_progress = 0.0
		step = 0

		def animate_theme():
			nonlocal step
			step += 1
			progress = min(1.0, step / 8)
			self.theme_override = {
				name: mix_color(start_theme[name], end_theme[name], progress)
				for name in start_theme
			}
			self._apply_theme()
			if step < 8:
				self.theme_job = self.root.after(18, animate_theme)
			else:
				self.theme_override = None
				self.theme_job = None
				self._apply_theme()
				self._save_packs()

		animate_theme()
		self._animate_button_line(active_theme_button)

	def _apply_theme(self):
		colors = self.theme
		self.root.configure(bg=colors["background"])
		for widget in (self.title_bar, self.main, self.left_controls, self.right_controls, self.heirloom_page, self.settings_page, self.settings_body, self.about_page, self.about_content):
			widget.configure(bg=colors["background"])
		self.window_title.configure(bg=colors["background"], fg=colors["text"])
		self.window_buttons.configure(bg=colors["background"])
		for button in (self.close_button, self.maximize_button, self.minimize_button):
			button.apply_background(colors["background"])
		for widget in self.main.winfo_children():
			if isinstance(widget, tk.Frame):
				widget.configure(bg=colors["background"])
				for child in widget.winfo_children():
					if isinstance(child, tk.Label):
						child.configure(bg=colors["background"], fg=colors["text"])
		self.card.configure(bg=colors["surface"], highlightbackground=colors["border"])
		self.content.configure(bg=colors["surface"])
		self.progress_group.configure(bg=colors["surface"])
		for widget in (self.status_label, self.counter_label):
			widget.configure(bg=colors["surface"], fg=colors["text"])
		self.entry.configure(bg=colors["entry"], fg=colors["text"], insertbackground=colors["text"], highlightthickness=1, highlightbackground=colors["border"], highlightcolor=colors["accent"])
		button_colors = self.button_colors
		for button in (self.apply_button, self.settings_apply_button, self.custom_color_button, self.about_project_button):
			button.set_style(button_colors["background"], button_colors["text"], button_colors["hover"], button_colors["hover_text"])
		for button in (self.reset_button, self.settings_undo_button):
			danger_colors = self.danger_button_colors
			button.set_style(danger_colors["background"], danger_colors["text"], danger_colors["hover"], danger_colors["hover_text"])
		for button, selected in ((self.light_theme_button, not self.dark_mode), (self.dark_theme_button, self.dark_mode)):
			line_progress = button.line_progress
			button.set_style(button_colors["background"], button_colors["text"], button_colors["hover"], button_colors["hover_text"], selected, button_colors["accent"])
			button.animate_line(line_progress if selected else 1.0)
			button.set_selection(False, button_colors["accent"])
		for button, selected in (
			(self.red_button_theme, self.button_theme == "red"),
			(self.blue_button_theme, self.button_theme == "blue"),
			(self.green_button_theme, self.button_theme == "green"),
			(self.custom_button_theme, self.button_theme == "custom"),
		):
			theme_name = "custom" if button is self.custom_button_theme else "red" if button is self.red_button_theme else "green" if button is self.green_button_theme else "blue"
			preview_colors = self._button_colors_for(theme_name)
			button.set_style(preview_colors["background"], preview_colors["text"], preview_colors["hover"], preview_colors["hover_text"], selected, preview_colors["accent"])
			button.set_selection(False, preview_colors["accent"])
		self._update_custom_color_visibility()
		for frame in (self.left_controls, self.right_controls):
			for child in frame.winfo_children():
				if isinstance(child, tk.Label):
					child.configure(bg=colors["background"], fg=colors["text"])
				elif isinstance(child, tk.Frame):
					child.configure(bg=colors["background"])
					for button in child.winfo_children():
						button.set_style(button_colors["background"], button_colors["text"], button_colors["hover"], button_colors["hover_text"])
		self.input_label.configure(bg=colors["background"], fg=colors["text"])
		for widget in (self.settings_title, self.theme_title, self.button_theme_title, self.custom_color_label, self.custom_color_warning, self.settings_hint, self.settings_pack_label):
			widget.configure(bg=colors["background"], fg=colors["text"])
		for widget in (self.about_title, self.about_creator_label, self.about_current_version_label, self.about_latest_version_label, self.about_update_label):
			widget.configure(bg=colors["background"], fg=colors["text"])
		for widget in (self.theme_choices, self.button_theme_choices, self.settings_content, self.settings_form):
			widget.configure(bg=colors["background"])
		self.settings_entry.configure(bg=colors["entry"], fg=colors["text"], insertbackground=colors["text"], highlightthickness=1, highlightbackground=colors["border"], highlightcolor=colors["accent"])
		self.custom_color_entry.configure(bg=colors["entry"], fg=colors["text"], insertbackground=colors["text"], highlightthickness=1, highlightbackground=colors["border"], highlightcolor=button_colors["accent"])
		self.progress.configure(bg=colors["surface"])
		navigation_fill = mix_color(colors["background"], button_colors["background"], 0.35)
		for navigation in (self.navigation, self.heirloom_navigation, self.settings_navigation, self.about_navigation):
			navigation.configure(bg=navigation_fill, highlightbackground=button_colors["accent"])
		for widget in (self.heirloom_title_label, self.heirloom_count_label):
			widget.configure(bg=colors["background"], fg=colors["text"])
		self._update_navigation(self.current_page)


if __name__ == "__main__":
	enable_high_dpi()
	root = tk.Tk()
	root.tk.call("tk", "scaling", 1.0)
	PackCounterApp(root)
	root.mainloop()

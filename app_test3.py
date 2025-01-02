import os
import base64
import json
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk  # 引入ttk模块，用于进度条和Treeview
from PIL import Image, ImageTk, ImageEnhance
import cv2
import shutil
import tempfile
import atexit
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
import requests  # 用于检测网络连接
from datetime import datetime  # 用于获取本地时间
import csv  # 增加了导出日志为csv文件的功能
from dotenv import load_dotenv  # 从.env文件中读取阿里云信息
import logging  # 日志

# 加载环境变量
load_dotenv()

# 初始化logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def set_text(self, new_text):
        self.text = new_text

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)  # 延迟0.5秒显示提示

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def showtip(self, event=None):
        if self.tipwindow or not self.text:
            return
        # 获取控件的位置
        x, y, cx, cy = self.widget.bbox("insert") if self.widget.winfo_class() == 'Entry' else (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # 去除窗口装饰
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("Helvetica", "10", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

# 定义 FaceRecognitionApp 类
class FaceRecognitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("人脸识别系统")
        self.root.geometry("1200x800")  # 增加宽度以适应列表和控制面板
        self.root.configure(bg="#2c3e50")  # 深蓝灰色背景

        # 创建临时文件夹及其子文件夹
        self.temp_dir = tempfile.mkdtemp(prefix="face_recognition_")
        self.uploaded_dir = os.path.join(self.temp_dir, "uploaded")
        self.camera_dir = os.path.join(self.temp_dir, "camera")
        os.makedirs(self.uploaded_dir, exist_ok=True)
        os.makedirs(self.camera_dir, exist_ok=True)

        # 注册程序退出时清理临时文件夹
        atexit.register(self.cleanup_temp_dir)

        # 阿里云 Access Key
        self.access_key_id = os.getenv('access_key_id')  # 从环境变量中读取 AccessKeyId
        self.access_key_secret = os.getenv('access_key_secret')  # 从环境变量中读取 AccessKeySecret

        # 检查必要的环境变量是否存在
        if not self.access_key_id or not self.access_key_secret:
            messagebox.showerror("环境变量错误", "未设置必要的环境变量：access_key_id 或 access_key_secret。")
            logger.error("未设置必要的环境变量：access_key_id 或 access_key_secret。")
            raise EnvironmentError("缺少必要的环境变量。")

        # 阿里云人脸识别 API URL（根据地域不同，可能需要调整）
        self.url = os.getenv('facebody_domain', "facebody.cn-shanghai.aliyuncs.com")

        # 人脸库ID，替换为你自己的库ID
        self.face_lib_id = os.getenv('face_lib_id', 'default')  # 从环境变量中读取 FaceLibId

        # 创建阿里云客户端
        try:
            self.client = AcsClient(self.access_key_id, self.access_key_secret, 'cn-shanghai')
            logger.info("阿里云客户端已初始化。")
        except Exception as e:
            messagebox.showerror("阿里云客户端错误", f"初始化阿里云客户端失败: {e}")
            logger.error(f"初始化阿里云客户端失败: {e}")
            raise e

        # 全局变量，用于存储用户选择的图片路径
        self.selected_image_paths = []

        # 用于存储图像引用，防止被垃圾回收
        self.images = []

        # 用于存储文件名与路径的映射
        self.filename_to_path = {}

        # 设置按钮样式
        self.style = ttk.Style()
        self.style.theme_use('clam')  # 使用 'clam' 主题，适合自定义样式
        self.style.configure("TButton",
                             font=("Helvetica", 12, "bold"),
                             padding=10,
                             relief="flat",
                             background="#1abc9c",  # 青绿色
                             foreground="white")
        self.style.map("TButton",
                       background=[('active', '#16a085')])  # 鼠标悬停时颜色变化

        # 创建顶部状态框架
        self.frame_status = tk.Frame(root, bg="#2c3e50")
        self.frame_status.pack(pady=10, padx=20, fill='x')

        # 网络连接状态标签
        self.network_status_label = tk.Label(self.frame_status, text="网络状态: 检测中...",
                                             font=("Helvetica", 12),
                                             bg="#2c3e50",
                                             fg="yellow")
        self.network_status_label.pack(side='left', padx=10)

        # 当地时间标签
        self.time_label = tk.Label(self.frame_status, text="当前时间: --:--:--",
                                   font=("Helvetica", 12),
                                   bg="#2c3e50",
                                   fg="yellow")
        self.time_label.pack(side='right', padx=10)

        # 创建顶部标题
        self.title_label = tk.Label(root, text="人脸识别系统",
                                    font=("Helvetica", 18, "bold"),
                                    bg="#2c3e50",
                                    fg="#ecf0f1")
        self.title_label.pack(pady=20)

        # 创建选择图片按钮框架
        self.frame_buttons = tk.Frame(root, bg="#2c3e50")
        self.frame_buttons.pack(pady=10, padx=20, fill='x')

        self.button_open_images = ttk.Button(self.frame_buttons, text="上传图片", command=self.open_images)
        self.button_open_images.pack(pady=5, fill='x')

        self.button_open_folder = ttk.Button(self.frame_buttons, text="上传文件夹图片", command=self.open_folder)
        self.button_open_folder.pack(pady=5, fill='x')

        self.button_start_camera = ttk.Button(self.frame_buttons, text="启动摄像头", command=self.open_camera_window)
        self.button_start_camera.pack(pady=5, fill='x')

        self.button_help = ttk.Button(self.frame_buttons, text="帮助", command=self.show_help)
        self.button_help.pack(pady=5, fill='x')

        # 添加手动输入路径的功能
        self.frame_manual_path = tk.Frame(root, bg="#2c3e50")
        self.frame_manual_path.pack(pady=10, padx=20, fill='x')

        self.label_manual_path = tk.Label(self.frame_manual_path, text="手动输入文件夹路径:",
                                          font=("Helvetica", 12),
                                          bg="#2c3e50",
                                          fg="#ecf0f1")
        self.label_manual_path.pack(side='left', padx=5)

        self.entry_manual_path = tk.Entry(self.frame_manual_path, width=50, font=("Helvetica", 12))
        self.entry_manual_path.pack(side='left', padx=5, fill='x', expand=True)

        self.button_browse_path = ttk.Button(self.frame_manual_path, text="浏览", command=self.browse_folder)
        self.button_browse_path.pack(side='left', padx=5)

        self.button_upload_manual_path = ttk.Button(self.frame_manual_path, text="上传", command=self.upload_faces_from_path)
        self.button_upload_manual_path.pack(side='left', padx=5)

        # 创建左侧的文件名列表框架
        self.frame_file_list = tk.Frame(root, bg="#2c3e50")
        self.frame_file_list.pack(pady=10, padx=20, fill='y', side='left')

        self.label_uploaded_files = tk.Label(self.frame_file_list, text="已上传文件列表:",
                                             font=("Helvetica", 12, "bold"),
                                             bg="#2c3e50",
                                             fg="#ecf0f1")
        self.label_uploaded_files.pack(pady=5)

        # 创建一个带滚动条的Listbox
        self.scrollbar = tk.Scrollbar(self.frame_file_list, orient=tk.VERTICAL)
        self.listbox_files = tk.Listbox(self.frame_file_list, width=40, height=30, font=("Helvetica", 12),
                                        yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.listbox_files.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.listbox_files.pack(side='left', fill='both', expand=True)

        # 绑定Listbox的选择事件
        self.listbox_files.bind('<<ListboxSelect>>', self.display_selected_image)

        # 创建右侧的图像显示框架
        self.frame_image = tk.Frame(root, bg="#2c3e50", bd=2, relief="groove")
        self.frame_image.pack(pady=20, padx=20, fill='both', expand=True, side='left')

        self.canvas_image = tk.Canvas(self.frame_image, bg="#34495e", cursor="hand2")
        self.canvas_image.pack(pady=10, padx=10, fill='both', expand=True)

        self.original_image = None  # 保存原始图像
        self.display_image = None   # 当前显示的图像
        self.photo_image = None     # ImageTk.PhotoImage 实例
        self.image_on_canvas = None # Canvas 上的图像对象

        # 初始化拖动相关变量
        self.canvas_image.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas_image.bind("<B1-Motion>", self.on_move_press)
        self.drag_data = {"x": 0, "y": 0}

        # 绑定鼠标滚轮事件用于缩放
        self.canvas_image.bind("<MouseWheel>", self.zoom_image)  # Windows
        self.canvas_image.bind("<Button-4>", self.zoom_image)    # Linux scroll up
        self.canvas_image.bind("<Button-5>", self.zoom_image)    # Linux scroll down

        # 绑定右键菜单用于旋转和全屏
        self.canvas_image.bind("<Button-3>", self.show_context_menu)

        # 创建右键菜单
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="顺时针旋转90°", command=lambda: self.rotate_image(90))
        self.context_menu.add_command(label="逆时针旋转90°", command=lambda: self.rotate_image(-90))
        self.context_menu.add_command(label="全屏查看", command=self.fullscreen_view)

        # 创建图像控制按钮框架
        self.frame_image_controls = tk.Frame(root, bg="#2c3e50")
        self.frame_image_controls.pack(pady=10, padx=20, fill='x')

        # 缩放按钮
        self.button_zoom_in = ttk.Button(self.frame_image_controls, text="放大", command=lambda: self.zoom_image_manual(1.1))
        self.button_zoom_in.pack(side='left', padx=5)
        ToolTip(self.button_zoom_in, "点击放大图像")

        self.button_zoom_out = ttk.Button(self.frame_image_controls, text="缩小", command=lambda: self.zoom_image_manual(0.9))
        self.button_zoom_out.pack(side='left', padx=5)
        ToolTip(self.button_zoom_out, "点击缩小图像")

        # 旋转按钮
        self.button_rotate_left = ttk.Button(self.frame_image_controls, text="逆时针旋转90°", command=lambda: self.rotate_image(-90))
        self.button_rotate_left.pack(side='left', padx=5)
        ToolTip(self.button_rotate_left, "逆时针旋转图像90°")

        self.button_rotate_right = ttk.Button(self.frame_image_controls, text="顺时针旋转90°", command=lambda: self.rotate_image(90))
        self.button_rotate_right.pack(side='left', padx=5)
        ToolTip(self.button_rotate_right, "顺时针旋转图像90°")

        # 添加缩放滑块
        self.scale = tk.Scale(self.frame_image_controls, from_=50, to=200, orient=tk.HORIZONTAL, label="缩放比例 (%)", command=self.scale_image)
        self.scale.set(100)  # 初始缩放比例为100%
        self.scale.pack(side='left', padx=10)
        ToolTip(self.scale, "拖动滑块调整图像缩放比例")

        # 添加底部版权信息
        self.footer_label = tk.Label(root, text="face-recognition-system based on Qianwen",
                                     font=("Helvetica", 10),
                                     bg="#2c3e50",
                                     fg="#ecf0f1")
        self.footer_label.pack(pady=10)

        # 启动网络状态和时间更新
        self.check_network()
        self.update_time()

        # 初始化日志列表
        self.logs = []

        # 添加导出日志按钮
        self.button_export_logs = ttk.Button(self.frame_buttons, text="导出使用日志", command=self.export_logs)
        self.button_export_logs.pack(pady=5, fill='x')
        ToolTip(self.button_export_logs, "将使用日志导出为CSV文件")

        # 加载语言资源
        self.languages = self.load_languages()
        self.current_language = 'zh'  # 默认语言为中文
        # 添加语言选择下拉菜单
        self.language_var = tk.StringVar(value='中文')
        self.dropdown_languages = ttk.Combobox(self.frame_buttons, textvariable=self.language_var, state='readonly')
        self.dropdown_languages['values'] = ['中文', 'English']
        self.dropdown_languages.bind('<<ComboboxSelected>>', self.change_language)
        self.dropdown_languages.pack(pady=5, fill='x')
        ToolTip(self.dropdown_languages, "选择界面语言")

        # 设置初始语言
        self.set_language(self.current_language)
        # 创建Scale控件，用于调整缩放比例
        self.scale = tk.Scale(self.frame_image_controls, from_=50, to=200, orient=tk.HORIZONTAL, label="缩放比例 (%)", command=self.scale_image)
        self.scale.set(100)  # 默认缩放为100%
        self.scale.pack()
    def scale_image(self, value):
        """根据Scale控件的值来缩放图像"""
        scale_factor = int(value) / 100  # 从百分比转化为缩放比例
        new_width = int(self.display_image.width * scale_factor)
        new_height = int(self.display_image.height * scale_factor)

        # 缩放图像
        self.display_image = self.display_image.resize((new_width, new_height), Image.LANCZOS)
        self.photo_image = ImageTk.PhotoImage(self.display_image)

        # 更新Canvas上的图像
        self.canvas_image.itemconfig(self.image_on_canvas, image=self.photo_image)
        self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))  # 更新Canvas的滚动区域
    def show_context_menu(self, event):
        # 创建右键菜单
        context_menu = Menu(self.root, tearoff=0)
        context_menu.add_command(label="Option 1", command=self.option1_action)
        context_menu.add_command(label="Option 2", command=self.option2_action)
        context_menu.add_separator()
        context_menu.add_command(label="Exit", command=self.root.quit)

    def option1_action(self):
        print("Option 1 selected")

    def option2_action(self):
        print("Option 2 selected")
    def load_languages(self):
        languages = {}
        try:
            with open('languages.json', 'r', encoding='utf-8') as f:
                languages = json.load(f)
            logger.info("语言资源加载成功。")
        except Exception as e:
            logger.error(f"语言资源加载失败: {e}")
            # 提供默认语言
            languages = {
                "zh": {
                    "network_status": "网络状态: 检测中...",
                    "current_time": "当前时间",
                    "title": "人脸识别系统",
                    "upload_images": "上传图片",
                    "upload_folder_images": "上传文件夹图片",
                    "start_camera": "启动摄像头",
                    "help": "帮助",
                    "manual_path_label": "手动输入文件夹路径:",
                    "browse": "浏览",
                    "upload": "上传",
                    "uploaded_files": "已上传文件列表:",
                    "export_logs": "导出使用日志",
                    "choose_language_tooltip": "选择界面语言",
                    "thank_you": "face-recognition-system based on Qianwen",
                    "upload_progress_title": "上传进度",
                    "uploading_images": "正在上传图片",
                    "upload_complete": "上传完成",
                    "upload_success": "成功上传: {uploaded} 张图片",
                    "upload_failed": "失败上传: {failed} 张图片",
                    "error": "错误",
                    "no_images_selected_error": "未选择任何图片进行上传。",
                    "open_image_error": "无法打开图片 {image}: {error}",
                    "upload_image_error": "上传图片 {image} 失败: {error}",
                    "capture_photo": "拍照",
                    "camera_window_title": "摄像头",
                    "help_text": "这是人脸识别系统的帮助文档。您可以上传图片、文件夹中的图片，启动摄像头拍照进行人脸识别。",
                    "help_window_title": "帮助"
                },
                "en": {
                    "network_status": "Network Status: Checking...",
                    "current_time": "Current Time",
                    "title": "Face Recognition System",
                    "upload_images": "Upload Images",
                    "upload_folder_images": "Upload Folder Images",
                    "start_camera": "Start Camera",
                    "help": "Help",
                    "manual_path_label": "Manually Enter Folder Path:",
                    "browse": "Browse",
                    "upload": "Upload",
                    "uploaded_files": "Uploaded Files List:",
                    "export_logs": "Export Usage Logs",
                    "choose_language_tooltip": "Choose Interface Language",
                    "thank_you": "face-recognition-system based on Qianwen",
                    "upload_progress_title": "Upload Progress",
                    "uploading_images": "Uploading Images",
                    "upload_complete": "Upload Complete",
                    "upload_success": "Successfully uploaded: {uploaded} images",
                    "upload_failed": "Failed to upload: {failed} images",
                    "error": "Error",
                    "no_images_selected_error": "No images selected for upload.",
                    "open_image_error": "Cannot open image {image}: {error}",
                    "upload_image_error": "Failed to upload image {image}: {error}",
                    "capture_photo": "Capture Photo",
                    "camera_window_title": "Camera",
                    "help_text": "This is the help documentation for the Face Recognition System. You can upload images, upload images from a folder, and start the camera to capture photos for face recognition.",
                    "help_window_title": "Help"
                }
            }
        return languages

    def set_language(self, lang_code):
        lang = self.languages.get(lang_code, self.languages['zh'])
        # 更新所有文本
        self.network_status_label.config(text=lang["network_status"])
        self.time_label.config(text=f"{lang['current_time']}: --:--:--")
        self.title_label.config(text=lang["title"])
        self.button_open_images.config(text=lang["upload_images"])
        self.button_open_folder.config(text=lang["upload_folder_images"])
        self.button_start_camera.config(text=lang["start_camera"])
        self.button_help.config(text=lang["help"])
        self.label_manual_path.config(text=lang["manual_path_label"])
        self.button_browse_path.config(text=lang["browse"])
        self.button_upload_manual_path.config(text=lang["upload"])
        self.label_uploaded_files.config(text=lang["uploaded_files"])
        self.button_export_logs.config(text=lang["export_logs"])
          # 绑定右键点击事件
        self.canvas_image.bind("<Button-3>", self.show_context_menu)

        # 更新底部版权信息
        self.footer_label.config(text=lang["thank_you"])

        # 更新其他弹窗中的文本将在相关方法中处理

        logger.info(f"界面语言已切换为: {lang_code}")
    def show_context_menu(self, event):
            # 创建右键菜单
            context_menu = Menu(self.root, tearoff=0)
            context_menu.add_command(label="Option 1", command=self.option1_action)
            context_menu.add_command(label="Option 2", command=self.option2_action)
            context_menu.add_separator()
            context_menu.add_command(label="Exit", command=self.root.quit)

            # 显示右键菜单，位置在鼠标点击的坐标
            context_menu.post(event.x_root, event.y_root)

    def change_language(self, event):
        selected_language = self.language_var.get()
        if selected_language == '中文':
            self.current_language = 'zh'
        elif selected_language == 'English':
            self.current_language = 'en'
        self.set_language(self.current_language)
        logger.info(f"语言切换为: {self.current_language}")

    def add_log(self, operation, result, matched_person=None):
        """
        添加一条日志记录。

        参数:
            operation (str): 操作类型，如“拍照”、“上传图片”等。
            result (str): 操作结果，如“成功”、“失败”。
            matched_person (str, optional): 匹配到的人员名称或ID。如果无匹配则为None。
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "Timestamp": timestamp,
            "Operation": operation,
            "Result": result,
            "Matched_Person": matched_person if matched_person else "无"
        }
        self.logs.append(log_entry)
        logger.info(f"日志记录：{log_entry}")

    def cleanup_temp_dir(self):
        """在程序退出时清理临时文件夹"""
        try:
            shutil.rmtree(self.temp_dir)
            logger.info(f"临时文件夹 {self.temp_dir} 已删除。")
        except Exception as e:
            logger.error(f"无法删除临时文件夹 {self.temp_dir}: {e}")

    def browse_folder(self):
        folder_path = filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder_path:
            self.entry_manual_path.delete(0, tk.END)
            self.entry_manual_path.insert(0, folder_path)
            logger.info(f"手动输入的文件夹路径: {folder_path}")

    def get_headers(self):
        return {
            "Content-Type": "multipart/form-data"
        }

    def compress_image(self, image_path, max_size=(800, 800)):
        img = Image.open(image_path)
        img.thumbnail(max_size)
        compressed_image_path = os.path.join(self.uploaded_dir, "compressed_" + os.path.basename(image_path))
        img.save(compressed_image_path)
        logger.info(f"压缩图片保存为: {compressed_image_path}")
        return compressed_image_path

    def enhance_image(self, image_path):
        img = Image.open(image_path)

        # 亮度增强（如果图像过暗）
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.5)  # 调高亮度

        # 对比度增强
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)  # 增强对比度

        # 锐化
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)  # 锐化增强

        enhanced_image_path = os.path.join(self.uploaded_dir, "enhanced_" + os.path.basename(image_path))
        img.save(enhanced_image_path)
        logger.info(f"增强图片保存为: {enhanced_image_path}")
        return enhanced_image_path

    def upload_faces(self):
        if not self.selected_image_paths:
            messagebox.showerror(self.languages[self.current_language]["error"], self.languages[self.current_language]["no_images_selected_error"])
            logger.error("上传失败：未选择任何图片。")
            self.add_log("上传图片", "失败：未选择任何图片")
            return

        # 创建一个顶层弹窗来显示处理状态
        progress_window = tk.Toplevel(self.root)
        progress_window.title(self.languages[self.current_language]["upload_progress_title"])
        progress_window.geometry("400x200")
        progress_window.configure(bg="#2c3e50")

        progress_label = tk.Label(progress_window, text=self.languages[self.current_language]["uploading_images"],
                                  font=("Helvetica", 12),
                                  bg="#2c3e50",
                                  fg="#ecf0f1")
        progress_label.pack(pady=20)

        progress_bar = ttk.Progressbar(progress_window, length=300, mode='determinate')
        progress_bar.pack(pady=20)

        # 设置进度条最大值为图片数量
        progress_bar["maximum"] = len(self.selected_image_paths)

        uploaded = 0
        failed = 0

        for i, image_path in enumerate(self.selected_image_paths, start=1):
            try:
                # 压缩并增强图片
                compressed_image_path = self.compress_image(image_path)  # 压缩图片
                enhanced_image_path = self.enhance_image(compressed_image_path)  # 增强图片

                # 打开图片并处理
                try:
                    img = Image.open(enhanced_image_path)
                except (IOError, SyntaxError) as e:
                    messagebox.showerror(self.languages[self.current_language]["error"], self.languages[self.current_language]["open_image_error"].format(image=os.path.basename(image_path), error=str(e)))
                    logger.error(f"跳过损坏文件: {image_path}, 错误详情: {e}")
                    self.add_log("上传图片", f"失败：无法打开图片 {image_path}")
                    failed += 1
                    continue  # 跳过损坏的文件

                # 使用 SDK 构建请求
                request = CommonRequest()
                request.set_accept_format('json')
                request.set_domain(self.url)
                request.set_method('POST')
                request.set_version('2019-12-30')
                request.set_action_name('AddFace')
                request.add_query_param('FaceLibId', self.face_lib_id)
                request.add_file_param('file', enhanced_image_path)

                # 发送请求
                response = self.client.do_action_with_exception(request)
                result = json.loads(response)

                if 'FaceRecords' in result:
                    logger.info(f"图片 {image_path} 上传成功！")
                    uploaded += 1
                    self.add_log("上传图片", "成功", os.path.basename(image_path))
                    # 添加到文件列表
                    filename = os.path.basename(image_path)
                    self.listbox_files.insert(tk.END, filename)
                    self.filename_to_path[filename] = image_path
                else:
                    logger.warning(f"图片 {image_path} 上传失败。错误代码：{json.dumps(result)}")
                    failed += 1
                    self.add_log("上传图片", f"失败：{json.dumps(result)}")

                # 更新进度条
                progress_label.config(text=f"{self.languages[self.current_language]['uploading_images']} ({i}/{len(self.selected_image_paths)})")
                progress_bar["value"] = i
                progress_window.update_idletasks()

            except Exception as e:
                messagebox.showerror(self.languages[self.current_language]["error"], self.languages[self.current_language]["upload_image_error"].format(image=os.path.basename(image_path), error=str(e)))
                logger.error(f"上传 {image_path} 时发生错误: {e}")
                self.add_log("上传图片", f"失败：{e}")
                failed += 1

        # 上传完成后关闭进度窗口并显示结果
        progress_window.destroy()
        messagebox.showinfo(self.languages[self.current_language]["upload_complete"], self.languages[self.current_language]["upload_success"].format(uploaded=uploaded) + "\n" + self.languages[self.current_language]["upload_failed"].format(failed=failed))
        logger.info(f"批量上传完成！成功上传: {uploaded} 张图片，失败: {failed} 张图片")

    def upload_faces_from_path(self):
        folder_path = self.entry_manual_path.get().strip()
        if not folder_path:
            messagebox.showerror("错误", "请输入文件夹路径！")
            logger.error("上传文件夹失败：未输入文件夹路径。")
            self.add_log("上传文件夹", "失败：未输入文件夹路径")
            return
        if not os.path.exists(folder_path):
            messagebox.showerror("错误", "输入的路径不存在！")
            logger.error(f"上传文件夹失败：路径不存在 {folder_path}")
            self.add_log("上传文件夹", f"失败：路径不存在 {folder_path}")
            return
        if not os.path.isdir(folder_path):
            messagebox.showerror("错误", "输入的路径不是一个文件夹！")
            logger.error(f"上传文件夹失败：路径不是文件夹 {folder_path}")
            self.add_log("上传文件夹", f"失败：路径不是文件夹 {folder_path}")
            return

        # 遍历文件夹中的所有图片文件
        image_extensions = (".jpg", ".jpeg", ".png")
        image_paths = [
            os.path.join(folder_path, filename) for filename in os.listdir(folder_path)
            if filename.lower().endswith(image_extensions)
        ]

        if not image_paths:
            messagebox.showwarning("无图片", "该文件夹中没有支持的图片文件（.jpg, .jpeg, .png）！")
            logger.warning(f"上传文件夹警告：文件夹 {folder_path} 中没有支持的图片文件。")
            self.add_log("上传文件夹", f"失败：文件夹 {folder_path} 中没有支持的图片文件")
            return

        logger.info(f"上传文件夹路径: {folder_path}, 找到 {len(image_paths)} 张图片")

        # 将图片复制到上传文件夹
        copied_image_paths = []
        for image_path in image_paths:
            try:
                dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                shutil.copy2(image_path, dest_path)
                copied_image_paths.append(dest_path)
                logger.info(f"复制图片 {image_path} 到 {dest_path}")
            except Exception as e:
                logger.error(f"复制图片 {image_path} 时发生错误: {e}")
                print(f"复制图片 {image_path} 时发生错误: {e}")

        if not copied_image_paths:
            messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
            logger.error(f"上传文件夹失败：没有图片被复制到上传文件夹 {self.uploaded_dir}")
            self.add_log("上传文件夹", "失败：没有图片被复制到上传文件夹")
            return

        self.selected_image_paths = copied_image_paths
        logger.info(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")
        self.add_log("上传文件夹", f"成功：复制了 {len(self.selected_image_paths)} 张图片")

        # 触发批量上传
        self.upload_faces()

    def match_face(self, image_path):
        with open(image_path, "rb") as image_file:
            files = {
                'file': ('image.jpg', image_file, 'image/jpeg')
            }

            data = {
                'Action': 'SearchFace',  # 搜索人脸库中是否有匹配
                'Version': '2019-12-30',  # 版本号
                'FaceLibId': self.face_lib_id,  # 人脸库ID
            }

            try:
                # 使用 SDK 构建请求
                request = CommonRequest()
                request.set_accept_format('json')
                request.set_domain(self.url)
                request.set_method('POST')
                request.set_version('2019-12-30')
                request.set_action_name('SearchFace')
                request.add_query_param('FaceLibId', self.face_lib_id)
                request.add_file_param('file', image_path)

                # 发送请求
                response = self.client.do_action_with_exception(request)
                result = json.loads(response)
                logger.info(f"人脸匹配响应: {result}")

                if 'FaceRecords' in result and len(result['FaceRecords']) > 0:
                    matched_person = result['FaceRecords'][0].get('Person', '未知')
                    return True, matched_person  # 匹配成功
                else:
                    return False, None  # 匹配失败
            except Exception as e:
                messagebox.showerror("识别失败", f"识别失败: {e}\n请确保摄像头正常工作并重新尝试。")
                logger.error(f"识别失败：{e}")
                self.add_log("人脸识别", f"失败：{e}")
                return False, None

    def display_selected_image(self, event):
        # 获取选中的文件名
        selection = self.listbox_files.curselection()
        if not selection:
            return
        index = selection[0]
        filename = self.listbox_files.get(index)
        image_path = self.filename_to_path.get(filename)

        if image_path and os.path.exists(image_path):
            try:
                # 打开并保存原始图像
                self.original_image = Image.open(image_path).convert("RGB")
                self.display_image = self.original_image.copy()
                self.photo_image = ImageTk.PhotoImage(self.display_image)

                # 在Canvas上显示图像
                if self.image_on_canvas:
                    self.canvas_image.delete(self.image_on_canvas)
                self.image_on_canvas = self.canvas_image.create_image(0, 0, anchor='nw', image=self.photo_image)

                # 调整Canvas大小以适应图像
                self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))

                # 保持对图像的引用
                self.canvas_image.image = self.photo_image

                logger.info(f"显示图片: {filename}")

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {filename}: {e}")
                logger.error(f"无法打开图片 {filename}: {e}")
                print(f"错误详情: {e}")

    def zoom_image(self, event):
        """使用鼠标滚轮进行缩放"""
        if event.num == 4 or event.delta > 0:
            scale = 1.1
        elif event.num == 5 or event.delta < 0:
            scale = 0.9
        else:
            scale = 1.0
        self.zoom_image_manual(scale)

    def zoom_image_manual(self, scale_factor):
        """通过按钮或鼠标滚轮进行缩放"""
        if self.display_image:
            new_width = int(self.display_image.width * scale_factor)
            new_height = int(self.display_image.height * scale_factor)

            # 限制缩放比例
            if new_width < 50 or new_height < 50:
                messagebox.showwarning("缩放限制", "无法缩放到更小的尺寸。")
                return
            if new_width > 5000 or new_height > 5000:
                messagebox.showwarning("缩放限制", "无法缩放到更大的尺寸。")
                return

            self.display_image = self.display_image.resize((new_width, new_height), Image.LANCZOS)
            self.photo_image = ImageTk.PhotoImage(self.display_image)
            self.canvas_image.itemconfig(self.image_on_canvas, image=self.photo_image)
            self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))
            self.canvas_image.image = self.photo_image  # 保持引用

    def rotate_image(self, angle):
        """旋转图像"""
        if self.display_image:
            self.display_image = self.display_image.rotate(angle, expand=True)
            self.photo_image = ImageTk.PhotoImage(self.display_image)
            self.canvas_image.itemconfig(self.image_on_canvas, image=self.photo_image)
            self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))
            self.canvas_image.image = self.photo_image  # 保持引用

    def on_button_press(self, event):
        """记录鼠标点击位置"""
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_move_press(self, event):
        """计算鼠标移动距离并移动图像"""
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        self.canvas_image.move(self.image_on_canvas, dx, dy)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def fullscreen_view(self):
        """全屏查看图像"""
        if self.display_image:
            top = tk.Toplevel(self.root)
            top.attributes("-fullscreen", True)
            top.configure(bg='black')

            # 创建Canvas
            fullscreen_canvas = tk.Canvas(top, bg='black')
            fullscreen_canvas.pack(fill=tk.BOTH, expand=True)

            # 调整图像尺寸以适应全屏
            screen_width = top.winfo_screenwidth()
            screen_height = top.winfo_screenheight()
            img_ratio = self.display_image.width / self.display_image.height
            screen_ratio = screen_width / screen_height

            if img_ratio > screen_ratio:
                new_width = screen_width
                new_height = int(screen_width / img_ratio)
            else:
                new_height = screen_height
                new_width = int(screen_height * img_ratio)

            resized_image = self.display_image.resize((new_width, new_height), Image.LANCZOS)
            photo_image_fullscreen = ImageTk.PhotoImage(resized_image)

            # 在全屏Canvas上显示图像
            fullscreen_canvas.create_image(screen_width//2, screen_height//2, anchor='center', image=photo_image_fullscreen)
            fullscreen_canvas.image = photo_image_fullscreen  # 保持引用

            # 绑定Esc键退出全屏
            top.bind("<Escape>", lambda e: top.destroy())

    def open_camera_window(self):
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception(self.languages[self.current_language]["error"] + ": 摄像头无法打开。")
            self.camera_window = tk.Toplevel(self.root)
            self.camera_window.title(self.languages[self.current_language]["camera_window_title"])
            self.camera_window.geometry("650x550")
            self.camera_window.configure(bg="#2c3e50")

            # 禁用主窗口
            self.root.attributes("-disabled", True)

            # 处理窗口关闭事件
            self.camera_window.protocol("WM_DELETE_WINDOW", self.close_camera_window)

            # 创建摄像头画面显示标签
            self.camera_label = tk.Label(self.camera_window, bg="#34495e")
            self.camera_label.pack(pady=20, padx=20, fill='both', expand=True)

            # 创建“拍照”按钮
            self.capture_button = ttk.Button(self.camera_window, text=self.languages[self.current_language]["capture_photo"], command=self.capture_photo)
            self.capture_button.pack(pady=10)
            ToolTip(self.capture_button, "点击拍照并进行人脸识别")

            # 启动视频流更新
            self.update_camera_frame()

            self.add_log("启动摄像头", "成功")
            logger.info("摄像头已启动。")

        except Exception as e:
            messagebox.showerror(self.languages[self.current_language]["error"], str(e))
            logger.error(f"启动摄像头失败：{e}")
            self.add_log("启动摄像头", f"失败：{e}")
            self.close_camera_window()
            return

    def update_camera_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # 转换颜色为RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            img = img.resize((600, 400), Image.LANCZOS)
            self.current_frame = img  # 保存当前帧用于拍照

            img_tk = ImageTk.PhotoImage(img)
            self.camera_label.imgtk = img_tk  # 保持引用
            self.camera_label.config(image=img_tk)

        # 每30毫秒更新一次画面
        self.camera_window.after(30, self.update_camera_frame)

    def capture_photo(self):
        if hasattr(self, 'current_frame') and self.current_frame:
            # 生成唯一的文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            captured_image_path = os.path.join(self.camera_dir, f"captured_face_{timestamp}.jpg")
            self.current_frame.save(captured_image_path)
            messagebox.showinfo("拍照成功", f"图片已保存为 {captured_image_path}")
            self.add_log("拍照", "成功", captured_image_path)  # 添加日志记录

            # 进行人脸匹配
            match_result, matched_person = self.match_face(captured_image_path)
            if match_result:
                messagebox.showinfo("结果", f"此人在人脸库中！匹配人员: {matched_person}")
                self.add_log("人脸匹配", "成功", matched_person)
            else:
                messagebox.showinfo("结果", "此人不在库中！")
                self.add_log("人脸匹配", "失败")

            # 提示用户是否继续
            if not messagebox.askyesno("继续", "是否继续上传新图片或继续拍照？"):
                self.close_camera_window()

    def close_camera_window(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
            logger.info("摄像头已释放。")
            self.add_log("关闭摄像头", "成功")
        if hasattr(self, 'camera_window') and self.camera_window.winfo_exists():
            self.camera_window.destroy()
        # 重新启用主窗口
        self.root.attributes("-disabled", False)
        cv2.destroyAllWindows()

    def open_images(self):
        file_paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("Image Files", "*.jpg;*.jpeg;*.png")]
        )
        if file_paths:
            logger.info(f"选择的图片路径: {file_paths}")

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in file_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                    logger.info(f"复制图片 {image_path} 到 {dest_path}")
                except Exception as e:
                    logger.error(f"复制图片 {image_path} 时发生错误: {e}")
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                logger.error("上传失败：没有图片被复制到上传文件夹。")
                self.add_log("上传图片", "失败：没有图片被复制到上传文件夹")
                return

            self.selected_image_paths = copied_image_paths
            logger.info(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")
            self.add_log("上传图片", f"成功：复制了 {len(self.selected_image_paths)} 张图片")

            # 自动显示第一张图片
            if self.selected_image_paths:
                self.listbox_files.selection_clear(0, tk.END)
                self.listbox_files.selection_set(0)
                self.listbox_files.event_generate("<<ListboxSelect>>")

    def open_folder(self):
        folder_path = filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder_path:
            # 遍历文件夹中的所有图片文件
            image_extensions = (".jpg", ".jpeg", ".png")
            image_paths = [
                os.path.join(folder_path, filename) for filename in os.listdir(folder_path)
                if filename.lower().endswith(image_extensions)
            ]

            # 如果文件夹没有图片，弹出提示
            if not image_paths:
                messagebox.showwarning("无图片", "该文件夹中没有支持的图片文件（.jpg, .jpeg, .png）！")
                logger.warning(f"上传文件夹警告：文件夹 {folder_path} 中没有支持的图片文件。")
                self.add_log("上传文件夹", f"失败：文件夹 {folder_path} 中没有支持的图片文件")
                return

            logger.info(f"选择的文件夹: {folder_path}")
            logger.info(f"找到 {len(image_paths)} 张图片")

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in image_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                    logger.info(f"复制图片 {image_path} 到 {dest_path}")
                except Exception as e:
                    logger.error(f"复制图片 {image_path} 时发生错误: {e}")
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                logger.error(f"上传文件夹失败：没有图片被复制到上传文件夹 {self.uploaded_dir}")
                self.add_log("上传文件夹", "失败：没有图片被复制到上传文件夹")
                return

            self.selected_image_paths = copied_image_paths
            logger.info(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")
            self.add_log("上传文件夹", f"成功：复制了 {len(self.selected_image_paths)} 张图片")

            # 自动显示第一张图片
            if self.selected_image_paths:
                self.listbox_files.selection_clear(0, tk.END)
                self.listbox_files.selection_set(0)
                self.listbox_files.event_generate("<<ListboxSelect>>")

    def check_network(self):
        """定期检查网络连接状态"""
        try:
            response = requests.get("https://www.google.com", timeout=5)
            if response.status_code == 200:
                self.network_status_label.config(text="网络状态: 已连接", fg="green")
                logger.info("网络状态: 已连接")
            else:
                self.network_status_label.config(text="网络状态: 未连接", fg="red")
                logger.warning("网络状态: 未连接")
        except requests.RequestException:
            self.network_status_label.config(text="网络状态: 未连接", fg="red")
            logger.warning("网络状态: 未连接")
        # 每5秒检查一次
        self.root.after(5000, self.check_network)

    def update_time(self):
        """定期更新时间显示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=f"当前时间: {current_time}")
        # 每秒更新一次
        self.root.after(1000, self.update_time)

    def export_logs(self):
        if not self.logs:
            messagebox.showinfo("导出日志", "当前没有任何日志记录。")
            logger.info("导出日志失败：当前没有任何日志记录。")
            return

        export_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if export_path:
            try:
                with open(export_path, mode='w', newline='', encoding='utf-8-sig') as csv_file:
                    fieldnames = ["Timestamp", "Operation", "Result", "Matched_Person"]
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

                    writer.writeheader()
                    for log in self.logs:
                        writer.writerow(log)

                messagebox.showinfo("导出成功", f"日志已成功导出到 {export_path}")
                logger.info(f"日志已导出到 {export_path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"导出日志失败: {e}")
                logger.error(f"导出日志失败: {e}")

    def show_help(self):
        help_text = self.languages[self.current_language].get("help_text", "")
        help_window = tk.Toplevel(self.root)
        help_window.title(self.languages[self.current_language]["help_window_title"])
        help_window.geometry("700x600")
        help_window.configure(bg="#2c3e50")

        # 使用ScrolledText显示长文本
        from tkinter.scrolledtext import ScrolledText
        help_textbox = ScrolledText(help_window, wrap=tk.WORD, bg="#2c3e50", fg="#ecf0f1", font=("Helvetica", 12))
        help_textbox.pack(fill='both', expand=True, padx=10, pady=10)
        help_textbox.insert(tk.END, help_text)
        help_textbox.config(state='disabled')  # 只读

    # 以下是集成的图像交互功能方法
    def zoom_image(self, event):
        """使用鼠标滚轮进行缩放"""
        if event.num == 4 or event.delta > 0:
            scale = 1.1
        elif event.num == 5 or event.delta < 0:
            scale = 0.9
        else:
            scale = 1.0
        self.zoom_image_manual(scale)

    def zoom_image_manual(self, scale_factor):
        """通过按钮或鼠标滚轮进行缩放"""
        if self.display_image:
            new_width = int(self.display_image.width * scale_factor)
            new_height = int(self.display_image.height * scale_factor)

            # 限制缩放比例
            if new_width < 50 or new_height < 50:
                messagebox.showwarning("缩放限制", "无法缩放到更小的尺寸。")
                return
            if new_width > 5000 or new_height > 5000:
                messagebox.showwarning("缩放限制", "无法缩放到更大的尺寸。")
                return

            self.display_image = self.display_image.resize((new_width, new_height), Image.LANCZOS)
            self.photo_image = ImageTk.PhotoImage(self.display_image)
            self.canvas_image.itemconfig(self.image_on_canvas, image=self.photo_image)
            self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))
            self.canvas_image.image = self.photo_image  # 保持引用

    def rotate_image(self, angle):
        """旋转图像"""
        if self.display_image:
            self.display_image = self.display_image.rotate(angle, expand=True)
            self.photo_image = ImageTk.PhotoImage(self.display_image)
            self.canvas_image.itemconfig(self.image_on_canvas, image=self.photo_image)
            self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))
            self.canvas_image.image = self.photo_image  # 保持引用

    def on_button_press(self, event):
        """记录鼠标点击位置"""
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_move_press(self, event):
        """计算鼠标移动距离并移动图像"""
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        self.canvas_image.move(self.image_on_canvas, dx, dy)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def fullscreen_view(self):
        """全屏查看图像"""
        if self.display_image:
            top = tk.Toplevel(self.root)
            top.attributes("-fullscreen", True)
            top.configure(bg='black')

            # 创建Canvas
            fullscreen_canvas = tk.Canvas(top, bg='black')
            fullscreen_canvas.pack(fill=tk.BOTH, expand=True)

            # 调整图像尺寸以适应全屏
            screen_width = top.winfo_screenwidth()
            screen_height = top.winfo_screenheight()
            img_ratio = self.display_image.width / self.display_image.height
            screen_ratio = screen_width / screen_height

            if img_ratio > screen_ratio:
                new_width = screen_width
                new_height = int(screen_width / img_ratio)
            else:
                new_height = screen_height
                new_width = int(screen_height * img_ratio)

            resized_image = self.display_image.resize((new_width, new_height), Image.LANCZOS)
            photo_image_fullscreen = ImageTk.PhotoImage(resized_image)

            # 在全屏Canvas上显示图像
            fullscreen_canvas.create_image(screen_width//2, screen_height//2, anchor='center', image=photo_image_fullscreen)
            fullscreen_canvas.image = photo_image_fullscreen  # 保持引用

            # 绑定Esc键退出全屏
            top.bind("<Escape>", lambda e: top.destroy())

    def open_camera_window(self):
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception(self.languages[self.current_language]["error"] + ": 摄像头无法打开。")
            self.camera_window = tk.Toplevel(self.root)
            self.camera_window.title(self.languages[self.current_language]["camera_window_title"])
            self.camera_window.geometry("650x550")
            self.camera_window.configure(bg="#2c3e50")

            # 禁用主窗口
            self.root.attributes("-disabled", True)

            # 处理窗口关闭事件
            self.camera_window.protocol("WM_DELETE_WINDOW", self.close_camera_window)

            # 创建摄像头画面显示标签
            self.camera_label = tk.Label(self.camera_window, bg="#34495e")
            self.camera_label.pack(pady=20, padx=20, fill='both', expand=True)

            # 创建“拍照”按钮
            self.capture_button = ttk.Button(self.camera_window, text=self.languages[self.current_language]["capture_photo"], command=self.capture_photo)
            self.capture_button.pack(pady=10)
            ToolTip(self.capture_button, "点击拍照并进行人脸识别")

            # 启动视频流更新
            self.update_camera_frame()

            self.add_log("启动摄像头", "成功")
            logger.info("摄像头已启动。")

        except Exception as e:
            messagebox.showerror(self.languages[self.current_language]["error"], str(e))
            logger.error(f"启动摄像头失败：{e}")
            self.add_log("启动摄像头", f"失败：{e}")
            self.close_camera_window()
            return

    def update_camera_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # 转换颜色为RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            img = img.resize((600, 400), Image.LANCZOS)
            self.current_frame = img  # 保存当前帧用于拍照

            img_tk = ImageTk.PhotoImage(img)
            self.camera_label.imgtk = img_tk  # 保持引用
            self.camera_label.config(image=img_tk)

        # 每30毫秒更新一次画面
        self.camera_window.after(30, self.update_camera_frame)

    def capture_photo(self):
        if hasattr(self, 'current_frame') and self.current_frame:
            # 生成唯一的文件名
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            captured_image_path = os.path.join(self.camera_dir, f"captured_face_{timestamp}.jpg")
            self.current_frame.save(captured_image_path)
            messagebox.showinfo("拍照成功", f"图片已保存为 {captured_image_path}")
            self.add_log("拍照", "成功", captured_image_path)  # 添加日志记录

            # 进行人脸匹配
            match_result, matched_person = self.match_face(captured_image_path)
            if match_result:
                messagebox.showinfo("结果", f"此人在人脸库中！匹配人员: {matched_person}")
                self.add_log("人脸匹配", "成功", matched_person)
            else:
                messagebox.showinfo("结果", "此人不在库中！")
                self.add_log("人脸匹配", "失败")

            # 提示用户是否继续
            if not messagebox.askyesno("继续", "是否继续上传新图片或继续拍照？"):
                self.close_camera_window()

    def close_camera_window(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
            logger.info("摄像头已释放。")
            self.add_log("关闭摄像头", "成功")
        if hasattr(self, 'camera_window') and self.camera_window.winfo_exists():
            self.camera_window.destroy()
        # 重新启用主窗口
        self.root.attributes("-disabled", False)
        cv2.destroyAllWindows()

    def open_images(self):
        file_paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("Image Files", "*.jpg;*.jpeg;*.png")]
        )
        if file_paths:
            logger.info(f"选择的图片路径: {file_paths}")

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in file_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                    logger.info(f"复制图片 {image_path} 到 {dest_path}")
                except Exception as e:
                    logger.error(f"复制图片 {image_path} 时发生错误: {e}")
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                logger.error("上传失败：没有图片被复制到上传文件夹。")
                self.add_log("上传图片", "失败：没有图片被复制到上传文件夹")
                return

            self.selected_image_paths = copied_image_paths
            logger.info(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")
            self.add_log("上传图片", f"成功：复制了 {len(self.selected_image_paths)} 张图片")

            # 自动显示第一张图片
            if self.selected_image_paths:
                self.listbox_files.selection_clear(0, tk.END)
                self.listbox_files.selection_set(0)
                self.listbox_files.event_generate("<<ListboxSelect>>")

    def open_folder(self):
        folder_path = filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder_path:
            # 遍历文件夹中的所有图片文件
            image_extensions = (".jpg", ".jpeg", ".png")
            image_paths = [
                os.path.join(folder_path, filename) for filename in os.listdir(folder_path)
                if filename.lower().endswith(image_extensions)
            ]

            # 如果文件夹没有图片，弹出提示
            if not image_paths:
                messagebox.showwarning("无图片", "该文件夹中没有支持的图片文件（.jpg, .jpeg, .png）！")
                logger.warning(f"上传文件夹警告：文件夹 {folder_path} 中没有支持的图片文件。")
                self.add_log("上传文件夹", f"失败：文件夹 {folder_path} 中没有支持的图片文件")
                return

            logger.info(f"选择的文件夹: {folder_path}")
            logger.info(f"找到 {len(image_paths)} 张图片")

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in image_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                    logger.info(f"复制图片 {image_path} 到 {dest_path}")
                except Exception as e:
                    logger.error(f"复制图片 {image_path} 时发生错误: {e}")
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                logger.error(f"上传文件夹失败：没有图片被复制到上传文件夹 {self.uploaded_dir}")
                self.add_log("上传文件夹", "失败：没有图片被复制到上传文件夹")
                return

            self.selected_image_paths = copied_image_paths
            logger.info(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")
            self.add_log("上传文件夹", f"成功：复制了 {len(self.selected_image_paths)} 张图片")

            # 自动显示第一张图片
            if self.selected_image_paths:
                self.listbox_files.selection_clear(0, tk.END)
                self.listbox_files.selection_set(0)
                self.listbox_files.event_generate("<<ListboxSelect>>")

    def check_network(self):
        """定期检查网络连接状态"""
        try:
            response = requests.get("https://www.google.com", timeout=5)
            if response.status_code == 200:
                self.network_status_label.config(text="网络状态: 已连接", fg="green")
                logger.info("网络状态: 已连接")
            else:
                self.network_status_label.config(text="网络状态: 未连接", fg="red")
                logger.warning("网络状态: 未连接")
        except requests.RequestException:
            self.network_status_label.config(text="网络状态: 未连接", fg="red")
            logger.warning("网络状态: 未连接")
        # 每5秒检查一次
        self.root.after(5000, self.check_network)

    def update_time(self):
        """定期更新时间显示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=f"当前时间: {current_time}")
        # 每秒更新一次
        self.root.after(1000, self.update_time)

    def export_logs(self):
        if not self.logs:
            messagebox.showinfo("导出日志", "当前没有任何日志记录。")
            logger.info("导出日志失败：当前没有任何日志记录。")
            return

        export_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if export_path:
            try:
                with open(export_path, mode='w', newline='', encoding='utf-8-sig') as csv_file:
                    fieldnames = ["Timestamp", "Operation", "Result", "Matched_Person"]
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

                    writer.writeheader()
                    for log in self.logs:
                        writer.writerow(log)

                messagebox.showinfo("导出成功", f"日志已成功导出到 {export_path}")
                logger.info(f"日志已导出到 {export_path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"导出日志失败: {e}")
                logger.error(f"导出日志失败: {e}")

    def show_help(self):
        help_text = self.languages[self.current_language].get("help_text", "")
        help_window = tk.Toplevel(self.root)
        help_window.title(self.languages[self.current_language]["help_window_title"])
        help_window.geometry("700x600")
        help_window.configure(bg="#2c3e50")

        # 使用ScrolledText显示长文本
        from tkinter.scrolledtext import ScrolledText
        help_textbox = ScrolledText(help_window, wrap=tk.WORD, bg="#2c3e50", fg="#ecf0f1", font=("Helvetica", 12))
        help_textbox.pack(fill='both', expand=True, padx=10, pady=10)
        help_textbox.insert(tk.END, help_text)
        help_textbox.config(state='disabled')  # 只读

    # 以下是集成的图像交互功能方法
    def zoom_image(self, event):
        """使用鼠标滚轮进行缩放"""
        if event.num == 4 or event.delta > 0:
            scale = 1.1
        elif event.num == 5 or event.delta < 0:
            scale = 0.9
        else:
            scale = 1.0
        self.zoom_image_manual(scale)

    def zoom_image_manual(self, scale_factor):
        """通过按钮或鼠标滚轮进行缩放"""
        if self.display_image:
            new_width = int(self.display_image.width * scale_factor)
            new_height = int(self.display_image.height * scale_factor)

            # 限制缩放比例
            if new_width < 50 or new_height < 50:
                messagebox.showwarning("缩放限制", "无法缩放到更小的尺寸。")
                return
            if new_width > 5000 or new_height > 5000:
                messagebox.showwarning("缩放限制", "无法缩放到更大的尺寸。")
                return

            self.display_image = self.display_image.resize((new_width, new_height), Image.LANCZOS)
            self.photo_image = ImageTk.PhotoImage(self.display_image)
            self.canvas_image.itemconfig(self.image_on_canvas, image=self.photo_image)
            self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))
            self.canvas_image.image = self.photo_image  # 保持引用

    def rotate_image(self, angle):
        """旋转图像"""
        if self.display_image:
            self.display_image = self.display_image.rotate(angle, expand=True)
            self.photo_image = ImageTk.PhotoImage(self.display_image)
            self.canvas_image.itemconfig(self.image_on_canvas, image=self.photo_image)
            self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))
            self.canvas_image.image = self.photo_image  # 保持引用

    def on_button_press(self, event):
        """记录鼠标点击位置"""
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_move_press(self, event):
        """计算鼠标移动距离并移动图像"""
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        self.canvas_image.move(self.image_on_canvas, dx, dy)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def fullscreen_view(self):
        """全屏查看图像"""
        if self.display_image:
            top = tk.Toplevel(self.root)
            top.attributes("-fullscreen", True)
            top.configure(bg='black')

            # 创建Canvas
            fullscreen_canvas = tk.Canvas(top, bg='black')
            fullscreen_canvas.pack(fill=tk.BOTH, expand=True)

            # 调整图像尺寸以适应全屏
            screen_width = top.winfo_screenwidth()
            screen_height = top.winfo_screenheight()
            img_ratio = self.display_image.width / self.display_image.height
            screen_ratio = screen_width / screen_height

            if img_ratio > screen_ratio:
                new_width = screen_width
                new_height = int(screen_width / img_ratio)
            else:
                new_height = screen_height
                new_width = int(screen_height * img_ratio)

            resized_image = self.display_image.resize((new_width, new_height), Image.LANCZOS)
            photo_image_fullscreen = ImageTk.PhotoImage(resized_image)

            # 在全屏Canvas上显示图像
            fullscreen_canvas.create_image(screen_width//2, screen_height//2, anchor='center', image=photo_image_fullscreen)
            fullscreen_canvas.image = photo_image_fullscreen  # 保持引用

            # 绑定Esc键退出全屏
            top.bind("<Escape>", lambda e: top.destroy())

# 以下是主程序启动部分
if __name__ == "__main__":
    root = tk.Tk()
    app = FaceRecognitionApp(root)
    root.mainloop()

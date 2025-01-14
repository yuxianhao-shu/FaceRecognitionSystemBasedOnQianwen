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
from PIL import Image, ImageTk
import locale
import numpy as np

# 加载环境变量
load_dotenv()

# 初始化logger
#配置日志基本信息，设置日志级别为INFO
logging.basicConfig(
    level=logging.INFO,
    formatter='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S',

    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(),
        logging.setFormatter(formatter)
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
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def set_text(self, new_text):
        """动态更新提示文本"""
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

    def show_tooltip(self, event=None):
        if self.tipwindow or not self.text:
            return
        # 获取控件的位置
        x, y, cx, cy = self.widget.bbox("insert") if self.widget.winfo_class() == 'Entry' else (0, 0, 0, 0)
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)

        # 去除窗口装饰
        tw.wm_overrideredirect(True)  

        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("Helvetica", "10", "normal"))
        # label组件内部的左右两侧各添加1像素的空白
        label.pack(ipadx=5)

    def hide_tooltip(self,event=None):
        if tw:
            tw.destroy()
            tw = None


# 定义 FaceRecognitionApp 类
class FaceRecognitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("人脸识别系统")
        self.root.geometry("1200x800")  # 增加宽度以适应列表和控制面板
        self.root.configure(bg="#ffffff")  # 深蓝灰色背景

        # 创建临时文件夹
        self.temp_dir = tempfile.mkdtemp(prefix="face_recognition_")

        # 创建子文件夹
        self.uploaded_dir = os.path.join(self.temp_dir, "uploaded")
        self.camera_dir = os.path.join(self.temp_dir, "camera")

        # 创建目录
        os.makedirs(self.uploaded_dir, exist_ok=True)
        os.makedirs(self.camera_dir, exist_ok=True)

        # 定义清理临时文件夹的函数
        def cleanup_temp_folder():
            self.temp_dir.cleanup
            
        try:
            print(f"临时文件夹路径：{self.temp_dir.name}")
        
        finally:
            # 注册程序退出时清理临时文件夹
            atexit.register(cleanup_temp_dir)

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

        # 加载语言资源
        def load_languages(self):
            languages = {}

        # 改变默认语言
        try:
            # 设置默认语言环境为简体中文
            locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
            print('当前语言环境已设置成简体中文')
        except local.Error as e:
            print (f'设置语言环境时出现错误：{e}')

        try:
            # 设置默认语言环境为英语（美国）
            locale.setlocale(locale.LC_ALL,'en_US.UTF-8')
            print('当前语言已设置成英语（美国）')
        except locale.Error as e:
            print(f'设置语言环境时出现错误：{e}')
        
    

        # 创建阿里云客户端
        try:
            client = AcsClient(
                access_key_id = 'your_access_key_id',
                access_key_secret = 'your_access_key_secret',
                region_id = 'cn-shanghai'
            )

            #创建请求
            request = CommonRequest()
            request.set_accept_format('json')
            request.set_domain('ecs.aliyuncs.com')
            request.set_method('POST')
            request.set_protocol_type('https') # https | http
            request.set_version('2014-05-26')
            request.set_action_name('DescribeInstances')

            # 发起请求并获取响应
            response = client.do_action_with_exception(request)
            print(str(response), encoding = 'utf-8')

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

        # 定义自定义颜色
        PRIMARY_COLOR = "#ffffff"        # 主背景色（白色）
        SECONDARY_COLOR = "#DCDCDC"      # 次背景色（浅灰色）
        ACCENT_COLOR = "#1E90FF"         # 按钮和一些高亮色（蓝色）
        ACCENT_COLOR_ACTIVE = "#27408B"  # 前景色（灰蓝色）
        TEXT_COLOR = "#ecf0f1"         

        # 配置全局控件样式
        self.style.configure(
            ".",  # '.' 表示全局
            font=("Microsoft YaHei", 11),
            background=PRIMARY_COLOR
        )

        # 配置 TFrame 样式
        self.style.configure(
            "TFrame",
            background=PRIMARY_COLOR
        )

        # 配置 TLabel 样式
        self.style.configure(
            "TLabel",
            background=PRIMARY_COLOR,
            foreground=TEXT_COLOR
        )

        # 配置 TButton 样式
        self.style.configure(
            "TButton",
            font=("Microsoft YaHei", 11, "bold"),
            padding=10,
            relief="flat",
            background=ACCENT_COLOR,
            foreground="white"
        )
        self.style.map(
            "TButton",
            background=[('active', ACCENT_COLOR_ACTIVE)]
        )

        # 配置 TCombobox 样式
        self.style.configure(
            "TCombobox",
            foreground="black",
            fieldbackground="#ffffff"
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#ffffff")]
        )

        # 创建顶部状态框架
        self.frame_status = tk.Frame(root, bg="#2c3e50")
        self.frame_status.pack(pady=10, padx=20, fill='x')

        # 网络连接状态标签
        self.network_status_label = tk.Label(self.frame_status, text=lang["network_status"],
                                            font=("Helvetica", 12),
                                            bg="#2c3e50",
                                            fg="yellow")
        self.network_status_label.pack(side='left', padx=10)

        # 当地时间标签
        self.time_label = tk.Label(self.frame_status, text=f"{lang['current_time']}: --:--:--",
                                font=("Helvetica", 12),
                                bg="#2c3e50",
                                fg="yellow")
        self.time_label.pack(side='right', padx=10)

        # 创建顶部标题
        self.title_label = ttk.Label(
            root,
            text=lang["title"],
            style="TLabel"
        )
        # 然后单独修改字体：
        self.title_label.configure(font=("Microsoft YaHei", 18, "bold"))
        self.title_label.pack(pady=20)

        # 创建按钮框架
        self.frame_buttons = ttk.Frame(root, style="TFrame")
        self.frame_buttons.pack(pady=10, padx=20, fill='x')

        # 创建内部按钮框架以使用 grid 布局
        self.frame_buttons_inner = tk.Frame(self.frame_buttons, bg="#2c3e50")
        self.frame_buttons_inner.pack(fill='x')

        # 添加上传图片到人脸库按钮
        self.button_upload_to_library = ttk.Button(
            self.frame_buttons_inner,
            text=lang["upload_images"],
            command=self.upload_faces_to_library,
            style="TButton"
        )
        self.button_upload_to_library.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        self.tooltip_upload_to_library = ToolTip(
            self.button_upload_to_library,
            lang.get("upload_images_tooltip", "上传图片到人脸库")
        )

        # 添加比对图片按钮
        self.button_match_faces = ttk.Button(
            self.frame_buttons_inner,
            text=lang["match_faces"],
            command=self.match_faces_from_images,
            style="TButton"
        )
        self.button_match_faces.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.tooltip_match_faces = ToolTip(
            self.button_match_faces,
            lang.get("match_faces_tooltip", "上传图片进行人脸比对")
        )

        # 添加启动摄像头按钮
        self.button_start_camera = ttk.Button(
            self.frame_buttons_inner,
            text=lang["start_camera"],
            command=self.open_camera_window,
            style="TButton"
        )
        self.button_start_camera.grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        self.tooltip_start_camera = ToolTip(
            self.button_start_camera,
            lang.get("start_camera_tooltip", "启动摄像头进行人脸识别")
        )



        # 添加导出日志按钮
        self.button_export_logs = ttk.Button(
            self.frame_buttons_inner,
            text=lang["export_logs"],
            command=self.export_logs,
            style="TButton"
        )
        self.button_export_logs.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        self.tooltip_export_logs = ToolTip(
            self.button_export_logs,
            lang.get("export_logs_tooltip", "将使用日志导出为CSV文件")
        )

        # 添加导出比对结果按钮（保持现有功能）
        self.button_export_matches = ttk.Button(
            self.frame_buttons_inner,
            text=lang["export_matches"],
            command=self.export_match_results,
            style="TButton"
        )
        self.button_export_matches.grid(row=0, column=4, padx=5, pady=5, sticky='ew')
        self.tooltip_export_matches = ToolTip(
            self.button_export_matches,
            lang.get("export_matches_tooltip", "将比对结果导出为CSV文件")
        )



        # 让所有列在内部框架中均分宽度
        for i in range(5):  # 更新列数为7
            self.frame_buttons_inner.grid_columnconfigure(i, weight=1)

        # 创建分割线
        separator = ttk.Separator(root, orient='horizontal')
        separator.pack(fill='x', padx=20, pady=5)

        # 添加手动输入路径的功能
        self.frame_manual_path = ttk.LabelFrame(
            root, 
            text="手动导入",  # 在这里加一个简短标题
            style="TFrame"
        )
        self.frame_manual_path.pack(pady=10, padx=20, fill='x')

        self.label_manual_path = tk.Label(self.frame_manual_path, text=lang["manual_path_label"],
                                        font=("Helvetica", 12),
                                        bg="#2c3e50",
                                        fg="#ecf0f1")
        self.label_manual_path.pack(side='left', padx=5)

        self.entry_manual_path = tk.Entry(self.frame_manual_path, width=50, font=("Helvetica", 12))
        self.entry_manual_path.pack(side='left', padx=5, fill='x', expand=True)

        self.button_browse_path = ttk.Button(self.frame_manual_path, text=lang["browse"], command=self.browse_folder, style="TButton")
        self.button_browse_path.pack(side='left', padx=5)
        self.tooltip_browse = ToolTip(
            self.button_browse_path,
            lang.get("browse_tooltip", "浏览文件夹")
        )

        self.button_upload_manual_path = ttk.Button(self.frame_manual_path, text=lang["upload"], command=self.upload_faces_from_path, style="TButton")
        self.button_upload_manual_path.pack(side='left', padx=5)
        self.tooltip_upload_manual = ToolTip(
            self.button_upload_manual_path,
            lang.get("upload_tooltip", "上传文件夹中的图片")
        )

        # 创建左侧的文件名列表框架
        self.frame_file_list = tk.Frame(root, bg="#2c3e50")
        self.frame_file_list.pack(pady=10, padx=20, fill='y', side='left')

        self.label_uploaded_files = tk.Label(self.frame_file_list, text=lang["uploaded_files"],
                                            font=("Helvetica", 12, "bold"),
                                            bg="#2c3e50",
                                            fg="#ecf0f1")
        self.label_uploaded_files.pack(pady=5)

        # 创建一个带滚动条的Treeview
        self.scrollbar = tk.Scrollbar(self.frame_file_list, orient=tk.VERTICAL)
        self.tree_files = ttk.Treeview(
            self.frame_file_list,
            columns=("Filename", "Status", "Match Result"),  # 包含所有列
            show='headings',
            yscrollcommand=self.scrollbar.set
        )
        self.scrollbar.config(command=self.tree_files.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.tree_files.pack(side='left', fill='both', expand=True)

        # 定义列标题
        self.tree_files.heading("Filename", text=lang["filename_header"])
        self.tree_files.heading("Status", text=lang["status_header"])
        self.tree_files.heading("Match Result", text=lang["match_result_header"])  # 新增标题

        # 设置列宽和对齐方式
        self.tree_files.column("Filename", width=250, anchor='w')
        self.tree_files.column("Status", width=100, anchor='center')
        self.tree_files.column("Match Result", width=150, anchor='center')  # 设置新列宽度

        # 定义上传成功和失败的标签
        self.tree_files.tag_configure("success", foreground="green")
        self.tree_files.tag_configure("failure", foreground="red")

        # 绑定Treeview的选择事件
        self.tree_files.bind('<<TreeviewSelect>>', self.display_selected_image)

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
        self.context_menu.add_command(label=lang["rotate_right"], command=lambda: self.rotate_image(90))
        self.context_menu.add_command(label=lang["rotate_left"], command=lambda: self.rotate_image(-90))
        self.context_menu.add_command(label=lang["fullscreen_view"], command=self.fullscreen_view)

        # 创建图像控制按钮框架（2x2 网格排列）
        self.frame_image_controls = ttk.Frame(root, style="TFrame")
        self.frame_image_controls.pack(pady=10, padx=20, fill='x')

        # 使用 grid 布局将按钮安排为 2x2
        # 第1行 - 放大和缩小按钮
        self.button_zoom_in = ttk.Button(
            self.frame_image_controls,
            text=lang["zoom_in"],
            command=lambda: self.zoom_image_manual(1.1),
            style="TButton"
        )
        self.button_zoom_in.grid(row=0, column=0, padx=10, pady=5, sticky='nsew')
        self.tooltip_zoom_in = ToolTip(
            self.button_zoom_in,
            lang.get("zoom_in_tooltip", "放大图片")
        )

        self.button_zoom_out = ttk.Button(
            self.frame_image_controls,
            text=lang["zoom_out"],
            command=lambda: self.zoom_image_manual(0.9),
            style="TButton"
        )
        self.button_zoom_out.grid(row=0, column=1, padx=10, pady=5, sticky='nsew')
        self.tooltip_zoom_out = ToolTip(
            self.button_zoom_out,
            lang.get("zoom_out_tooltip", "缩小图片")
        )

        # 第2行 - 顺时针和逆时针旋转按钮
        self.button_rotate_left = ttk.Button(
            self.frame_image_controls,
            text=lang["rotate_left"],
            command=lambda: self.rotate_image(-90),
            style="TButton"
        )
        self.button_rotate_left.grid(row=1, column=0, padx=10, pady=5, sticky='nsew')
        self.tooltip_rotate_left = ToolTip(
            self.button_rotate_left,
            lang.get("rotate_left_tooltip", "逆时针旋转图片")
        )

        self.button_rotate_right = ttk.Button(
            self.frame_image_controls,
            text=lang["rotate_right"],
            command=lambda: self.rotate_image(90),
            style="TButton"
        )
        self.button_rotate_right.grid(row=1, column=1, padx=10, pady=5, sticky='nsew')
        self.tooltip_rotate_right = ToolTip(
            self.button_rotate_right,
            lang.get("rotate_right_tooltip", "顺时针旋转图片")
        )

        # 第3行 - 缩放滑块
        self.scale = tk.Scale(
            self.frame_image_controls,
            from_=10,  # 调整最小值为10%
            to=200,    # 保持最大值为200%
            orient=tk.HORIZONTAL,
            label=lang["scale_label"],
            command=self.scale_image
        )
        self.scale.set(100)  # 初始缩放比例为100%
        self.scale.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky='ew')
        self.tooltip_scale = ToolTip(
            self.scale,
            lang.get("scale_tooltip", "缩放图片")
        )
        self.scale.config(state='normal')  # 使能缩放滑块

        # 设置 grid 中的行和列权重，使按钮和滑块均匀扩展
        self.frame_image_controls.grid_columnconfigure(0, weight=1)
        self.frame_image_controls.grid_columnconfigure(1, weight=1)
        self.frame_image_controls.grid_rowconfigure(0, weight=1)
        self.frame_image_controls.grid_rowconfigure(1, weight=1)
        self.frame_image_controls.grid_rowconfigure(2, weight=1)  # 新增第三行

        # 添加底部版权信息
        self.footer_label = tk.Label(root, text=lang["thank_you"],
                                    font=("Helvetica", 10),
                                    bg="#2c3e50",
                                    fg="#ecf0f1")
        self.footer_label.pack(pady=10)

        # 初始化日志列表
        self.logs = []

        # 启动网络状态和时间更新
        self.check_network()
        self.update_time()

        # 加载图标并创建右下角按钮
        self.load_icons_and_create_bottom_right_buttons(lang)

        # 设置初始语言（确保所有控件已初始化）
        self.set_language(self.current_language)

        # 添加当前缩放因子
        self.current_scale = 1.0  # 初始缩放比例为100%

    def load_icons_and_create_bottom_right_buttons(self, lang):
        """加载图标并创建右下角的帮助和语言选择按钮"""
        try:
            # 加载帮助图标
            help_image = Image.open("icons/info.png")  # 替换为您的帮助图标路径
            help_image = help_image.resize((32, 32), Image.Resampling.LANCZOS)  # 调整大小
            self.help_photo = ImageTk.PhotoImage(help_image)

            # 加载语言选择图标
            lang_image = Image.open("icons/earth.png")  # 替换为您的语言图标路径
            lang_image = lang_image.resize((32, 32), Image.Resampling.LANCZOS)  # 调整大小
            self.lang_photo = ImageTk.PhotoImage(lang_image)

            logger.info("图标已成功加载。")
        except Exception as e:
            messagebox.showerror("图标加载错误", f"无法加载图标: {e}")
            logger.error(f"无法加载图标: {e}")
            raise e

        # 创建一个框架用于右下角的按钮
        self.frame_bottom_right = tk.Frame(self.root, bg="#2c3e50")
        self.frame_bottom_right.place(relx=1.0, rely=1.0, anchor='se', x=-20, y=-20)  # 调整x和y以设置距离右下角的距离

        # 创建帮助按钮
        self.button_help_icon = ttk.Button(
            self.frame_bottom_right,
            image=self.help_photo,
            command=self.show_help,
            style="Icon.TButton"  # 使用自定义样式
        )
        self.button_help_icon.pack(side='right', padx=5)

        self.tooltip_help = ToolTip(
            self.button_help_icon,
            lang.get("help_tooltip", "查看帮助文档")
        )

        # 创建语言选择按钮
        self.button_lang_icon = ttk.Button(
            self.frame_bottom_right,
            image=self.lang_photo,
            command=self.toggle_language_menu,  # 创建一个方法来切换语言菜单
            style="Icon.TButton"
        )
        self.button_lang_icon.pack(side='right', padx=5)

        self.tooltip_lang = ToolTip(
            self.button_lang_icon,
            lang.get("choose_language_tooltip", "选择界面语言")
        )

        # 创建语言菜单（下拉菜单）
        self.language_menu = tk.Menu(self.root, tearoff=0)
        self.language_menu.add_command(label=lang.get("language_chinese", "中文"), command=lambda: self.set_language('zh'))
        self.language_menu.add_command(label=lang.get("language_english", "English"), command=lambda: self.set_language('en'))


    def toggle_language_menu(self):
        """切换语言选择菜单的显示"""
        try:
            # 获取语言按钮的坐标
            x = self.button_lang_icon.winfo_rootx()
            y = self.button_lang_icon.winfo_rooty() + self.button_lang_icon.winfo_height()
            self.language_menu.tk_popup(x, y)
        finally:
            self.language_menu.grab_release()

    def scale_image(self, value):
        """根据Scale控件的值来缩放图像"""
        try:
            # 更新当前缩放因子
            self.current_scale = float(value) / 100  # 从百分比转化为缩放比例
            logger.info(f"缩放比例: {self.current_scale}")

            if not self.original_image:
                logger.warning("没有图像可缩放。")
                messagebox.showwarning("缩放警告", "当前没有图像可缩放。")
                return

            logger.info(f"原始图像大小: {self.original_image.width}x{self.original_image.height}")
            new_width = int(self.original_image.width * self.current_scale)
            new_height = int(self.original_image.height * self.current_scale)
            logger.info(f"新图像大小: {new_width}x{new_height}")

            # 基于原始图像进行缩放
            self.display_image = self.original_image.resize((new_width, new_height), Image.LANCZOS)
            self.photo_image = ImageTk.PhotoImage(self.display_image)
            logger.info("图像缩放完成。")

            # 更新Canvas上的图像
            self.canvas_image.itemconfig(self.image_on_canvas, image=self.photo_image)
            self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))  # 更新Canvas的滚动区域
            logger.info("Canvas图像更新完成。")

            # 确保图像位于Canvas的中心
            self.canvas_image.update_idletasks()
            canvas_width = self.canvas_image.winfo_width()
            canvas_height = self.canvas_image.winfo_height()
            self.canvas_image.coords(self.image_on_canvas, canvas_width // 2, canvas_height // 2)

            # 保持对图像的引用
            self.canvas_image.image = self.photo_image
            logger.info("保持图像引用完成。")
        except Exception as e:
            logger.error(f"缩放图像时发生错误: {e}")
            messagebox.showerror("缩放错误", f"缩放图像时发生错误: {e}")

    def load_languages(self):
        """加载语言资源"""
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
                    "help_window_title": "帮助",
                    # 添加工具提示相关键
                    "zoom_in_tooltip": "放大图片",
                    "zoom_out_tooltip": "缩小图片",
                    "rotate_left_tooltip": "逆时针旋转图片",
                    "rotate_right_tooltip": "顺时针旋转图片",
                    "scale_tooltip": "缩放图片"
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
                    "help_window_title": "Help",
                    # 添加工具提示相关键
                    "zoom_in_tooltip": "Zoom in the image",
                    "zoom_out_tooltip": "Zoom out the image",
                    "rotate_left_tooltip": "Rotate image counterclockwise",
                    "rotate_right_tooltip": "Rotate image clockwise",
                    "scale_tooltip": "Scale the image"
                }
            }
        return languages




    def show_context_menu(self, event):
        """显示右键菜单"""
        self.context_menu.post(event.x_root, event.y_root)

    def option1_action(self):
        print("Option 1 selected")

    def option2_action(self):
        print("Option 2 selected")



    def set_language(self, lang_code):
        """设置界面语言"""
        lang = self.languages.get(lang_code, self.languages['zh'])
        self.current_language = lang_code  # 更新当前语言

        # 更新所有文本
        self.network_status_label.config(text=lang["network_status"])
        self.time_label.config(text=f"{lang['current_time']}: --:--:--")
        self.title_label.config(text=lang["title"])
        self.button_upload_to_library.config(text=lang["upload_images"])
        self.button_match_faces.config(text=lang["match_faces"])  # 更新比对按钮文本
        self.button_start_camera.config(text=lang["start_camera"])
        #self.button_help.config(text=lang["help"])
        self.label_manual_path.config(text=lang["manual_path_label"])
        self.button_browse_path.config(text=lang["browse"])
        self.button_upload_manual_path.config(text=lang["upload"])
        self.label_uploaded_files.config(text=lang["uploaded_files"])
        self.button_export_logs.config(text=lang["export_logs"])
        self.button_export_matches.config(text=lang["export_matches"])  # 更新导出比对结果按钮

        # 更新图像控制按钮的文本
        self.button_zoom_in.config(text=lang["zoom_in"])
        self.button_zoom_out.config(text=lang["zoom_out"])
        self.button_rotate_left.config(text=lang["rotate_left"])
        self.button_rotate_right.config(text=lang["rotate_right"])

        # 更新缩放滑块的标签
        self.scale.config(label=lang["scale_label"])

        # 更新工具提示
        self.tooltip_zoom_in.set_text(lang["zoom_in_tooltip"])
        self.tooltip_zoom_out.set_text(lang["zoom_out_tooltip"])
        self.tooltip_rotate_left.set_text(lang["rotate_left_tooltip"])
        self.tooltip_rotate_right.set_text(lang["rotate_right_tooltip"])
        self.tooltip_scale.set_text(lang["scale_tooltip"])
        self.tooltip_export_logs.set_text(lang.get("export_logs_tooltip", "将使用日志导出为CSV文件"))
        self.tooltip_export_matches.set_text(lang.get("export_matches_tooltip", "将比对结果导出为CSV文件"))
        self.tooltip_help.set_text(lang.get("help_tooltip", "查看帮助文档"))
        self.tooltip_lang.set_text(lang.get("choose_language_tooltip", "选择界面语言"))

        # 更新Treeview列标题
        self.tree_files.heading("Filename", text=lang["filename_header"])
        self.tree_files.heading("Status", text=lang["status_header"])
        self.tree_files.heading("Match Result", text=lang["match_result_header"])  # 更新新列标题

        # 更新底部版权信息
        self.footer_label.config(text=lang["thank_you"])

        # 更新上下文菜单的标签（使用索引或标识符）
        self.context_menu.entryconfig(0, label=lang["rotate_right"])
        self.context_menu.entryconfig(1, label=lang["rotate_left"])
        self.context_menu.entryconfig(2, label=lang["fullscreen_view"])

        # 更新语言菜单中的语言选项
        self.language_menu.entryconfig(0, label=lang.get("language_chinese", "中文"))
        self.language_menu.entryconfig(1, label=lang.get("language_english", "English"))

        logger.info(f"界面语言已切换为: {lang_code}")




    def change_language(self, event):
        """切换界面语言"""
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
        """浏览文件夹并选择路径"""
        folder_path = filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder_path:
            self.entry_manual_path.delete(0, tk.END)
            self.entry_manual_path.insert(0, folder_path)
            logger.info(f"手动输入的文件夹路径: {folder_path}")

    def get_headers(self):
        """获取请求头"""
        return {
            "Content-Type": "multipart/form-data"
        }

    def compress_image(self, image_path, max_size=(800, 800)):
        """压缩图片"""
        img = Image.open(image_path)
        img.thumbnail(max_size)
        compressed_image_path = os.path.join(self.uploaded_dir, "compressed_" + os.path.basename(image_path))
        img.save(compressed_image_path)
        logger.info(f"压缩图片保存为: {compressed_image_path}")
        return compressed_image_path

    def enhance_image_opencv(image_path):
        """读取图像"""
        img = cv2.imread(image_path)

        # 转换为HSV颜色空间，方便调整亮度、饱和度
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        # 亮度增强（如果图像过暗）
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.5)  # 调高亮度

        # 直方图均衡化（对比度增强）
        gray = cv2.cvtColor(enhanced_image, cv2.COLOR_BGR2GRAY)
        equalized = cv2.equalizeHist(gray)
        enhanced_image = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)
        
        # 锐化
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)  # 锐化增强

        enhanced_image_path = os.path.join(self.uploaded_dir, "enhanced_" + os.path.basename(image_path))
        img.save(enhanced_image_path)
        logger.info(f"增强图片保存为: {enhanced_image_path}")

        return enhanced_image_path

    def upload_faces(self):
        """上传选定的图片进行人脸识别并比对"""
        logger.info("开始执行 upload_faces 方法")
        
        if not self.selected_image_paths:
            self.root.after(0, lambda: messagebox.showerror(
                self.languages[self.current_language]["error"],
                self.languages[self.current_language]["no_images_selected_error"]
            ))
            logger.error("上传失败：未选择任何图片。")
            self.add_log("上传图片", "失败：未选择任何图片")
            return

        try:
            # 创建一个顶层弹窗来显示处理状态
            progress_window = tk.Toplevel(self.root)
            progress_window.title(self.languages[self.current_language]["match_progress_title"])  # 使用比对相关标题
            progress_window.geometry("400x200")
            progress_window.configure(bg="#2c3e50")

            progress_label = tk.Label(
                progress_window,
                text=self.languages[self.current_language]["matching_images"],  # 使用比对相关文本
                font=("Helvetica", 12),
                bg="#2c3e50",
                fg="#ecf0f1"
            )
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

                    logger.info(f"开始上传图片: {enhanced_image_path}")
                    print(f"开始上传图片: {enhanced_image_path}")  # 临时打印

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

                    logger.debug(f"上传响应: {result}")
                    print(f"上传响应: {result}")  # 临时打印

                    # 判断上传是否成功
                    if 'FaceRecords' in result and len(result['FaceRecords']) > 0:
                        status = "成功"
                        tag = "success"
                        uploaded += 1
                        self.add_log("上传图片到人脸库", "成功", os.path.basename(image_path))
                    else:
                        status = "失败"
                        tag = "failure"
                        failed += 1
                        self.add_log("上传图片到人脸库", f"失败：{result.get('Message', '未知错误')}")

                    # 添加到文件列表并设置颜色
                    filename = os.path.basename(image_path)
                    item_id = self.tree_files.insert(
                        "",
                        "end",
                        values=(filename, status, "N/A"),  # 不进行比对，Match Result 设置为 "N/A"
                        tags=(tag,)
                    )
                    self.filename_to_path[item_id] = image_path  # 使用 item_id 作为键
                    logger.info(f"添加到列表: {filename} - {status}, 路径: {image_path}")
                    print(f"添加到列表: {filename} - {status}, 路径: {image_path}")  # 临时打印

                    # 更新进度条
                    progress_label.config(text=f"{self.languages[self.current_language]['uploading_images']} ({i}/{len(file_paths)})")
                    progress_bar["value"] = i
                    progress_window.update_idletasks()

                except Exception as e:
                    logger.error(f"上传 {image_path} 时发生错误: {e}")
                    self.add_log("上传图片到人脸库", f"失败：{e}")
                    # 添加到 Treeview 即使出现异常
                    filename = os.path.basename(image_path)
                    item_id = self.tree_files.insert(
                        "",
                        "end",
                        values=(filename, "失败", "N/A"),
                        tags=("failure",)
                    )
                    self.filename_to_path[item_id] = image_path
                    failed += 1
                    messagebox.showerror(
                        self.languages[self.current_language]["error"],
                        self.languages[self.current_language]["upload_image_error"].format(
                            image=filename, error=str(e)
                        )
                    )

            # 上传完成后关闭进度窗口并显示结果
            progress_window.destroy()
            messagebox.showinfo(
                self.languages[self.current_language]["upload_complete"],
                self.languages[self.current_language]["upload_success"].format(uploaded=uploaded) + "\n" + 
                self.languages[self.current_language]["upload_failed"].format(failed=failed)
            )
            logger.info(f"批量上传完成！成功上传: {uploaded} 张图片，失败: {failed} 张图片")
            print(f"批量上传完成！成功上传: {uploaded} 张图片，失败: {failed} 张图片")  # 临时打印

            # 自动显示第一张图片（仅上传成功的图片）
            if uploaded > 0:
                # 获取所有项
                all_items = self.tree_files.get_children()
                if all_items:
                    for item in all_items:
                        status = self.tree_files.item(item, 'values')[1]
                        if status == "成功":
                            self.tree_files.selection_set(item)
                            self.tree_files.focus(item)
                            self.tree_files.event_generate("<<TreeviewSelect>>")
                            break

        except Exception as e:
            logger.error(f"上传过程中发生错误: {e}")
            messagebox.showerror(
                self.languages[self.current_language]["error"],
                f"上传过程中发生错误: {e}"
            )
            progress_window.destroy()



    def upload_faces_from_path(self):
        """从手动输入的文件夹路径上传图片"""
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

        # 自动显示第一张图片
        if self.selected_image_paths:
            # 获取所有项
            all_items = self.tree_files.get_children()
            if all_items:
                first_item = all_items[0]
                self.tree_files.selection_set(first_item)
                self.tree_files.focus(first_item)
                self.tree_files.event_generate("<<TreeviewSelect>>")




    def match_face(self, image_path):
        """进行人脸匹配"""
        try:
            with open(image_path, "rb") as image_file:
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
            logger.error(f"识别失败：{e}")
            self.add_log("人脸识别", f"失败：{e}")
            return False, None

    def display_selected_image(self, event):
        """显示选中的图片"""
        # 获取选中的行
        selected_items = self.tree_files.selection()
        if not selected_items:
            return
        item = selected_items[0]
        filename = self.tree_files.item(item, "values")[0]
        image_path = self.filename_to_path.get(item)  # 使用 item_id 获取路径

        if image_path and os.path.exists(image_path):
            try:
                # 打开并保存原始图像
                self.original_image = Image.open(image_path).convert("RGB")
                self.display_image = self.original_image.copy()
                self.photo_image = ImageTk.PhotoImage(self.display_image)

                # 在Canvas上显示图像，锚点改为'center'
                if self.image_on_canvas:
                    self.canvas_image.delete(self.image_on_canvas)
                # 确保 Canvas 的尺寸已更新
                self.canvas_image.update_idletasks()
                canvas_width = self.canvas_image.winfo_width()
                canvas_height = self.canvas_image.winfo_height()
                self.image_on_canvas = self.canvas_image.create_image(
                    canvas_width // 2,
                    canvas_height // 2,
                    anchor='center',
                    image=self.photo_image
                )

                # 调整Canvas大小以适应图像
                self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))

                # 保持对图像的引用
                self.canvas_image.image = self.photo_image

                logger.info(f"显示图片: {filename}")

                # 启用缩放滑块并重置其值
                self.scale.config(state='normal')
                self.scale.set(100)  # 重置为100%
                self.display_image = self.original_image.copy()  # 确保 display_image 是 original_image 的副本

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {filename}: {e}")
                logger.error(f"无法打开图片 {filename}: {e}")
                print(f"错误详情: {e}")
                self.scale.config(state='disabled')  # 禁用缩放滑块
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
        if not self.original_image:
            logger.warning("没有图像可缩放。")
            messagebox.showwarning("缩放警告", "当前没有图像可缩放。")
            return

        # 计算新的缩放因子
        new_scale = self.current_scale * scale_factor

        # 限制缩放比例
        if new_scale < 0.1:  # 将最小缩放因子从0.5调整为0.1（10%）
            messagebox.showwarning("缩放限制", "无法缩放到更小的尺寸。")
            return
        if new_scale > 5.0:
            messagebox.showwarning("缩放限制", "无法缩放到更大的尺寸。")
            return

        # 更新当前缩放因子
        self.current_scale = new_scale
        logger.info(f"新的缩放比例: {self.current_scale}")

        # 更新缩放滑块的位置（以反映当前缩放因子）
        self.scale.set(int(self.current_scale * 100))

        # 基于原始图像进行缩放
        try:
            new_width = int(self.original_image.width * self.current_scale)
            new_height = int(self.original_image.height * self.current_scale)
            self.display_image = self.original_image.resize((new_width, new_height), Image.LANCZOS)
            self.photo_image = ImageTk.PhotoImage(self.display_image)
            self.canvas_image.itemconfig(self.image_on_canvas, image=self.photo_image)

            # 确保图像位于Canvas的中心
            self.canvas_image.update_idletasks()
            canvas_width = self.canvas_image.winfo_width()
            canvas_height = self.canvas_image.winfo_height()
            self.canvas_image.coords(self.image_on_canvas, canvas_width // 2, canvas_height // 2)

            # 更新Canvas的滚动区域
            self.canvas_image.config(scrollregion=self.canvas_image.bbox(tk.ALL))

            # 保持对图像的引用
            self.canvas_image.image = self.photo_image
            logger.info("Canvas图像更新完成。")
            logger.info("保持图像引用完成。")
        except Exception as e:
            logger.error(f"缩放图像时发生错误: {e}")
            messagebox.showerror("缩放错误", f"缩放图像时发生错误: {e}")

    def rotate_image(self, angle):
        """旋转图像"""
        if not self.display_image:
            return
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
        if self.image_on_canvas is not None:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            self.canvas_image.move(self.image_on_canvas, dx, dy)
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
        else:
            logger.warning("没有图像在Canvas上，无法移动。")

    def fullscreen_view(self):
        """全屏查看图像"""
        if not self.display_image:
            return
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
        """打开摄像头窗口"""
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
        """更新摄像头画面"""
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
        """捕捉当前帧并进行人脸识别"""
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
        """关闭摄像头窗口并释放资源"""
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
            logger.info("摄像头已释放。")
            self.add_log("关闭摄像头", "成功")
        if hasattr(self, 'camera_window') and self.camera_window.winfo_exists():
            self.camera_window.destroy()
        # 重新启用主窗口
        self.root.attributes("-disabled", False)
        cv2.destroyAllWindows()

        """上传图片"""
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

            # 调用 upload_faces 处理并显示图片
            self.upload_faces()

            # 自动显示第一张图片
            if self.selected_image_paths:
                # 获取所有项
                all_items = self.tree_files.get_children()
                if all_items:
                    first_item = all_items[0]
                    self.tree_files.selection_set(first_item)
                    self.tree_files.focus(first_item)
                    self.tree_files.event_generate("<<TreeviewSelect>>")




        """上传文件夹中的图片"""
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
                # 获取所有项
                all_items = self.tree_files.get_children()
                if all_items:
                    first_item = all_items[0]
                    self.tree_files.selection_set(first_item)
                    self.tree_files.focus(first_item)
                    self.tree_files.event_generate("<<TreeviewSelect>>")

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
        """导出日志为CSV文件"""
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
        """显示帮助文档"""
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

    def export_match_results(self):
        """导出比对结果为CSV文件"""
        export_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if export_path:
            try:
                with open(export_path, mode='w', newline='', encoding='utf-8-sig') as csv_file:
                    fieldnames = ["Filename", "Status", "Match Result"]
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

                    writer.writeheader()
                    for item in self.tree_files.get_children():
                        filename, status, match_result = self.tree_files.item(item, 'values')
                        writer.writerow({
                            "Filename": filename,
                            "Status": status,
                            "Match Result": match_result
                        })

                messagebox.showinfo("导出成功", f"比对结果已成功导出到 {export_path}")
                logger.info(f"比对结果已导出到 {export_path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"导出比对结果失败: {e}")
                logger.error(f"导出比对结果失败: {e}")


    def upload_faces_to_library(self):
        """上传图片到人脸库"""
        # 允许用户选择单张或多张图片
        file_paths = filedialog.askopenfilenames(
            title=self.languages[self.current_language]["upload_images"],
            filetypes=[("Image Files", "*.jpg;*.jpeg;*.png")]
        )
        
        if not file_paths:
            messagebox.showwarning("警告", "未选择任何图片进行上传。")
            logger.warning("上传失败：未选择任何图片。")
            self.add_log("上传图片到人脸库", "失败：未选择任何图片")
            return
        
        # 创建一个顶层弹窗来显示处理状态
        progress_window = tk.Toplevel(self.root)
        progress_window.title(self.languages[self.current_language]["upload_progress_title"])
        progress_window.geometry("400x200")
        progress_window.configure(bg="#2c3e50")

        progress_label = tk.Label(
            progress_window,
            text=self.languages[self.current_language]["uploading_images"],
            font=("Helvetica", 12),
            bg="#2c3e50",
            fg="#ecf0f1"
        )
        progress_label.pack(pady=20)

        progress_bar = ttk.Progressbar(progress_window, length=300, mode='determinate')
        progress_bar.pack(pady=20)

        # 设置进度条最大值为图片数量
        progress_bar["maximum"] = len(file_paths)

        uploaded = 0
        failed = 0

        for i, image_path in enumerate(file_paths, start=1):
            try:
                # 压缩并增强图片
                compressed_image_path = self.compress_image(image_path)  # 压缩图片
                enhanced_image_path = self.enhance_image(compressed_image_path)  # 增强图片

                logger.info(f"开始上传图片: {enhanced_image_path}")
                print(f"开始上传图片: {enhanced_image_path}")  # 临时打印

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

                logger.debug(f"上传响应: {result}")
                print(f"上传响应: {result}")  # 临时打印

                # 判断上传是否成功
                if 'FaceRecords' in result and len(result['FaceRecords']) > 0:
                    status = "成功"
                    tag = "success"
                    uploaded += 1
                    self.add_log("上传图片到人脸库", "成功", os.path.basename(image_path))
                else:
                    status = "失败"
                    tag = "failure"
                    failed += 1
                    self.add_log("上传图片到人脸库", f"失败：{result.get('Message', '未知错误')}")
                
                # 添加到文件列表并设置颜色
                filename = os.path.basename(image_path)
                item_id = self.tree_files.insert(
                    "",
                    "end",
                    values=(filename, status, "N/A"),  # 不进行比对，Match Result 设置为 "N/A"
                    tags=(tag,)
                )
                self.filename_to_path[item_id] = image_path  # 使用 item_id 作为键
                logger.info(f"添加到列表: {filename} - {status}, 路径: {image_path}")
                print(f"添加到列表: {filename} - {status}, 路径: {image_path}")  # 临时打印

                # 更新进度条
                progress_label.config(text=f"{self.languages[self.current_language]['uploading_images']} ({i}/{len(file_paths)})")
                progress_bar["value"] = i
                progress_window.update_idletasks()

            except Exception as e:
                logger.error(f"上传 {image_path} 时发生错误: {e}")
                self.add_log("上传图片到人脸库", f"失败：{e}")
                # 添加到 Treeview 即使出现异常
                filename = os.path.basename(image_path)
                item_id = self.tree_files.insert(
                    "",
                    "end",
                    values=(filename, "失败", "N/A"),
                    tags=("failure",)
                )
                self.filename_to_path[item_id] = image_path
                failed += 1
                messagebox.showerror(
                    self.languages[self.current_language]["error"],
                    self.languages[self.current_language]["upload_image_error"].format(
                        image=filename, error=str(e)
                    )
                )
        
        # 上传完成后关闭进度窗口并显示结果
        progress_window.destroy()
        messagebox.showinfo(
            self.languages[self.current_language]["upload_complete"],
            self.languages[self.current_language]["upload_success"].format(uploaded=uploaded) + "\n" + 
            self.languages[self.current_language]["upload_failed"].format(failed=failed)
        )
        logger.info(f"批量上传完成！成功上传: {uploaded} 张图片，失败: {failed} 张图片")
        print(f"批量上传完成！成功上传: {uploaded} 张图片，失败: {failed} 张图片")  # 临时打印

        # 自动显示第一张图片（仅上传成功的图片）
        if uploaded > 0:
            # 获取所有项
            all_items = self.tree_files.get_children()
            if all_items:
                for item in all_items:
                    status = self.tree_files.item(item, 'values')[1]
                    if status == "成功":
                        self.tree_files.selection_set(item)
                        self.tree_files.focus(item)
                        self.tree_files.event_generate("<<TreeviewSelect>>")
                        break

    def match_faces_from_images(self):
        """上传图片进行人脸比对"""
        # 允许用户选择单张或多张图片
        file_paths = filedialog.askopenfilenames(
            title=self.languages[self.current_language]["match_faces"],
            filetypes=[("Image Files", "*.jpg;*.jpeg;*.png")]
        )
        
        if not file_paths:
            messagebox.showwarning("警告", "未选择任何图片进行比对。")
            logger.warning("比对失败：未选择任何图片。")
            self.add_log("比对图片", "失败：未选择任何图片")
            return
        
        # 创建一个顶层弹窗来显示处理状态
        progress_window = tk.Toplevel(self.root)
        progress_window.title(self.languages[self.current_language]["upload_progress_title"])  # 可更改为比对相关标题
        progress_window.geometry("400x200")
        progress_window.configure(bg="#2c3e50")

        progress_label = tk.Label(
            progress_window,
            text=self.languages[self.current_language]["uploading_images"],  # 可更改为比对相关文本
            font=("Helvetica", 12),
            bg="#2c3e50",
            fg="#ecf0f1"
        )
        progress_label.pack(pady=20)

        progress_bar = ttk.Progressbar(progress_window, length=300, mode='determinate')
        progress_bar.pack(pady=20)

        # 设置进度条最大值为图片数量
        progress_bar["maximum"] = len(file_paths)

        matched = 0
        unmatched = 0

        for i, image_path in enumerate(file_paths, start=1):
            try:
                # 压缩并增强图片（可选，根据需要决定）
                compressed_image_path = self.compress_image(image_path)  # 压缩图片
                enhanced_image_path = self.enhance_image(compressed_image_path)  # 增强图片

                logger.info(f"开始比对图片: {enhanced_image_path}")
                print(f"开始比对图片: {enhanced_image_path}")  # 临时打印

                # 进行人脸比对
                match_result, matched_person = self.match_face(enhanced_image_path)

                if match_result:
                    status = "成功"
                    match_display = matched_person
                    matched += 1
                    self.add_log("比对图片", "成功", matched_person)
                else:
                    status = "失败"
                    match_display = "未匹配"
                    unmatched += 1
                    self.add_log("比对图片", "失败：未匹配到任何人")

                # 添加到文件列表并设置颜色
                filename = os.path.basename(image_path)
                item_id = self.tree_files.insert(
                    "",
                    "end",
                    values=(filename, status, match_display),
                    tags=(tag := "success" if match_result else "failure",)
                )
                self.filename_to_path[item_id] = image_path  # 使用 item_id 作为键
                logger.info(f"添加到列表: {filename} - {status} - {match_display}, 路径: {image_path}")
                print(f"添加到列表: {filename} - {status} - {match_display}, 路径: {image_path}")  # 临时打印

                # 更新进度条
                progress_label.config(text=f"{self.languages[self.current_language]['uploading_images']} ({i}/{len(file_paths)})")  # 可更改为比对相关文本
                progress_bar["value"] = i
                progress_window.update_idletasks()

            except Exception as e:
                logger.error(f"比对 {image_path} 时发生错误: {e}")
                self.add_log("比对图片", f"失败：{e}")
                # 添加到 Treeview 即使出现异常
                filename = os.path.basename(image_path)
                item_id = self.tree_files.insert(
                    "",
                    "end",
                    values=(filename, "失败", "N/A"),
                    tags=("failure",)
                )
                self.filename_to_path[item_id] = image_path
                unmatched += 1
                messagebox.showerror(
                    self.languages[self.current_language]["error"],
                    self.languages[self.current_language]["upload_image_error"].format(
                        image=filename, error=str(e)
                    )
                )
        
        # 比对完成后关闭进度窗口并显示结果
        progress_window.destroy()
        messagebox.showinfo(
            self.languages[self.current_language]["upload_complete"],  # 可更改为比对相关标题
            self.languages[self.current_language]["upload_success"].format(uploaded=matched) + "\n" + 
            self.languages[self.current_language]["upload_failed"].format(failed=unmatched)
        )
        logger.info(f"批量比对完成！成功匹配: {matched} 张图片，失败: {unmatched} 张图片")
        print(f"批量比对完成！成功匹配: {matched} 张图片，失败: {unmatched} 张图片")  # 临时打印

        # 自动显示第一张匹配成功的图片
        if matched > 0:
            # 获取所有项
            all_items = self.tree_files.get_children()
            if all_items:
                for item in all_items:
                    status = self.tree_files.item(item, 'values')[1]
                    if status == "成功":
                        self.tree_files.selection_set(item)
                        self.tree_files.focus(item)
                        self.tree_files.event_generate("<<TreeviewSelect>>")
                        break

# 以下是主程序启动部分
if __name__ == "__main__":
    root = tk.Tk()
    app = FaceRecognitionApp(root)
    root.mainloop()

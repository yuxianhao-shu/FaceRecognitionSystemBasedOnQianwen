import base64
import json
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk  # 引入ttk模块，用于进度条和Treeview
from PIL import Image, ImageTk, ImageEnhance
import cv2
import os
import shutil
import tempfile
import atexit
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
import requests  # 用于检测网络连接
from datetime import datetime  # 用于获取本地时间
import csv #增加了导出日志为csv文件的功能
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class FaceRecognitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("人脸识别系统")
        self.root.geometry("1000x800")  # 增加宽度以适应列表
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
        self.access_key_secret =  os.getenv('access_key_secret')  # 从环境变量中读取 AccessKeySecret

        # 阿里云人脸识别 API URL（根据地域不同，可能需要调整）
        self.url = os.getenv('facebody_domain', "facebody.cn-shanghai.aliyuncs.com")

        # 人脸库ID，替换为你自己的库ID
        self.face_lib_id = os.getenv('face_lib_id', 'default')  # 从环境变量中读取 FaceLibId

        # 创建阿里云客户端
        self.client = AcsClient(self.access_key_id, self.access_key_secret, 'cn-shanghai')

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

        #self.button_upload_image = ttk.Button(self.frame_buttons, text="批量上传人脸", command=self.upload_faces)
        #self.button_upload_image.pack(pady=5, fill='x')

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

        self.label_image = tk.Label(self.frame_image, bg="#34495e")
        self.label_image.pack(pady=10, padx=10, fill='both', expand=True)

        # 添加底部版权信息
        self.footer_label = tk.Label(root, text="face-recognition-system based on Qianwen",
                                     font=("Helvetica", 10),
                                     bg="#2c3e50",
                                     fg="#ecf0f1")
        self.footer_label.pack(pady=10)
        # 启动网络状态和时间更新
        self.check_network()
        self.update_time()

    def cleanup_temp_dir(self):
        """在程序退出时清理临时文件夹"""
        try:
            shutil.rmtree(self.temp_dir)
            print(f"临时文件夹 {self.temp_dir} 已删除。")
        except Exception as e:
            print(f"无法删除临时文件夹 {self.temp_dir}: {e}")

    def browse_folder(self):
        folder_path = filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder_path:
            self.entry_manual_path.delete(0, tk.END)
            self.entry_manual_path.insert(0, folder_path)

    def get_headers(self):
        return {
            "Content-Type": "multipart/form-data"
        }

    def compress_image(self, image_path, max_size=(800, 800)):
        img = Image.open(image_path)
        img.thumbnail(max_size)
        compressed_image_path = os.path.join(self.uploaded_dir, "compressed_" + os.path.basename(image_path))
        img.save(compressed_image_path)
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
        return enhanced_image_path

    def upload_faces(self):
        if not self.selected_image_paths:
            messagebox.showerror("错误", "请先选择一张或多张图片！")
            return

        # 创建一个顶层弹窗来显示处理状态
        progress_window = tk.Toplevel(self.root)
        progress_window.title("上传进度")
        progress_window.geometry("400x200")
        progress_window.configure(bg="#2c3e50")

        progress_label = tk.Label(progress_window, text="正在上传图片...",
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
                    messagebox.showerror("上传错误", f"无法打开图片 {image_path}: {e}")
                    print(f"跳过损坏文件: {image_path}, 错误详情: {e}")
                    failed += 1
                    continue  # 跳过损坏的文件

                with open(enhanced_image_path, "rb") as image_file:
                    files = {
                        'file': ('image.jpg', image_file, 'image/jpeg')
                    }

                    data = {
                        'Action': 'AddFace',  # 添加人脸到人脸库
                        'Version': '2019-12-30',  # 版本号
                        'FaceLibId': self.face_lib_id,  # 人脸库ID
                    }

                    # 使用 SDK 构建请求
                    request = CommonRequest()
                    request.set_accept_format('json')
                    request.set_domain("facebody.cn-shanghai.aliyuncs.com")
                    request.set_method('POST')
                    request.set_version('2019-12-30')
                    request.set_action_name('AddFace')
                    request.add_query_param('FaceLibId', self.face_lib_id)
                    request.add_file_param('file', enhanced_image_path)

                    # 发送请求
                    response = self.client.do_action_with_exception(request)
                    result = json.loads(response)
                    if 'FaceRecords' in result:
                        print(f"图片 {image_path} 上传成功！")
                        uploaded += 1
                        # 添加到文件列表
                        filename = os.path.basename(image_path)
                        self.listbox_files.insert(tk.END, filename)
                        self.filename_to_path[filename] = image_path
                    else:
                        print(f"图片 {image_path} 上传失败。错误代码：{json.dumps(result)}")
                        failed += 1

                # 更新进度条
                progress_bar["value"] = i
                progress_window.update_idletasks()

            except Exception as e:
                messagebox.showerror("上传错误", f"上传 {image_path} 时发生错误: {str(e)}\n请检查文件格式或路径是否正确。")
                print(f"上传 {image_path} 时发生错误: {e}")
                failed += 1

        # 上传完成后关闭进度窗口并显示结果
        progress_window.destroy()
        messagebox.showinfo("上传完成", f"批量上传完成！\n成功上传: {uploaded} 张图片\n失败: {failed} 张图片")

    def upload_faces_from_path(self):
        folder_path = self.entry_manual_path.get().strip()
        if not folder_path:
            messagebox.showerror("错误", "请输入文件夹路径！")
            return
        if not os.path.exists(folder_path):
            messagebox.showerror("错误", "输入的路径不存在！")
            return
        if not os.path.isdir(folder_path):
            messagebox.showerror("错误", "输入的路径不是一个文件夹！")
            return

        # 遍历文件夹中的所有图片文件
        image_extensions = (".jpg", ".jpeg", ".png")
        image_paths = [
            os.path.join(folder_path, filename) for filename in os.listdir(folder_path)
            if filename.lower().endswith(image_extensions)
        ]

        if not image_paths:
            messagebox.showwarning("无图片", "该文件夹中没有支持的图片文件（.jpg, .jpeg, .png）！")
            return

        # 将图片复制到上传文件夹
        copied_image_paths = []
        for image_path in image_paths:
            try:
                dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                shutil.copy2(image_path, dest_path)
                copied_image_paths.append(dest_path)
            except Exception as e:
                print(f"复制图片 {image_path} 时发生错误: {e}")

        if not copied_image_paths:
            messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
            return

        # 更新 selected_image_paths
        self.selected_image_paths = copied_image_paths
        print(f"从路径 {folder_path} 复制了 {len(self.selected_image_paths)} 张图片到上传文件夹。")

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
                request.set_domain("facebody.cn-shanghai.aliyuncs.com")
                request.set_method('POST')
                request.set_version('2019-12-30')
                request.set_action_name('SearchFace')
                request.add_query_param('FaceLibId', self.face_lib_id)
                request.add_file_param('file', image_path)

                # 发送请求
                response = self.client.do_action_with_exception(request)
                result = json.loads(response)
                if 'FaceRecords' in result and len(result['FaceRecords']) > 0:
                    return True  # 匹配成功
                else:
                    return False  # 匹配失败
            except Exception as e:
                messagebox.showerror("识别失败", f"识别失败: {e}\n请确保摄像头正常工作并重新尝试。")
                return False

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
                img = Image.open(image_path).convert("RGB")
                img = img.resize((600, 400), Image.LANCZOS)  # 调整大小以适应显示区域

                img_tk = ImageTk.PhotoImage(img)
                print(f"ImageTk.PhotoImage created for {filename}: {img_tk}")  # 调试信息

                # 将图像添加到实例列表中以保持引用
                self.images.append(img_tk)

                # 更新label的image属性，并确保引用不被垃圾回收
                self.label_image.config(image=img_tk)
                self.label_image.image = img_tk  # 保持引用有效

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {filename}: {e}")  # 捕获并显示错误
                print(f"错误详情: {e}")  # 打印详细的错误信息

    def open_camera_window(self):
        # 创建一个新的顶层窗口
        self.camera_window = tk.Toplevel(self.root)
        self.camera_window.title("摄像头")
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
        self.capture_button = ttk.Button(self.camera_window, text="拍照", command=self.capture_photo)
        self.capture_button.pack(pady=10)

        # 打开摄像头
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("摄像头错误", "无法打开摄像头，请检查摄像头连接。")
            self.close_camera_window()
            return

        # 开始视频流更新
        self.update_camera_frame()

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
        if hasattr(self, 'current_frame'):
            # 生成唯一的文件名
            timestamp = int(cv2.getTickCount())
            captured_image_path = os.path.join(self.camera_dir, f"captured_face_{timestamp}.jpg")
            self.current_frame.save(captured_image_path)
            messagebox.showinfo("拍照成功", f"图片已保存为 {captured_image_path}")

            # 进行人脸匹配
            if self.match_face(captured_image_path):
                messagebox.showinfo("结果", "此人在人脸库中！")
            else:
                messagebox.showinfo("结果", "此人不在库中！")

            # 提示用户是否继续
            if not messagebox.askyesno("继续", "是否继续上传新图片或继续拍照？"):
                self.close_camera_window()

    def close_camera_window(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        if hasattr(self, 'camera_window'):
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
            print("选择的图片路径:", file_paths)  # 打印图片路径

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in file_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                except Exception as e:
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                return

            self.selected_image_paths = copied_image_paths
            print(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")

            try:
                for image_path in self.selected_image_paths:
                    # 这里只显示每张图片的文件名到Listbox
                    img = Image.open(image_path).convert("RGB")  # 转换为RGB避免一些格式问题
                    img = img.resize((300, 300), Image.LANCZOS)  # 使用 Image.LANCZOS 调整大小

                    img_tk = ImageTk.PhotoImage(img)
                    print(f"ImageTk.PhotoImage created: {img_tk}")  # 调试信息

                    # 将图像添加到实例列表中以保持引用
                    self.images.append(img_tk)

                    # 更新label的image属性，并确保引用不被垃圾回收
                    self.label_image.config(image=img_tk)
                    self.label_image.image = img_tk  # 保持引用有效

                    # 添加到文件列表
                    filename = os.path.basename(image_path)
                    self.listbox_files.insert(tk.END, filename)
                    self.filename_to_path[filename] = image_path

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {self.selected_image_paths[0]}: {e}")  # 捕获并显示错误
                print(f"错误详情: {e}")  # 打印详细的错误信息

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
                return

            print(f"选择的文件夹: {folder_path}")
            print(f"找到 {len(image_paths)} 张图片")

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in image_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                except Exception as e:
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                return

            self.selected_image_paths = copied_image_paths
            print(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")

            try:
                for image_path in self.selected_image_paths:
                    # 这里只显示每张图片的文件名到Listbox
                    img = Image.open(image_path).convert("RGB")
                    img = img.resize((300, 300), Image.LANCZOS)  # 使用 Image.LANCZOS 调整大小
                    img_tk = ImageTk.PhotoImage(img)
                    print(f"ImageTk.PhotoImage created for folder: {img_tk}")  # 调试信息

                    # 将图像添加到实例列表中以保持引用
                    self.images.append(img_tk)

                    # 更新label的image属性，并确保引用不被垃圾回收
                    self.label_image.config(image=img_tk)
                    self.label_image.image = img_tk

                    # 添加到文件列表
                    filename = os.path.basename(image_path)
                    self.listbox_files.insert(tk.END, filename)
                    self.filename_to_path[filename] = image_path

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {self.selected_image_paths[0]}: {e}")  # 捕获并显示错误
                print(f"错误详情: {e}")  # 打印详细的错误信息

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
                img = Image.open(image_path).convert("RGB")
                img = img.resize((600, 400), Image.LANCZOS)  # 调整大小以适应显示区域

                img_tk = ImageTk.PhotoImage(img)
                print(f"ImageTk.PhotoImage created for {filename}: {img_tk}")  # 调试信息

                # 将图像添加到实例列表中以保持引用
                self.images.append(img_tk)

                # 更新label的image属性，并确保引用不被垃圾回收
                self.label_image.config(image=img_tk)
                self.label_image.image = img_tk  # 保持引用有效

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {filename}: {e}")  # 捕获并显示错误
                print(f"错误详情: {e}")  # 打印详细的错误信息

    def open_camera_window(self):
        # 创建一个新的顶层窗口
        self.camera_window = tk.Toplevel(self.root)
        self.camera_window.title("摄像头")
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
        self.capture_button = ttk.Button(self.camera_window, text="拍照", command=self.capture_photo)
        self.capture_button.pack(pady=10)

        # 打开摄像头
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("摄像头错误", "无法打开摄像头，请检查摄像头连接。")
            self.close_camera_window()
            return

        # 开始视频流更新
        self.update_camera_frame()

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
        if hasattr(self, 'current_frame'):
            # 生成唯一的文件名
            timestamp = int(cv2.getTickCount())
            captured_image_path = os.path.join(self.camera_dir, f"captured_face_{timestamp}.jpg")
            self.current_frame.save(captured_image_path)
            messagebox.showinfo("拍照成功", f"图片已保存为 {captured_image_path}")

            # 进行人脸匹配
            if self.match_face(captured_image_path):
                messagebox.showinfo("结果", "此人在人脸库中！")
            else:
                messagebox.showinfo("结果", "此人不在库中！")

            # 提示用户是否继续
            if not messagebox.askyesno("继续", "是否继续上传新图片或继续拍照？"):
                self.close_camera_window()

    def close_camera_window(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        if hasattr(self, 'camera_window'):
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
            print("选择的图片路径:", file_paths)  # 打印图片路径

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in file_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                except Exception as e:
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                return

            self.selected_image_paths = copied_image_paths
            print(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")

            try:
                for image_path in self.selected_image_paths:
                    # 这里只显示每张图片的文件名到Listbox
                    img = Image.open(image_path).convert("RGB")  # 转换为RGB避免一些格式问题
                    img = img.resize((300, 300), Image.LANCZOS)  # 使用 Image.LANCZOS 调整大小

                    img_tk = ImageTk.PhotoImage(img)
                    print(f"ImageTk.PhotoImage created: {img_tk}")  # 调试信息

                    # 将图像添加到实例列表中以保持引用
                    self.images.append(img_tk)

                    # 更新label的image属性，并确保引用不被垃圾回收
                    self.label_image.config(image=img_tk)
                    self.label_image.image = img_tk  # 保持引用有效

                    # 添加到文件列表
                    filename = os.path.basename(image_path)
                    self.listbox_files.insert(tk.END, filename)
                    self.filename_to_path[filename] = image_path

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {self.selected_image_paths[0]}: {e}")  # 捕获并显示错误
                print(f"错误详情: {e}")  # 打印详细的错误信息

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
                return

            print(f"选择的文件夹: {folder_path}")
            print(f"找到 {len(image_paths)} 张图片")

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in image_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                except Exception as e:
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                return

            self.selected_image_paths = copied_image_paths
            print(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")

            try:
                for image_path in self.selected_image_paths:
                    # 这里只显示每张图片的文件名到Listbox
                    img = Image.open(image_path).convert("RGB")
                    img = img.resize((300, 300), Image.LANCZOS)  # 使用 Image.LANCZOS 调整大小
                    img_tk = ImageTk.PhotoImage(img)
                    print(f"ImageTk.PhotoImage created for folder: {img_tk}")  # 调试信息

                    # 将图像添加到实例列表中以保持引用
                    self.images.append(img_tk)

                    # 更新label的image属性，并确保引用不被垃圾回收
                    self.label_image.config(image=img_tk)
                    self.label_image.image = img_tk

                    # 添加到文件列表
                    filename = os.path.basename(image_path)
                    self.listbox_files.insert(tk.END, filename)
                    self.filename_to_path[filename] = image_path

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {self.selected_image_paths[0]}: {e}")  # 捕获并显示错误
                print(f"错误详情: {e}")  # 打印详细的错误信息

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
                img = Image.open(image_path).convert("RGB")
                img = img.resize((600, 400), Image.LANCZOS)  # 调整大小以适应显示区域

                img_tk = ImageTk.PhotoImage(img)
                print(f"ImageTk.PhotoImage created for {filename}: {img_tk}")  # 调试信息

                # 将图像添加到实例列表中以保持引用
                self.images.append(img_tk)

                # 更新label的image属性，并确保引用不被垃圾回收
                self.label_image.config(image=img_tk)
                self.label_image.image = img_tk  # 保持引用有效

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {filename}: {e}")  # 捕获并显示错误
                print(f"错误详情: {e}")  # 打印详细的错误信息

    def open_camera_window(self):
        # 创建一个新的顶层窗口
        self.camera_window = tk.Toplevel(self.root)
        self.camera_window.title("摄像头")
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
        self.capture_button = ttk.Button(self.camera_window, text="拍照", command=self.capture_photo)
        self.capture_button.pack(pady=10)

        # 打开摄像头
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("摄像头错误", "无法打开摄像头，请检查摄像头连接。")
            self.close_camera_window()
            return

        # 开始视频流更新
        self.update_camera_frame()

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
        if hasattr(self, 'current_frame'):
            # 生成唯一的文件名
            timestamp = int(cv2.getTickCount())
            captured_image_path = os.path.join(self.camera_dir, f"captured_face_{timestamp}.jpg")
            self.current_frame.save(captured_image_path)
            messagebox.showinfo("拍照成功", f"图片已保存为 {captured_image_path}")

            # 进行人脸匹配
            if self.match_face(captured_image_path):
                messagebox.showinfo("结果", "此人在人脸库中！")
            else:
                messagebox.showinfo("结果", "此人不在库中！")

            # 提示用户是否继续
            if not messagebox.askyesno("继续", "是否继续上传新图片或继续拍照？"):
                self.close_camera_window()

    def close_camera_window(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        if hasattr(self, 'camera_window'):
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
            print("选择的图片路径:", file_paths)  # 打印图片路径

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in file_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                except Exception as e:
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                return

            self.selected_image_paths = copied_image_paths
            print(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")

            try:
                for image_path in self.selected_image_paths:
                    # 这里只显示每张图片的文件名到Listbox
                    img = Image.open(image_path).convert("RGB")  # 转换为RGB避免一些格式问题
                    img = img.resize((300, 300), Image.LANCZOS)  # 使用 Image.LANCZOS 调整大小

                    img_tk = ImageTk.PhotoImage(img)
                    print(f"ImageTk.PhotoImage created: {img_tk}")  # 调试信息

                    # 将图像添加到实例列表中以保持引用
                    self.images.append(img_tk)

                    # 更新label的image属性，并确保引用不被垃圾回收
                    self.label_image.config(image=img_tk)
                    self.label_image.image = img_tk  # 保持引用有效

                    # 添加到文件列表
                    filename = os.path.basename(image_path)
                    self.listbox_files.insert(tk.END, filename)
                    self.filename_to_path[filename] = image_path

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {self.selected_image_paths[0]}: {e}")  # 捕获并显示错误
                print(f"错误详情: {e}")  # 打印详细的错误信息

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
                return

            print(f"选择的文件夹: {folder_path}")
            print(f"找到 {len(image_paths)} 张图片")

            # 将图片复制到上传文件夹
            copied_image_paths = []
            for image_path in image_paths:
                try:
                    dest_path = os.path.join(self.uploaded_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, dest_path)
                    copied_image_paths.append(dest_path)
                except Exception as e:
                    print(f"复制图片 {image_path} 时发生错误: {e}")

            if not copied_image_paths:
                messagebox.showerror("错误", "没有图片被复制到上传文件夹！")
                return

            self.selected_image_paths = copied_image_paths
            print(f"已复制 {len(self.selected_image_paths)} 张图片到上传文件夹。")

            try:
                for image_path in self.selected_image_paths:
                    # 这里只显示每张图片的文件名到Listbox
                    img = Image.open(image_path).convert("RGB")
                    img = img.resize((300, 300), Image.LANCZOS)  # 使用 Image.LANCZOS 调整大小
                    img_tk = ImageTk.PhotoImage(img)
                    print(f"ImageTk.PhotoImage created for folder: {img_tk}")  # 调试信息

                    # 将图像添加到实例列表中以保持引用
                    self.images.append(img_tk)

                    # 更新label的image属性，并确保引用不被垃圾回收
                    self.label_image.config(image=img_tk)
                    self.label_image.image = img_tk

                    # 添加到文件列表
                    filename = os.path.basename(image_path)
                    self.listbox_files.insert(tk.END, filename)
                    self.filename_to_path[filename] = image_path

            except (IOError, SyntaxError) as e:
                messagebox.showerror("错误", f"无法打开图片 {self.selected_image_paths[0]}: {e}")  # 捕获并显示错误
                print(f"错误详情: {e}")  # 打印详细的错误信息


    def check_network(self):
        """定期检查网络连接状态"""
        try:
            response = requests.get("https://www.google.com", timeout=5)
            if response.status_code == 200:
                self.network_status_label.config(text="网络状态: 已连接", fg="green")
            else:
                self.network_status_label.config(text="网络状态: 未连接", fg="red")
        except requests.RequestException:
            self.network_status_label.config(text="网络状态: 未连接", fg="red")
        # 每5秒检查一次
        self.root.after(5000, self.check_network)

    def update_time(self):
        """定期更新时间显示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=f"当前时间: {current_time}")
        # 每秒更新一次
        self.root.after(1000, self.update_time)

if __name__ == "__main__":
    root = tk.Tk()
    app = FaceRecognitionApp(root)
    root.mainloop()

# Face recognition system based on qianwen
# 人脸识别系统
## 项目简介
人脸识别系统是一款基于Python和Tkinter开发的图形用户界面（GUI）应用，利用阿里云人脸识别API实现高效的人脸检测与识别功能。该系统支持上传单张或多张图片、上传整个文件夹的图片、通过摄像头实时捕捉人脸并进行识别。此外，系统具备日志记录与导出功能，支持多语言界面切换，确保用户体验友好且功能全面。
## 功能特性
- **图片上传**：支持单张或多张图片的批量上传，支持`.jpg`、`.jpeg`、`.png`格式。
- **文件夹上传**：一次性上传文件夹内所有支持格式的图片。
- **摄像头捕捉**：启动摄像头实时视频流，拍照并进行人脸识别。
- **图片预览**：上传的图片将显示在列表中，并可点击查看预览。
- **网络状态监测**：实时监测网络连接状态，确保API请求的顺利进行。
- **当前时间显示**：界面顶部显示本地当前时间，实时更新。
- **日志记录与导出**：记录所有操作与识别结果，并支持导出为CSV文件。
- **多语言支持**：支持中文与英文界面切换，满足不同用户需求。
- **环境变量配置**：通过`.env`文件安全管理阿里云API的密钥与配置。
## 安装与配置
### 先决条件
- **Python版本**：确保已安装Python 3.6及以上版本。
### 克隆仓库
```bash
git clone https://github.com/yuxianhao-shu/FaceRecognitionSystemBasedOnQianwen.git
cd FaceRecognitionSystemBasedOnQianwen
```
### 创建虚拟环境（可选）
```bash
python -m venv venv
source venv/bin/activate  # 对于Windows用户：venv\Scripts\activate
```
### 安装依赖
```bash
pip install -r requirements.txt
```
**`requirements.txt`内容示例**：
```
Pillow
opencv-python
aliyunsdkcore
python-dotenv
requests
```
### 配置环境变量
在项目根目录创建一个`.env`文件，并添加以下内容：
```env
access_key_id=你的阿里云AccessKeyId
access_key_secret=你的阿里云AccessKeySecret
face_lib_id=你的阿里云人脸库ID
facebody_domain=facebody.cn-shanghai.aliyuncs.com  # 可根据地域调整
```
**注意**：确保`.env`文件不被公开，以保护你的阿里云密钥安全。
## 使用说明
### 启动应用
运行主程序启动人脸识别系统：
```bash
python app.py
```
### 界面操作
1. **上传图片**：
   - 点击“上传图片”按钮。
   - 在弹出的文件选择对话框中，选择一张或多张支持格式的图片。
   - 选择后，图片将被复制到上传文件夹，并在列表中显示。
2. **上传文件夹图片**：
   - 点击“上传文件夹图片”按钮。
   - 在弹出的文件夹选择对话框中，选择一个包含图片的文件夹。
   - 文件夹中的所有支持格式的图片将被复制到上传文件夹，并在列表中显示。
3. **启动摄像头**：
   - 点击“启动摄像头”按钮。
   - 摄像头窗口将打开，显示实时视频流。
   - 点击“拍照”按钮进行拍照，系统将自动进行人脸识别。
   - 识别结果将以消息框形式显示，并记录在日志中。
4. **手动输入文件夹路径**：
   - 在“手动输入文件夹路径”框中输入目标文件夹的路径。
   - 点击“浏览”按钮可以通过对话框选择文件夹。
   - 点击“上传”按钮，文件夹中的所有支持格式的图片将被复制到上传文件夹，并开始上传。
5. **导出使用日志**：
   - 点击“导出使用日志”按钮。
   - 在弹出的保存对话框中选择保存位置和文件名。
   - 日志将以CSV文件格式导出，记录所有操作和识别结果。
6. **语言切换**：
   - 在语言选择下拉菜单中选择“中文”或“English”。
   - 界面语言将即时切换。
### 查看日志
所有操作和识别结果将记录在`app.log`文件中，位于项目根目录。同时，用户可通过“导出使用日志”功能，将日志导出为CSV文件，便于后续查看与分析。
## 常见问题
- **无法打开摄像头**：
  - 请检查摄像头连接是否正常，或尝试重新启动应用程序。
- **识别结果不准确**：
  - 确保拍摄环境光线充足，摄像头清晰，并使用高质量的图片。
- **CSV文件乱码**：
  - 请确保使用支持UTF-8编码的程序打开，或尝试使用“utf-8-sig”编码导出日志。
- **环境变量错误**：
  - 确保`.env`文件中已正确配置`access_key_id`、`access_key_secret`和`face_lib_id`。
## 开发者联系方式
如有任何问题或建议，请联系开发者：
- **邮箱**：yushifu@shu.edu.cn
## 许可证
本项目采用MIT许可证。详情请参阅[LICENSE](LICENSE)文件。
## 致谢
感谢所有为本项目提供支持与贡献的开发者与用户！
# 安装与运行
```bash
# 克隆仓库
git clone https://github.com/yourusername/face-recognition-system.git
cd face-recognition-system

# （可选）创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Windows用户使用: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
# 在项目根目录创建 .env 文件，并添加以下内容：
# access_key_id=你的阿里云AccessKeyId
# access_key_secret=你的阿里云AccessKeySecret
# face_lib_id=你的阿里云人脸库ID
# facebody_domain=facebody.cn-shanghai.aliyuncs.com

# 运行应用
python main.py
```

# 目录结构

```
face-recognition-system/
├── main.py
├── requirements.txt
├── .env
├── languages.json
├── app.log
└── README.md
```

- `main.py`: 主程序文件。
- `requirements.txt`: Python依赖包列表。
- `.env`: 环境变量配置文件。
- `languages.json`: 多语言支持资源文件。
- `app.log`: 应用运行日志。
- `README.md`: 项目说明文件。

# 语言资源

`languages.json`文件用于支持多语言界面，默认包含中文和英文两种语言。可根据需要添加更多语言支持。

**示例内容**：

```json
{
    "zh": {
        "network_status": "网络状态: 检测中...",
        "current_time": "当前时间",
        "title": "人脸识别系统",
        "upload_images": "上传图片",
        "upload_folder_images": "上传文件夹图片",
        "start_camera": "启动摄像头",
        "manual_path_label": "手动输入文件夹路径:",
        "browse": "浏览",
        "upload": "上传",
        "uploaded_files": "已上传文件列表:",
        "export_logs": "导出使用日志",
        "help": "帮助"
    },
    "en": {
        "network_status": "Network Status: Checking...",
        "current_time": "Current Time",
        "title": "Face Recognition System",
        "upload_images": "Upload Images",
        "upload_folder_images": "Upload Folder Images",
        "start_camera": "Start Camera",
        "manual_path_label": "Manually Input Folder Path:",
        "browse": "Browse",
        "upload": "Upload",
        "uploaded_files": "Uploaded Files List:",
        "export_logs": "Export Logs",
        "help": "Help"
    }
}
```

# 日志管理

系统会自动记录所有操作与识别结果，日志文件为`app.log`，位于项目根目录。同时，用户可通过“导出使用日志”功能，将日志导出为CSV文件，便于后续查看与分析。

# 清理临时文件

应用运行期间会创建临时文件夹存储上传的图片与拍摄的照片。程序退出时，会自动清理这些临时文件夹，确保系统资源不被占用。

# 支持与贡献
欢迎任何形式的贡献与支持！如果发现问题或有改进建议，请通过[GitHub Issues](https://github.com/yuxianhao-shu/FaceRecognitionSystemBasedOnQianwen/issues)与我们联系。
**感谢使用人脸识别系统！**

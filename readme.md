# 🌳 Gradio File Explorer for Remote Environments

A lightweight, web-based file explorer built with Python and Gradio. This tool is designed to help you manage files in remote environments like **RunPod**, **Docker containers**, **Google Colab**, or any headless server where you don't have a native GUI file manager.

It allows you to browse the filesystem, upload files, zip folders for download, and delete items directly from a web interface, exposing a public link for easy access.

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/EazyEzar/gradio-file-explorer.git
cd gradio-file-explorer
```

### 2. Install Dependencies
Make sure you have Python installed, then run:
```bash
pip install -r requirements.txt
```
*Dependencies: `gradio`, `pandas`*

### 3. Run the Explorer
```bash
python app_fex.py
```

The app runs on port **7861** by default.
- It will generate a **public Gradio link** (e.g., `https://xxxx.gradio.live`) which you can use to access your files from anywhere.
- If running locally, access it at `http://localhost:7861`.

## ⚙️ Configuration

The application is pre-configured for remote use:

- **Root Directory**: By default, `ROOT_DIR` is set to `/` in `app_fex.py`.
  > `ROOT_DIR = "/"`
  > This gives you access to the **entire filesystem** of the container/server. Change this variable in the script if you want to restrict access to a specific folder (e.g., `/workspace`).

- **Public Access**: `share=True` is enabled by default in the launch command, which creates a temporary public link.
  > `demo.launch(..., share=True)`

## 🌟 Features

- **Browse**: Navigate directories with a visual interface.
- **Upload**: Drag and drop files to upload them to the current directory on your server.
- **Download**: Select multiple files or folders and download them as a single ZIP file.
- **Delete**: Remove files or folders (with safety confirmation).
- **Sort**: Automatically sorts directories first, then files.

## 📦 Requirements

- Python 3.x
- `gradio`
- `pandas`

#!/usr/bin/env python3
# ros_art_patcher_gui.py - v1.4 最终修正版 (适配 SquashFS-NG 1.3.2)

import os
import sys
import shutil
import tempfile
import subprocess
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox

# 尝试导入 NPK 处理模块
try:
    from npk import NovaPackage, NpkPartID
except ImportError:
    print("错误: 找不到 npk.py 模块。请确保 npk.py 在脚本目录下。")

# 签名密钥
LICENSE_KEY = "9DBC845E9018537810FDAE62824322EEE1B12BAD81FCA28EC295FB397C61CE0B"
SIGN_KEY = "7D008D9B80B036FB0205601FEE79D550927EBCA937B7008CC877281F2F8AC640"

# 机型预设参数
DEVICE_PRESETS = {
    "AX5": {
        "target": "lib/bdwlan/c52_130.bdwlan",
        "offset": "0x1000",
        "size": "64K"
    },
    "AX3600": {
        "target": "lib/bdwlan/h53_soc1_502.bdwlan",
        "offset": "0x1000",
        "size": "128K"
    }
}

def get_tool_path(tool_name):
    # 纯净路径，不带引号
    base_path = os.path.dirname(os.path.realpath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    local_tool = os.path.join(base_path, f"{tool_name}.exe")
    return local_tool if os.path.exists(local_tool) else tool_name

def parse_human_size(size_str):
    size_str = size_str.upper().strip()
    if not size_str: return None
    if size_str.endswith('K'): return int(float(size_str[:-1]) * 1024)
    if size_str.endswith('M'): return int(float(size_str[:-1]) * 1024 * 1024)
    try: return int(size_str, 0)
    except: raise ValueError(f"无效大小: {size_str}")

# ==========================================
# GUI 界面
# ==========================================

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("green")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RouterOS NPK ART 补丁工具 v1.4")
        self.geometry("700x750")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(6, weight=1)

        self.label_title = ctk.CTkLabel(self, text="RouterOS NPK ART 补丁工具", font=ctk.CTkFont(size=22, weight="bold"))
        self.label_title.grid(row=0, column=0, columnspan=3, padx=20, pady=20)

        # 1. 输入 NPK
        self.btn_npk = ctk.CTkButton(self, text="选择原始 NPK", command=self.browse_npk)
        self.btn_npk.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        self.entry_npk = ctk.CTkEntry(self, placeholder_text="选择 .npk 软件包...")
        self.entry_npk.grid(row=1, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew")

        # 2. 输入 ART 文件
        self.btn_art = ctk.CTkButton(self, text="选择 ART 文件", command=self.browse_art)
        self.btn_art.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        self.entry_art = ctk.CTkEntry(self, placeholder_text="选择提取源文件...")
        self.entry_art.grid(row=2, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew")

        # 3. 机型选择
        self.param_frame = ctk.CTkFrame(self)
        self.param_frame.grid(row=3, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")
        self.param_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.param_frame, text="目标机型标签:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=15, sticky="w")
        self.model_selector = ctk.CTkSegmentedButton(self.param_frame, values=list(DEVICE_PRESETS.keys()), command=self.update_model_params)
        self.model_selector.grid(row=0, column=1, padx=10, pady=15, sticky="ew")

        self.info_label = ctk.CTkLabel(self.param_frame, text="载入预设参数...", text_color="gray")
        self.info_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 15), sticky="ew")

        # 4. 输出 NPK
        self.btn_out = ctk.CTkButton(self, text="保存输出 NPK", command=self.browse_out)
        self.btn_out.grid(row=4, column=0, padx=20, pady=10, sticky="w")
        self.entry_out = ctk.CTkEntry(self, placeholder_text="输出文件名...")
        self.entry_out.grid(row=4, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew")

        # 5. 执行
        self.btn_run = ctk.CTkButton(self, text="开始打补丁并打包", height=45, fg_color="green", command=self.run_patch)
        self.btn_run.grid(row=5, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        # 6. 日志
        self.textbox_log = ctk.CTkTextbox(self, state="disabled", font=("Consolas", 12))
        self.textbox_log.grid(row=6, column=0, columnspan=3, padx=20, pady=(0, 20), sticky="nsew")

        self.model_selector.set("AX5")
        self.update_model_params("AX5")

    def log(self, msg, is_error=False):
        self.textbox_log.configure(state="normal")
        prefix = "[错误] " if is_error else ">> "
        self.textbox_log.insert(tk.END, f"{prefix}{msg}\n")
        self.textbox_log.see(tk.END)
        self.textbox_log.configure(state="disabled")
        self.update_idletasks()

    def update_model_params(self, model_name):
        config = DEVICE_PRESETS[model_name]
        info_text = f"参数: {config['offset']} | {config['size']} | {config['target']}"
        self.info_label.configure(text=info_text)

    def browse_npk(self):
        f = filedialog.askopenfilename(filetypes=[("NPK Files", "*.npk")])
        if f: self.entry_npk.delete(0, tk.END); self.entry_npk.insert(0, f)

    def browse_art(self):
        f = filedialog.askopenfilename()
        if f: self.entry_art.delete(0, tk.END); self.entry_art.insert(0, f)

    def browse_out(self):
        f = filedialog.asksaveasfilename(defaultextension=".npk", filetypes=[("NPK Files", "*.npk")])
        if f: self.entry_out.delete(0, tk.END); self.entry_out.insert(0, f)

    def run_patch(self):
        npk_path = self.entry_npk.get()
        art_path = self.entry_art.get()
        out_path = self.entry_out.get()
        model_name = self.model_selector.get()

        if not all([npk_path, art_path, out_path, model_name]):
            messagebox.showerror("错误", "参数不完整")
            return

        config = DEVICE_PRESETS[model_name]
        self.btn_run.configure(state="disabled", text="处理中...")
        workdir = tempfile.mkdtemp(prefix="ros_patch_")
        
        try:
            # 1. 提取 ART
            self.log(f"--- 任务开始: {model_name} ---")
            with open(art_path, 'rb') as f:
                f.seek(int(config['offset'], 0))
                art_data = f.read(parse_human_size(config['size']))

            # 2. 加载 NPK 并验证 SquashFS
            self.log("正在解析 NPK 结构...")
            npk = NovaPackage.load(npk_path)
            sfs_part = npk[NpkPartID.SQUASHFS]
            sfs_data = sfs_part.data
            
            if not sfs_data.startswith(b'hsqs'):
                self.log("警告: 提取的数据头部未发现 'hsqs' 签名，文件系统可能损坏或不标准", True)
            
            self.log(f"提取 SquashFS 大小: {len(sfs_data)} 字节")

            sfs_file = os.path.join(workdir, "fs.sfs")
            root_dir = os.path.join(workdir, "root")
            with open(sfs_file, "wb") as f: f.write(sfs_data)
            
            # 3. 使用列表形式调用 subprocess (不使用 shell=True)
            self.log("正在调用 rdsquashfs 解压...")
            # rdsquashfs 1.3.2 语法: rdsquashfs -u <dir> <file>
            res_unpack = subprocess.run(
                [get_tool_path("rdsquashfs"), "-u", root_dir, sfs_file],
                capture_output=True, text=True
            )
            
            if res_unpack.returncode != 0:
                self.log(f"解压失败 stderr: {res_unpack.stderr}", True)
                raise Exception("SquashFS 解压失败，可能是 NPK 版本不兼容。")

            # 4. 替换
            dest = os.path.join(root_dir, config['target'].replace('/', os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f: f.write(art_data)
            self.log(f"补丁已写入: {config['target']}")

            # 5. 打包
            self.log("正在调用 gensquashfs 打包...")
            os.remove(sfs_file)
            res_pack = subprocess.run(
                [get_tool_path("gensquashfs"), "-D", root_dir, "-c", "xz", "-b", "262144", sfs_file],
                capture_output=True, text=True
            )
            
            if res_pack.returncode != 0:
                self.log(f"打包失败 stderr: {res_pack.stderr}", True)
                raise Exception("SquashFS 打包失败。")

            # 6. 回写签名
            with open(sfs_file, "rb") as f: sfs_part.data = f.read()
            self.log("正在签署并保存 NPK...")
            npk.sign(bytes.fromhex(LICENSE_KEY), bytes.fromhex(SIGN_KEY))
            npk.save(out_path)
            
            self.log(f"成功！输出文件: {os.path.basename(out_path)}")
            messagebox.showinfo("完成", "补丁制作成功！")

        except Exception as e:
            self.log(str(e), True)
            messagebox.showerror("错误", str(e))
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            self.btn_run.configure(state="normal", text="开始打补丁并打包")

if __name__ == "__main__": App().mainloop()

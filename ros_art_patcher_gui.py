#!/usr/bin/env python3
# ros_art_patcher_gui.py - v1.1 预设机型版 RouterOS NPK 补丁工具

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
        self.title("RouterOS NPK ART 补丁工具 v1.1")
        self.geometry("700x750")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(6, weight=1)

        # 标题
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

        # 3. 机型选择与参数显示区
        self.param_frame = ctk.CTkFrame(self)
        self.param_frame.grid(row=3, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")
        self.param_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.param_frame, text="目标机型标签:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=15, sticky="w")
        self.model_selector = ctk.CTkSegmentedButton(self.param_frame, values=list(DEVICE_PRESETS.keys()), command=self.update_model_params)
        self.model_selector.grid(row=0, column=1, padx=10, pady=15, sticky="ew")

        # 参数预览（只读显示，确保固定）
        self.info_label = ctk.CTkLabel(self.param_frame, text="请选择机型以载入预设参数", text_color="gray")
        self.info_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 15), sticky="ew")

        # 4. 输出 NPK
        self.btn_out = ctk.CTkButton(self, text="保存输出 NPK", command=self.browse_out)
        self.btn_out.grid(row=4, column=0, padx=20, pady=10, sticky="w")
        self.entry_out = ctk.CTkEntry(self, placeholder_text="输出文件名...")
        self.entry_out.grid(row=4, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew")

        # 5. 执行
        self.btn_run = ctk.CTkButton(self, text="开始打补丁并打包", height=45, fg_color="green", hover_color="darkgreen", command=self.run_patch)
        self.btn_run.grid(row=5, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        # 6. 日志
        self.textbox_log = ctk.CTkTextbox(self, state="disabled", font=("Consolas", 12))
        self.textbox_log.grid(row=6, column=0, columnspan=3, padx=20, pady=(0, 20), sticky="nsew")

        # 初始默认选择
        self.model_selector.set("AX5")
        self.update_model_params("AX5")

    def update_model_params(self, model_name):
        config = DEVICE_PRESETS[model_name]
        info_text = f"预设参数：偏移量 {config['offset']} | 提取大小 {config['size']} | 目标路径 {config['target']}"
        self.info_label.configure(text=info_text, text_color="#2FA572")
        self.log(f"已切换至机型: {model_name}")

    def browse_npk(self):
        f = filedialog.askopenfilename(filetypes=[("NPK Files", "*.npk")])
        if f:
            self.entry_npk.delete(0, tk.END)
            self.entry_npk.insert(0, f)

    def browse_art(self):
        f = filedialog.askopenfilename()
        if f:
            self.entry_art.delete(0, tk.END)
            self.entry_art.insert(0, f)

    def browse_out(self):
        f = filedialog.asksaveasfilename(defaultextension=".npk")
        if f:
            self.entry_out.delete(0, tk.END)
            self.entry_out.insert(0, f)

    def log(self, msg):
        self.textbox_log.configure(state="normal")
        self.textbox_log.insert(tk.END, f">> {msg}\n")
        self.textbox_log.see(tk.END)
        self.textbox_log.configure(state="disabled")
        self.update_idletasks()

    def run_patch(self):
        npk_path = self.entry_npk.get()
        art_path = self.entry_art.get()
        out_path = self.entry_out.get()
        model_name = self.model_selector.get()

        if not all([npk_path, art_path, out_path, model_name]):
            messagebox.showerror("错误", "请确保已选择输入/输出文件及机型标签")
            return

        config = DEVICE_PRESETS[model_name]
        target_in_fs = config['target'].lstrip("/")
        
        self.btn_run.configure(state="disabled", text="正在处理...")
        workdir = tempfile.mkdtemp(prefix="ros_art_")
        
        try:
            # 1. 提取 ART 数据
            offset = int(config['offset'], 0)
            size = parse_human_size(config['size'])
            
            self.log(f"--- 任务启动 [{model_name}] ---")
            self.log(f"从 ART 提取数据: 偏移={hex(offset)}, 大小={size}")
            
            with open(art_path, 'rb') as f:
                f.seek(offset)
                art_data = f.read(size)
            
            if len(art_data) < size:
                raise Exception(f"提取数据不足，预期 {size} 字节，实际仅得到 {len(art_data)} 字节")

            # 2. 加载 NPK
            self.log("加载原始 NPK 软件包...")
            npk = NovaPackage.load(npk_path)
            
            # 3. 提取 SquashFS
            self.log("解压内部文件系统 (SquashFS)...")
            sfs_data = npk[NpkPartID.SQUASHFS].data
            sfs_file = os.path.join(workdir, "fs.sfs")
            root_dir = os.path.join(workdir, "root")
            with open(sfs_file, "wb") as f: f.write(sfs_data)
            
            subprocess.run(f"unsquashfs -d {root_dir} {sfs_file}", shell=True, check=True)

            # 4. 替换目标文件
            dest_path = os.path.join(root_dir, target_in_fs)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(art_data)
            self.log(f"已替换文件内容: {target_in_fs}")

            # 5. 重建 SquashFS
            self.log("重建文件系统 (XZ 压缩, 256k 块大小)...")
            os.remove(sfs_file)
            # 使用 RouterOS 标准的 SquashFS 打包参数
            subprocess.run(
                f"mksquashfs {root_dir} {sfs_file} -root-owned -Xbcj arm -comp xz -b 256k", 
                shell=True, check=True
            )
            with open(sfs_file, "rb") as f:
                npk[NpkPartID.SQUASHFS].data = f.read()

            # 6. 签名并保存
            self.log("对软件包进行重新签名...")
            npk.sign(bytes.fromhex(LICENSE_KEY), bytes.fromhex(SIGN_KEY))
            npk.save(out_path)
            
            self.log(f"--- 处理成功！ ---")
            self.log(f"输出路径: {os.path.basename(out_path)}")
            
            messagebox.showinfo("完成", f"[{model_name}] 补丁应用成功！\n文件长度 (Hex): {hex(os.path.getsize(out_path)).upper()}")

        except Exception as e:
            self.log(f"错误: {str(e)}", True)
            messagebox.showerror("处理失败", str(e))
        finally:
            shutil.rmtree(workdir)
            self.btn_run.configure(state="normal", text="开始打补丁并打包")

if __name__ == "__main__":
    app = App()
    app.mainloop()

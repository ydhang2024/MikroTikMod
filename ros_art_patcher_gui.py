#!/usr/bin/env python3
import os
import sys
import shutil
import tempfile
import subprocess
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox

# 导入 NPK 处理模块
try:
    from npk import NovaPackage, NpkPartID
except ImportError:
    print("错误: 找不到 npk.py")

# 常量配置
LICENSE_KEY = "9DBC845E9018537810FDAE62824322EEE1B12BAD81FCA28EC295FB397C61CE0B"
SIGN_KEY = "7D008D9B80B036FB0205601FEE79D550927EBCA937B7008CC877281F2F8AC640"

DEVICE_PRESETS = {
    "AX5": {"target": "lib/bdwlan/c52_130.bdwlan", "offset": "0x1000", "size": "64K"},
    "AX3600": {"target": "lib/bdwlan/h53_soc1_502.bdwlan", "offset": "0x1000", "size": "128K"}
}

def get_tool(name):
    base = os.path.dirname(os.path.realpath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    path = os.path.join(base, f"{name}.exe")
    return f'"{path}"' if os.path.exists(path) else name

RDSQUASHFS = get_tool("rdsquashfs")
GENSQUASHFS = get_tool("gensquashfs")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RouterOS NPK ART Patcher v1.3.2")
        self.geometry("700x700")
        
        # 界面布局 (省略部分重复的UI代码，保持逻辑一致)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(self, text="ROS NPK ART 补丁工具 (NG版)", font=("微软雅黑", 20, "bold")).grid(row=0, column=0, columnspan=3, pady=20)

        # 输入/输出选择
        self.add_file_row("原始 NPK:", 1, "entry_npk")
        self.add_file_row("ART 文件:", 2, "entry_art")
        self.add_file_row("输出路径:", 4, "entry_out")

        # 机型选择
        self.model_var = tk.StringVar(value="AX5")
        self.seg_btn = ctk.CTkSegmentedButton(self, values=list(DEVICE_PRESETS.keys()), variable=self.model_var)
        self.seg_btn.grid(row=3, column=0, columnspan=3, padx=20, pady=10, sticky="ew")

        self.btn_run = ctk.CTkButton(self, text="执行打包", fg_color="green", height=40, command=self.run)
        self.btn_run.grid(row=5, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        self.log_box = ctk.CTkTextbox(self, state="disabled", font=("Consolas", 12))
        self.log_box.grid(row=6, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")

    def add_file_row(self, label, row, attr):
        ctk.CTkLabel(self, text=label).grid(row=row, column=0, padx=20, sticky="w")
        entry = ctk.CTkEntry(self)
        entry.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
        setattr(self, attr, entry)
        ctk.CTkButton(self, text="浏览", width=60, command=lambda: self.browse(entry)).grid(row=row, column=2, padx=20)

    def browse(self, entry):
        f = filedialog.askopenfilename()
        if f: entry.delete(0, tk.END); entry.insert(0, f)

    def log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f">> {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.update()

    def run(self):
        conf = DEVICE_PRESETS[self.model_var.get()]
        workdir = tempfile.mkdtemp()
        try:
            self.log(f"开始处理: {self.model_var.get()}")
            # 1. 提取ART
            with open(self.entry_art.get(), 'rb') as f:
                f.seek(int(conf['offset'], 0))
                art_data = f.read(1024 * int(conf['size'].replace('K','')))

            # 2. NPK解包
            npk = NovaPackage.load(self.entry_npk.get())
            sfs_path = os.path.join(workdir, "temp.sfs")
            root_dir = os.path.join(workdir, "root")
            with open(sfs_path, "wb") as f: f.write(npk[NpkPartID.SQUASHFS].data)
            
            # 使用 rdsquashfs 解压
            subprocess.run(f'{RDSQUASHFS} --unpack-dir "{root_dir}" "{sfs_path}"', shell=True, check=True)

            # 3. 替换文件
            dest = os.path.join(root_dir, conf['target'])
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f: f.write(art_data)
            
            # 4. 使用 gensquashfs 打包
            os.remove(sfs_path)
            subprocess.run(f'{GENSQUASHFS} --pack-dir "{root_dir}" --compressor xz --block-size 262144 "{sfs_path}"', shell=True, check=True)
            
            with open(sfs_path, "rb") as f: npk[NpkPartID.SQUASHFS].data = f.read()
            npk.sign(bytes.fromhex(LICENSE_KEY), bytes.fromhex(SIGN_KEY))
            npk.save(self.entry_out.get())
            self.log("完成！")
            messagebox.showinfo("成功", f"补丁已完成\n十六进制长度: {hex(os.path.getsize(self.entry_out.get()))}")
        except Exception as e:
            self.log(f"错误: {e}")
        finally:
            shutil.rmtree(workdir)

if __name__ == "__main__": App().mainloop()

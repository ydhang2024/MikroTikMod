#!/usr/bin/env python3
# ros_art_patcher_gui.py - v1.5 结构修复版 (自动对齐 SquashFS 报头)

import os
import sys
import shutil
import tempfile
import subprocess
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox

try:
    from npk import NovaPackage, NpkPartID
except ImportError:
    print("错误: 找不到 npk.py 模块。")

LICENSE_KEY = "9DBC845E9018537810FDAE62824322EEE1B12BAD81FCA28EC295FB397C61CE0B"
SIGN_KEY = "7D008D9B80B036FB0205601FEE79D550927EBCA937B7008CC877281F2F8AC640"

DEVICE_PRESETS = {
    "AX5": {"target": "lib/bdwlan/c52_130.bdwlan", "offset": "0x1000", "size": "64K"},
    "AX3600": {"target": "lib/bdwlan/h53_soc1_502.bdwlan", "offset": "0x1000", "size": "128K"}
}

def get_tool_path(tool_name):
    base_path = os.path.dirname(os.path.realpath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    local_tool = os.path.join(base_path, f"{tool_name}.exe")
    return local_tool if os.path.exists(local_tool) else tool_name

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RouterOS NPK ART 补丁工具 v1.5")
        self.geometry("700x750")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(self, text="RouterOS NPK ART 补丁工具", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, columnspan=3, padx=20, pady=20)

        # UI 布局保持不变
        self.btn_npk = ctk.CTkButton(self, text="选择原始 NPK", command=self.browse_npk).grid(row=1, column=0, padx=20, pady=10, sticky="w")
        self.entry_npk = ctk.CTkEntry(self, placeholder_text="选择 .npk 软件包..."); self.entry_npk.grid(row=1, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew")

        self.btn_art = ctk.CTkButton(self, text="选择 ART 文件", command=self.browse_art).grid(row=2, column=0, padx=20, pady=10, sticky="w")
        self.entry_art = ctk.CTkEntry(self, placeholder_text="选择提取源文件..."); self.entry_art.grid(row=2, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew")

        self.param_frame = ctk.CTkFrame(self); self.param_frame.grid(row=3, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")
        self.param_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.param_frame, text="目标机型标签:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=15, sticky="w")
        self.model_selector = ctk.CTkSegmentedButton(self.param_frame, values=list(DEVICE_PRESETS.keys()), command=self.update_model_params)
        self.model_selector.grid(row=0, column=1, padx=10, pady=15, sticky="ew")
        self.info_label = ctk.CTkLabel(self.param_frame, text="载入中...", text_color="gray"); self.info_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 15), sticky="ew")

        self.btn_out = ctk.CTkButton(self, text="保存输出 NPK", command=self.browse_out).grid(row=4, column=0, padx=20, pady=10, sticky="w")
        self.entry_out = ctk.CTkEntry(self, placeholder_text="输出文件名..."); self.entry_out.grid(row=4, column=1, columnspan=2, padx=(0, 20), pady=10, sticky="ew")

        self.btn_run = ctk.CTkButton(self, text="开始打补丁并打包", height=45, fg_color="green", command=self.run_patch)
        self.btn_run.grid(row=5, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        self.textbox_log = ctk.CTkTextbox(self, state="disabled", font=("Consolas", 12))
        self.textbox_log.grid(row=6, column=0, columnspan=3, padx=20, pady=(0, 20), sticky="nsew")

        self.model_selector.set("AX5"); self.update_model_params("AX5")

    def log(self, msg, is_error=False):
        self.textbox_log.configure(state="normal")
        self.textbox_log.insert(tk.END, f"{'[错误] ' if is_error else '>> '}{msg}\n")
        self.textbox_log.see(tk.END); self.textbox_log.configure(state="disabled")
        self.update_idletasks()

    def update_model_params(self, m):
        c = DEVICE_PRESETS[m]
        self.info_label.configure(text=f"参数: {c['offset']} | {c['size']} | {c['target']}")

    def browse_npk(self):
        f = filedialog.askopenfilename(filetypes=[("NPK Files", "*.npk")]); 
        if f: self.entry_npk.delete(0, tk.END); self.entry_npk.insert(0, f)

    def browse_art(self):
        f = filedialog.askopenfilename(); 
        if f: self.entry_art.delete(0, tk.END); self.entry_art.insert(0, f)

    def browse_out(self):
        f = filedialog.asksaveasfilename(defaultextension=".npk", filetypes=[("NPK Files", "*.npk")]); 
        if f: self.entry_out.delete(0, tk.END); self.entry_out.insert(0, f)

    def run_patch(self):
        npk_p, art_p, out_p, m_name = self.entry_npk.get(), self.entry_art.get(), self.entry_out.get(), self.model_selector.get()
        if not all([npk_p, art_p, out_p]): return messagebox.showerror("错误", "参数不全")

        config = DEVICE_PRESETS[m_name]
        self.btn_run.configure(state="disabled", text="处理中...")
        workdir = tempfile.mkdtemp(prefix="ros_patch_")
        
        try:
            # 1. 提取 ART
            with open(art_p, 'rb') as f:
                f.seek(int(config['offset'], 0))
                art_data = f.read(int(float(config['size'][:-1]) * 1024) if config['size'].endswith('K') else int(config['size'], 0))

            # 2. 加载 NPK 并修正 SquashFS 报头
            self.log(f"--- 任务开始: {m_name} ---")
            npk = NovaPackage.load(npk_p)
            sfs_part = npk[NpkPartID.SQUASHFS]
            raw_sfs = sfs_part.data
            
            # 调试：打印前 16 字节
            self.log(f"原始数据头 (Hex): {raw_sfs[:16].hex(' ').upper()}")

            # 核心修正：寻找 hsqs 签名位置 (0x68 0x73 0x71 0x73)
            start_idx = raw_sfs.find(b'hsqs')
            if start_idx == -1:
                raise Exception("在该 NPK 分区中未找到有效的 SquashFS 签名 (hsqs)")
            
            if start_idx > 0:
                self.log(f"检测到报头偏移，已自动切除前 {start_idx} 字节")
                sfs_data = raw_sfs[start_idx:]
            else:
                sfs_data = raw_sfs

            sfs_file = os.path.join(workdir, "fs.sfs")
            root_dir = os.path.join(workdir, "root")
            with open(sfs_file, "wb") as f: f.write(sfs_data)
            
            # 3. 解压 - 尝试更显式的参数
            self.log("正在解压文件系统...")
            # 注意：某些版本的 rdsquashfs 需要 --unpack-path
            res_unpack = subprocess.run([get_tool_path("rdsquashfs"), "-u", root_dir, sfs_file], capture_output=True, text=True)
            
            if res_unpack.returncode != 0:
                self.log(f"解压失败详细信息: {res_unpack.stderr}", True)
                raise Exception("SquashFS 结构解析失败。")

            # 4. 替换
            dest = os.path.join(root_dir, config['target'].replace('/', os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f: f.write(art_data)
            self.log(f"成功替换内部文件: {config['target']}")

            # 5. 打包 - 保持原始压缩参数
            self.log("正在重新打包...")
            os.remove(sfs_file)
            res_pack = subprocess.run([get_tool_path("gensquashfs"), "-D", root_dir, "-c", "xz", "-b", "262144", sfs_file], capture_output=True, text=True)
            
            if res_pack.returncode != 0:
                self.log(f"打包失败: {res_pack.stderr}", True)
                raise Exception("打包失败。")

            # 6. 回写并签名
            with open(sfs_file, "rb") as f:
                # 如果之前切除了报头，回写时也要考虑是否需要补回 NPK 原始的非 SFS 数据
                # 这里假设 NPK 容器需要的是纯净的 SFS
                sfs_part.data = f.read()

            self.log("正在重新计算签名...")
            npk.sign(bytes.fromhex(LICENSE_KEY), bytes.fromhex(SIGN_KEY))
            npk.save(out_p)
            
            self.log(f"恭喜！文件已生成: {os.path.basename(out_p)}")
            messagebox.showinfo("成功", "补丁制作成功！")

        except Exception as e:
            self.log(str(e), True)
            messagebox.showerror("错误", str(e))
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            self.btn_run.configure(state="normal", text="开始打补丁并打包")

if __name__ == "__main__": App().mainloop()

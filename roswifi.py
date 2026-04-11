#!/usr/bin/env python3

import os
import sys
import shutil
import argparse
import subprocess
import tempfile

from npk import NovaPackage, NpkPartID

VERSION = "1.1"

LICENSE_KEY = os.getenv('CUSTOM_LICENSE_PRIVATE_KEY')
SIGN_KEY = os.getenv('CUSTOM_NPK_SIGN_PRIVATE_KEY')

def run(cmd):
    print(">", cmd)
    process = subprocess.run(cmd, shell=True)
    if process.returncode != 0:
        print("Command failed")
        sys.exit(1)

def check_tools():
    tools = [
        "unsquashfs",
        "mksquashfs"
    ]
    for t in tools:
        if shutil.which(t) is None:
            print("Missing tool:", t)
            print("Install with:")
            print("sudo apt install squashfs-tools")
            sys.exit(1)

def copy_replace(src, dst):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copy_replace(s, d)
        else:
            shutil.copy2(s, d)
            print("Replace:", item)

def extract_squashfs(data, workdir):
    squashfs = os.path.join(workdir, "fs.sfs")
    with open(squashfs, "wb") as f:
        f.write(data)
    root = os.path.join(workdir, "root")
    run(f"unsquashfs -d {root} {squashfs}")
    return squashfs, root

def rebuild_squashfs(root, squashfs):
    if os.path.exists(squashfs):
        os.remove(squashfs)
    run(
        f"mksquashfs {root} {squashfs} "
        "-root-owned -Xbcj arm -comp xz -b 256k"
    )
    with open(squashfs, "rb") as f:
        return f.read()

def patch_bdwlan_multiple(input_npk, bdwlan_dirs, output_npks):
    
    if not LICENSE_KEY or not SIGN_KEY:
        print("Error: Missing CUSTOM_LICENSE_PRIVATE_KEY or CUSTOM_NPK_SIGN_PRIVATE_KEY env variables.")
        sys.exit(1)

    print("[1/6] Loading Base NPK to extract filesystem")
    base_npk = NovaPackage.load(input_npk)
    pkg = base_npk[NpkPartID.NAME_INFO].data.name
    print("Package:", pkg)

    print("[2/6] Creating temp workspace")
    workdir = tempfile.mkdtemp(prefix="roswifi_")

    try:
        print("[3/6] Extracting base squashfs (Only done once for efficiency)")
        base_squashfs, base_root = extract_squashfs(
            base_npk[NpkPartID.SQUASHFS].data,
            workdir
        )

        for i, (b_dir, o_npk) in enumerate(zip(bdwlan_dirs, output_npks)):
            print(f"\n--- Processing Target {i+1}/{len(bdwlan_dirs)}: {o_npk} ---")
            
            # 为当前修改创建一个独立的文件树副本，防止多个文件夹的修改互相污染
            current_root = os.path.join(workdir, f"root_mod_{i}")
            shutil.copytree(base_root, current_root)

            print(f"[{i+1}-A] Replacing bdwlan from {b_dir}")
            target = os.path.join(current_root, "lib/bdwlan")
            copy_replace(b_dir, target)

            print(f"[{i+1}-B] Rebuilding squashfs")
            new_squashfs_path = os.path.join(workdir, f"fs_mod_{i}.sfs")
            newfs = rebuild_squashfs(current_root, new_squashfs_path)

            print(f"[{i+1}-C] Injecting and Signing package")
            # 重新 load 以保证基础 NPK 对象不受上一次循环的污染
            npk = NovaPackage.load(input_npk)
            npk[NpkPartID.SQUASHFS].data = newfs

            license_key = bytes.fromhex(LICENSE_KEY)
            sign_key = bytes.fromhex(SIGN_KEY)
            npk.sign(license_key, sign_key)

            npk.save(o_npk)
            print(f"[{i+1}-D] Successfully generated: {o_npk}")

    finally:
        print("\nCleaning workspace")
        shutil.rmtree(workdir)

def main():
    parser = argparse.ArgumentParser(
        prog="roswifi",
        description="RouterOS WIFI calibration patch tool (Multi-target Support)"
    )

    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input base NPK"
    )

    parser.add_argument(
        "-b",
        "--bdwlan",
        required=True,
        nargs='+',
        help="bdwlan directories (one or multiple space-separated)"
    )

    parser.add_argument(
        "-o",
        "--output",
        required=True,
        nargs='+',
        help="Output NPKs (must match the number of bdwlan directories)"
    )

    parser.add_argument(
        "--version",
        action="store_true"
    )

    args = parser.parse_args()

    if args.version:
        print("roswifi", VERSION)
        return

    check_tools()

    if not os.path.exists(args.input):
        print("Input NPK not found")
        sys.exit(1)

    if len(args.bdwlan) != len(args.output):
        print("Error: The number of bdwlan directories must match the number of output files.")
        sys.exit(1)

    for b_dir in args.bdwlan:
        if not os.path.exists(b_dir):
            print(f"bdwlan directory not found: {b_dir}")
            sys.exit(1)

    patch_bdwlan_multiple(
        args.input,
        args.bdwlan,
        args.output
    )

if __name__ == "__main__":
    main()

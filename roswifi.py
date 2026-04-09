#!/usr/bin/env python3

import os
import sys
import shutil
import argparse
import subprocess
import tempfile

from npk import NovaPackage, NpkPartID


VERSION = "1.0"


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


def patch_bdwlan(input_npk, bdwlan_dir, output_npk):

    print("[1/6] Loading NPK")

    npk = NovaPackage.load(input_npk)

    pkg = npk[NpkPartID.NAME_INFO].data.name

    print("Package:", pkg)

    print("[2/6] Creating temp workspace")

    workdir = tempfile.mkdtemp(prefix="roswifi_")

    try:

        print("[3/6] Extracting squashfs")

        squashfs, root = extract_squashfs(
            npk[NpkPartID.SQUASHFS].data,
            workdir
        )

        print("[4/6] Replacing bdwlan")

        target = os.path.join(root, "lib/bdwlan")

        copy_replace(bdwlan_dir, target)

        print("[5/6] Rebuilding squashfs")

        newfs = rebuild_squashfs(root, squashfs)

        npk[NpkPartID.SQUASHFS].data = newfs

        print("[6/6] Signing package")

        license_key = bytes.fromhex(LICENSE_KEY)
        sign_key = bytes.fromhex(SIGN_KEY)

        npk.sign(license_key, sign_key)

        npk.save(output_npk)

        print("Output:", output_npk)

    finally:

        print("Cleaning workspace")

        shutil.rmtree(workdir)


def main():

    parser = argparse.ArgumentParser(
        prog="roswifi",
        description="RouterOS WIFI calibration patch tool"
    )

    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input NPK"
    )

    parser.add_argument(
        "-b",
        "--bdwlan",
        required=True,
        help="bdwlan directory"
    )

    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output NPK"
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

    if not os.path.exists(args.bdwlan):
        print("bdwlan directory not found")
        sys.exit(1)

    patch_bdwlan(
        args.input,
        args.bdwlan,
        args.output
    )


if __name__ == "__main__":
    main()


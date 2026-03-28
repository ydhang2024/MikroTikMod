#!/bin/bash

# 用法: ./wifipatch.sh <MODE> <ART_FILE> <NPK_FILE1> <NPK_FILE2> ...
usage() {
    echo "用法: $0 <MODE> <ART_FILE> <NPK_FILE1> [NPK_FILE2 ...]"
    exit 1
}

if [ $# -lt 3 ]; then usage; fi

MODE=$1
BIN=$2
shift 2 # 移除前两个参数，剩下全是要处理的 NPK 文件
NPK_FILES=$@

# 1. 自动提取 MAC 标识 (假设格式为 mtd8_MAC_ART.bin)
# 提取文件名 -> 去掉路径 -> 提取中间的 MAC 部分
FILENAME=$(basename "$BIN")
MAC_ID=$(echo "$FILENAME" | cut -d'_' -f2)

# 如果没提取到（格式不对），给个默认值
if [ -z "$MAC_ID" ]; then MAC_ID="UNKNOWN"; fi

# 2. 根据模式设置基础参数
case $MODE in
    1) OFFSET="0x1000"; SIZE=$((64*1024)); OUTFILE="c52_130.bdwlan"; MODENAME="AX5" ;;
    2) OFFSET="0x1000"; SIZE=$((128*1024)); OUTFILE="h53_soc1_502.bdwlan"; MODENAME="AX3600" ;;
    *) echo "错误: 目前批量模式仅支持模式 1 和 2"; exit 1 ;;
esac

echo ">>> 启动批量任务 <<<"
echo "设备模式: $MODENAME | MAC标识: $MAC_ID"
echo "--------------------------------------"

# 3. 循环处理每一个 NPK 文件
for NPK in $NPK_FILES; do
    if [ ! -f "$NPK" ]; then
        echo "跳过: 文件 $NPK 不存在"
        continue
    fi

    # 构造输出文件名: 模式名_MAC标识_原始文件名
    ORIG_NPK_NAME=$(basename "$NPK")
    FINAL_OUT="${MODENAME}_${MAC_ID}-${ORIG_NPK_NAME}"

    echo "正在处理: $ORIG_NPK_NAME -> $FINAL_OUT"

    # 截取二进制
    dd if="$BIN" of="$OUTFILE" skip=$OFFSET count=$SIZE iflag=skip_bytes,count_bytes status=none

    # 封装
    mkdir -p bdwlan
    mv "$OUTFILE" bdwlan/
    python3 roswifi.py -i "$NPK" -b bdwlan/ -o "$FINAL_OUT"
    
    # 清理临时目录
    rm -rf bdwlan/
    echo "完成: $FINAL_OUT"
    echo "--------------------------------------"
done

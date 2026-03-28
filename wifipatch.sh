#!/bin/bash

# 用法: ./wifipatch.sh <MODE> <MAC_FRAGMENT> <VER_FRAGMENT1> [VER_FRAGMENT2 ...]
usage() {
    echo "用法: $0 <MODE> <MAC_FRAGMENT> <VER_FRAGMENT1> [VER_FRAGMENT2 ...]"
    exit 1
}

if [ $# -lt 3 ]; then usage; fi

MODE=$1
MAC_QUERY=$2
shift 2
VER_QUERIES=$@

# 1. 精准检索 ART 文件
# 规则：匹配 mtd8_*.bin 且中间包含指定的 MAC 片段
# 使用 grep 正则确保匹配的是两个下划线中间的内容
BIN=$(ls art/mtd8_*.bin 2>/dev/null | grep -E "mtd8_[^_]*${MAC_QUERY}[^_]*_ART\.bin" | head -n 1)

if [ -z "$BIN" ]; then
    echo "::error::在 art/ 目录中找不到匹配 MAC '$MAC_QUERY' 的 ART 文件 (规则: mtd8_..._ART.bin)"
    exit 1
fi

# 提取完整的 MAC 标识用于最终命名
MAC_ID=$(basename "$BIN" | cut -d'_' -f2)
echo ">>> 已锁定 ART: $BIN (完整 MAC: $MAC_ID)"

# 2. 模式定义
case $MODE in
    1) OFFSET="0x1000"; SIZE=$((64*1024)); OUTFILE="c52_130.bdwlan"; MODENAME="AX5" ;;
    2) OFFSET="0x1000"; SIZE=$((128*1024)); OUTFILE="h53_soc1_502.bdwlan"; MODENAME="AX3600" ;;
    *) echo "::error::无效模式"; exit 1 ;;
esac

# 3. 循环检索并处理 NPK 文件
for VER in $VER_QUERIES; do
    # 规则：匹配包含指定版本号且以 .npk 结尾的文件
    # \b 表示单词边界，防止 7.1 匹配到 7.15 (在文件名处理中通常用 - 或 . 分隔)
    # 这里使用更稳妥的 grep 过滤
    NPK=$(ls qcom/*.npk 2>/dev/null | grep -E "[-.]${VER}([-.]|$)" | head -n 1)
    
    if [ -z "$NPK" ]; then
        echo "::warning::跳过：在 qcom/ 找不到版本 '$VER' (建议检查文件名是否包含该版本号)"
        continue
    fi

    ORIG_NPK_NAME=$(basename "$NPK")
    # 最终输出格式：模式名_MAC标识-原始文件名
    FINAL_OUT="${MODENAME}_${MAC_ID}-${ORIG_NPK_NAME}"

    echo "--------------------------------------"
    echo "处理版本: $VER -> 匹配文件: $ORIG_NPK_NAME"
    
    # 二进制提取
    dd if="$BIN" of="$OUTFILE" skip=$OFFSET count=$SIZE iflag=skip_bytes,count_bytes status=none
    
    # 目录操作
    mkdir -p bdwlan
    mv "$OUTFILE" bdwlan/
    
    # 调用 Python 封装逻辑
    # 确保 roswifi.py, npk.py, toyecc 都在根目录
    python3 roswifi.py -i "$NPK" -b bdwlan/ -o "$FINAL_OUT"
    
    rm -rf bdwlan/
    echo "生成成功: $FINAL_OUT"
done

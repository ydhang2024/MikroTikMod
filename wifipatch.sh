#!/bin/bash

# =================================================================
# RouterOS WIFI Patch Tool (2026 自动化版)
# 支持功能：模糊匹配、正则检索、批量处理、MAC自动提取
# =================================================================

usage() {
    echo "用法: $0 <MODE> <MAC_FRAGMENT> <VER_FRAGMENT1> [VER_FRAGMENT2 ...]"
    echo "示例: $0 2 A1B2 7.15 7.16"
    echo "  MODE: 1(AX5/1800), 2(AX6/3600)"
    echo "  MAC_FRAGMENT: ART文件名中的MAC片段 (如 a1b2)"
    echo "  VER_FRAGMENT: NPK文件名中的版本片段 (如 7.15)"
    exit 1
}

# 基础检查
if [ $# -lt 3 ]; then
    usage
fi

MODE=$1
MAC_QUERY=$2
shift 2
VER_QUERIES=$@

# 1. 自动检索 ART 文件 (精准正则 + 不区分大小写)
# 匹配规则: art/mtd8_xxxx_ART.bin
BIN=$(ls art/mtd8_*.bin 2>/dev/null | grep -Ei "mtd8_[^_]*${MAC_QUERY}[^_]*_ART\.bin" | head -n 1)

if [ -z "$BIN" ]; then
    echo "::error::在 art/ 目录中找不到匹配 '$MAC_QUERY' 的文件 (需符合 mtd8_MAC_ART.bin 格式)"
    exit 1
fi

# 从找到的完整文件名中提取真实的 MAC 标识用于后续命名
MAC_ID=$(basename "$BIN" | cut -d'_' -f2)
echo ">>> [确认] ART文件: $BIN"
echo ">>> [确认] 识别到MAC: $MAC_ID"

# 2. 根据模式设置硬件参数
case $MODE in
    1)
        OFFSET="0x1000"
        SIZE=$(( 64 * 1024 ))
        OUTFILE="c52_130.bdwlan"
        MODENAME="AX5"
        ;;
    2)
        OFFSET="0x1000"
        SIZE=$(( 128 * 1024 ))
        OUTFILE="h53_soc1_502.bdwlan"
        MODENAME="AX3600"
        ;;
    *)
        echo "::error::无效模式 $MODE (仅支持 1 或 2)"
        exit 1
        ;;
esac

echo ">>> [确认] 运行模式: $MODENAME"
echo "----------------------------------------------------------------"

# 3. 循环处理每一个版本片段
for VER in $VER_QUERIES; do
    # 检索 NPK 文件 (忽略大小写，且版本号前后应有分隔符防止误匹配)
    NPK=$(ls qcom/*.npk 2>/dev/null | grep -Ei "[-.]${VER}([-.]|$)" | head -n 1)
    
    if [ -z "$NPK" ]; then
        echo "::warning::跳过版本 '$VER': 在 qcom/ 目录中未找到匹配文件"
        continue
    fi

    ORIG_NPK_NAME=$(basename "$NPK")
    # 生成文件名格式：模式名_MAC标识-原始文件名.npk
    FINAL_OUT="${MODENAME}_${MAC_ID}-${ORIG_NPK_NAME}"

    echo "正在修补版本: $VER"
    echo "  源文件: $ORIG_NPK_NAME"
    echo "  生成结果: $FINAL_OUT"

    # --- 核心逻辑开始 ---
    
    # 提取二进制 (dd)
    # status=none 隐藏 dd 的冗余输出
    dd if="$BIN" of="$OUTFILE" skip=$OFFSET count=$SIZE iflag=skip_bytes,count_bytes status=none

    # 创建临时处理目录
    mkdir -p bdwlan
    mv "$OUTFILE" bdwlan/

    # 调用 Python 封装 (确保 npk.py 和 toyecc 在同级目录)
    # 如果 roswifi.py 报错，请检查 Python 环境是否安装了 ecdsa/pycryptodome
    python3 roswifi.py -i "$NPK" -b bdwlan/ -o "$FINAL_OUT"

    # 清理现场
    rm -rf bdwlan/
    
    # --- 核心逻辑结束 ---

    if [ -f "$FINAL_OUT" ]; then
        echo ">>> [成功] 已生成: $FINAL_OUT"
    else
        echo "::error::[失败] $FINAL_OUT 未能成功创建，请检查 roswifi.py 日志"
    fi
    echo "----------------------------------------------------------------"
done

echo "任务全部完成。"

#!/bin/bash

# =================================================================
# RouterOS WIFI Patch Tool (2026 通用检索版)
# 功能：全路径模糊匹配、多版本批量处理、自动消除十六进制警告
# =================================================================

usage() {
    echo "用法: $0 <MODE> <MAC_FRAGMENT> <VER_FRAGMENT1> [VER_FRAGMENT2 ...]"
    echo "示例: $0 2 A1B2 7.15 7.16"
    echo "  MODE: 1(AX5/1800), 2(AX6/3600)"
    echo "  MAC_FRAGMENT: ART文件名中包含的MAC片段 (不区分大小写)"
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

# 1. 灵活检索 ART 文件 (不再强制 mtd8_xxx_ART 格式)
# 只要文件名包含 MAC_QUERY 且以 .bin 结尾即可
BIN=$(ls art/*.bin 2>/dev/null | grep -i "${MAC_QUERY}" | head -n 1)

if [ -z "$BIN" ]; then
    echo "::error::[未找到文件] 在 art/ 目录中找不到包含 '$MAC_QUERY' 的 .bin 文件。"
    exit 1
fi

# 提取 MAC 标识用于输出文件名命名
# 逻辑：如果文件名包含下划线，提取第二段；否则直接用输入片段作为标识
FILENAME=$(basename "$BIN")
if [[ "$FILENAME" == *"_"* ]]; then
    MAC_ID=$(echo "$FILENAME" | cut -d'_' -f2)
else
    MAC_ID="$MAC_QUERY"
fi

echo ">>> [系统提示] 已锁定 ART 路径: $BIN"
echo ">>> [系统提示] 使用 MAC 标识: $MAC_ID"

# 2. 硬件参数设置 (使用 $(()) 强制转换为十进制，消除 dd 0x 警告)
case $MODE in
    1)
        OFFSET=$((0x1000))
        SIZE=$(( 64 * 1024 ))
        OUTFILE="c52_130.bdwlan"
        MODENAME="AX5"
        ;;
    2)
        OFFSET=$((0x1000))
        SIZE=$(( 128 * 1024 ))
        OUTFILE="h53_soc1_502.bdwlan"
        MODENAME="AX3600"
        ;;
    *)
        echo "::error::[模式错误] 仅支持 1 或 2。"
        exit 1
        ;;
esac

echo ">>> [系统提示] 当前设备模式: $MODENAME"
echo "----------------------------------------------------------------"

# 3. 批量处理 NPK 版本
for VER in $VER_QUERIES; do
    # 检索 NPK 文件 (忽略大小写，且匹配版本前后的分隔符)
    NPK=$(ls qcom/*.npk 2>/dev/null | grep -Ei "[-.]${VER}([-.]|$)" | head -n 1)
    
    if [ -z "$NPK" ]; then
        echo "::warning::[跳过] 版本 '$VER' 未能匹配到任何 NPK 文件。"
        continue
    fi

    ORIG_NPK_NAME=$(basename "$NPK")
    # 构造输出文件名: 模式_MAC-原始包名.npk
    FINAL_OUT="${MODENAME}_${MAC_ID}-${ORIG_NPK_NAME}"

    echo "[处理中] 版本: $VER"
    echo "  -> 输入: $ORIG_NPK_NAME"
    echo "  -> 输出: $FINAL_OUT"

    # --- 核心修补逻辑 ---
    
    # 步骤 A: 截取二进制数据 (使用十进制 OFFSET 规避警告)
    dd if="$BIN" of="$OUTFILE" skip=$OFFSET count=$SIZE iflag=skip_bytes,count_bytes status=none

    # 步骤 B: 目录准备
    mkdir -p bdwlan
    mv "$OUTFILE" bdwlan/

    # 步骤 C: 调用 Python 封装逻辑
    python3 roswifi.py -i "$NPK" -b bdwlan/ -o "$FINAL_OUT"

    # 步骤 D: 环境清理
    rm -rf bdwlan/
    
    # --- 校验结果 ---
    if [ -f "$FINAL_OUT" ]; then
        echo ">>> [成功] 已生成补丁包: $FINAL_OUT"
    else
        echo "::error::[失败] $FINAL_OUT 生成异常。"
    fi
    echo "----------------------------------------------------------------"
done

echo ">>> 所有任务执行完毕。 <<<"

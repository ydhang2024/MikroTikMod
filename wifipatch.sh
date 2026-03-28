#!/bin/bash

echo "======================================"
echo " RouterOS WIFI patch Tool"
echo "======================================"

echo
echo "选择设备模式:"
echo "1) RedMiAX5/XiaoMiAX1800"
echo "2) RedMiAX6/XiaoMiAX3600"
echo "3) 自定义"
echo

read -p "输入模式编号: " MODE

case $MODE in

1)
OFFSET="0x1000"
SIZE="64K"
OUTFILE="c52_130.bdwlan"
DEVICE="AX5/AX1800"
;;

2)
OFFSET="0x1000"
SIZE="128K"
OUTFILE="h53_soc1_502.bdwlan"
DEVICE="AX6/AX3600"
;;

3)
read -p "输入截取偏移 (支持0x): " OFFSET
read -p "输入长度 (支持K/M): " SIZE
read -p "输出文件名: " OUTFILE
DEVICE="CUSTOM"
;;

*)
echo "无效模式"
exit 1
;;

esac

echo
echo "当前模式: $DEVICE"
echo "截取偏移: $OFFSET"
echo "截取长度: $SIZE"
echo "输出文件: $OUTFILE"
echo

read -p "输入原始ART文件名(如:mtd8_0ART.bin): " BIN
read -p "输入原始wifi文件名(如:wifi-qcom-7.20.8-arm64.npk): " NPK
read -p "输出修改后wifi文件名(如:ax5_wifi-qcom-7.20.8-arm64.npk): " OUTNPK
# 单位转换函数
convert_size() {

VAL=$1

if [[ $VAL == *K || $VAL == *k ]]; then
    echo $(( ${VAL%[Kk]} * 1024 ))

elif [[ $VAL == *M || $VAL == *m ]]; then
    echo $(( ${VAL%[Mm]} * 1024 * 1024 ))

else
    echo $VAL
fi
}

SIZE=$(convert_size $SIZE)
OFFSET=$((OFFSET))

echo
echo "开始截取二进制..."

dd if="$BIN" of="$OUTFILE" skip=$OFFSET count=$SIZE iflag=skip_bytes,count_bytes status=progress

echo
echo "截取完成"

mkdir -p bdwlan

echo
echo "移动文件..."

mv "$OUTFILE" bdwlan/

echo
echo "移动到目录文件夹:"
echo "bdwlan/$OUTFILE"

echo
echo "开始调用 roswifi.py 替换bdwlan文件..."

python3 roswifi.py -i "$NPK" -b bdwlan/ -o "$OUTNPK"

echo
echo "删除bdwlan文件夹"

rm -rf bdwlan/

echo
echo "================================================================"
echo "完成，最终文件为："$OUTNPK"，请测试是否正常"
echo "================================================================"

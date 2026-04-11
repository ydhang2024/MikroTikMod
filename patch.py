import subprocess,lzma
import struct,os,re
from npk import NovaPackage,NpkPartID,NpkFileContainer

def replace_chunks(old_chunks,new_chunks,data,name):
    pattern_parts = [re.escape(chunk) + b'(.{0,6})' for chunk in old_chunks[:-1]]
    pattern_parts.append(re.escape(old_chunks[-1])) 
    pattern_bytes = b''.join(pattern_parts)
    pattern = re.compile(pattern_bytes, flags=re.DOTALL) 
    def replace_match(match):
        replaced = b''.join([new_chunks[i] + match.group(i+1) for i in range(len(new_chunks) - 1)])
        replaced += new_chunks[-1]
        print(f'{name} public key patched {b"".join(old_chunks)[:16].hex().upper()}...')
        return replaced
    return re.sub(pattern, replace_match, data)

def replace_key(old,new,data,name=''):
    old_chunks = [old[i:i+4] for i in range(0, len(old), 4)]
    new_chunks = [new[i:i+4] for i in range(0, len(new), 4)]
    data =  replace_chunks(old_chunks, new_chunks, data,name)
    key_map = [28,19,25,16,14,3,24,15,22,8,6,17,11,7,9,23,18,13,10,0,26,21,2,5,20,30,31,4,27,29,1,12,]
    old_chunks = [bytes([old[i]]) for i in key_map]
    new_chunks = [bytes([new[i]]) for i in key_map]
    data =  replace_chunks(old_chunks, new_chunks, data,name)
    arch = os.getenv('ARCH') or 'x86'
    arch = arch.replace('-', '')
    if arch in ['arm64','arm']:
        old_chunks = [old[i:i+4] for i in range(0, len(old), 4)]
        new_chunks = [new[i:i+4] for i in range(0, len(new), 4)]
        old_bytes = old_chunks[4] + old_chunks[5] + old_chunks[2] + old_chunks[0] + old_chunks[1] + old_chunks[6] + old_chunks[7]
        new_bytes = new_chunks[4] + new_chunks[5] + new_chunks[2] + new_chunks[0] + new_chunks[1] + new_chunks[6] + new_chunks[7]
        if old_bytes in data:
            print(f'{name} public key patched {old[:16].hex().upper()}...')
            data = data.replace(old_bytes,new_bytes)
            old_codes = [bytes.fromhex('793583E2'),bytes.fromhex('FD3A83E2'),bytes.fromhex('193D83E2')]  #0x1e400000+0xfd000+0x640  
            new_codes = [bytes.fromhex('FF34A0E3'),bytes.fromhex('753C83E2'),bytes.fromhex('FC3083E2')]  #0xff0075fc= 0xff000000+0x7500+0xfc
            data =  replace_chunks(old_codes, new_codes, data,name)
        else:
            def conver_chunks(data:bytes):
                ret = [
                    (data[2] << 16) | (data[1] << 8) | data[0] | ((data[3] << 24) & 0x03000000),
                    (data[3] >> 2) | (data[4] << 6) | (data[5] << 14) | ((data[6] << 22) & 0x1C00000),
                    (data[6] >> 3) | (data[7] << 5) | (data[8] << 13) | ((data[9] << 21) & 0x3E00000),
                    (data[9] >> 5) | (data[10] << 3) | (data[11] << 11) | ((data[12] << 19) & 0x1F80000),
                    (data[12] >> 6) | (data[13] << 2) | (data[14] << 10) | (data[15] << 18),
                    data[16] | (data[17] << 8) | (data[18] << 16) | ((data[19] << 24) & 0x01000000),
                    (data[19] >> 1) | (data[20] << 7) | (data[21] << 15) | ((data[22] << 23) & 0x03800000),
                    (data[22] >> 3) | (data[23] << 5) | (data[24] << 13) | ((data[25] << 21) & 0x1E00000),
                    (data[25] >> 4) | (data[26] << 4) | (data[27] << 12) | ((data[28] << 20) & 0x3F00000),
                    (data[28] >> 6) | (data[29] << 2) | (data[30] << 10) | (data[31] << 18)
                ]
                return [struct.pack('<I', x ) for x in ret]
            old_chunks = conver_chunks(old)
            new_chunks = conver_chunks(new)
            old_bytes = b''.join([v for i,v in enumerate(old_chunks) if i != 8])
            new_bytes = b''.join([v for i,v in enumerate(new_chunks) if i != 8])
            if old_bytes in data:
                print(f'{name} public key patched {old[:16].hex().upper()}...')
                data = data.replace(old_bytes,new_bytes)
                old_codes = [bytes.fromhex('713783E2'),bytes.fromhex('223A83E2'),bytes.fromhex('8D3F83E2')]  #0x1C40000+0x22000+0x234  
                new_codes = [bytes.fromhex('973303E3'),bytes.fromhex('DD3883E3'),bytes.fromhex('033483E3')]  #0x03DD3397 = 0x3397|0x00DD0000|0x03000000
                data =  replace_chunks(old_codes, new_codes, data,name)

    return data

def patch_bzimage(data: bytes, key_dict: dict):
    PE_TEXT_SECTION_OFFSET = 414
    HEADER_PAYLOAD_OFFSET = 584
    HEADER_PAYLOAD_LENGTH_OFFSET = HEADER_PAYLOAD_OFFSET + 4
    text_section_raw_data = struct.unpack_from(
        '<I', data, PE_TEXT_SECTION_OFFSET)[0]
    payload_offset = text_section_raw_data + \
        struct.unpack_from('<I', data, HEADER_PAYLOAD_OFFSET)[0]
    payload_length = struct.unpack_from(
        '<I', data, HEADER_PAYLOAD_LENGTH_OFFSET)[0]
    # last 4 bytes is uncompressed size(z_output_len)
    payload_length = payload_length - 4
    z_output_len = struct.unpack_from(
        '<I', data, payload_offset+payload_length)[0]
    vmlinux_xz = data[payload_offset:payload_offset+payload_length]
    vmlinux = lzma.decompress(vmlinux_xz)
    assert z_output_len == len(
        vmlinux), 'vmlinux size is not equal to expected'
    CPIO_HEADER_MAGIC = b'07070100'
    CPIO_FOOTER_MAGIC = b'TRAILER!!!\x00\x00\x00\x00'  # 545241494C455221212100000000
    cpio_offset1 = vmlinux.index(CPIO_HEADER_MAGIC)
    initramfs = vmlinux[cpio_offset1:]
    cpio_offset2 = initramfs.index(CPIO_FOOTER_MAGIC)+len(CPIO_FOOTER_MAGIC)
    initramfs = initramfs[:cpio_offset2]
    new_initramfs = initramfs
    for old_public_key, new_public_key in key_dict.items():
        if old_public_key in new_initramfs:
            print(f'initramfs public key patched {old_public_key[:16].hex().upper()}...')
            new_initramfs = new_initramfs.replace(
                old_public_key, new_public_key)
    new_vmlinux = vmlinux.replace(initramfs, new_initramfs)
    new_vmlinux_xz = lzma.compress(new_vmlinux, check=lzma.CHECK_CRC32, filters=[
        {"id": lzma.FILTER_X86},
        {"id": lzma.FILTER_LZMA2,
         "preset": 9 | lzma.PRESET_EXTREME,
         'dict_size': 32*1024*1024,
         "lc": 4, "lp": 0, "pb": 0,
         },
    ])
    new_payload_length = len(new_vmlinux_xz)
    assert new_payload_length <= payload_length, 'new vmlinux.xz size is too big'
    # last 4 bytes is uncompressed size(z_output_len)
    new_payload_length = new_payload_length + 4
    new_data = bytearray(data)
    struct.pack_into(
        '<I', new_data, HEADER_PAYLOAD_LENGTH_OFFSET, new_payload_length)
    vmlinux_xz += struct.pack('<I', z_output_len)
    new_vmlinux_xz += struct.pack('<I', z_output_len)
    new_vmlinux_xz = new_vmlinux_xz.ljust(len(vmlinux_xz), b'\0')
    new_data = new_data.replace(vmlinux_xz, new_vmlinux_xz)
    return new_data


def patch_block(dev:str,file:str,key_dict):
    BLOCK_SIZE = 4096
    #sudo debugfs /dev/nbd0p1 -R 'stats' | grep "Block size" | sed -n '1p' | cut -d ':' -f 2 

    #sudo debugfs /dev/nbd0p1 -R 'stat boot/initrd.rgz' 2> /dev/null | sed -n '11p'
    stdout,_ = run_shell_command(f"debugfs {dev} -R 'stat {file}' 2> /dev/null | sed -n '11p' ")
    #(0-11):1592-1603, (IND):1173, (12-15):1604-1607, (16-26):1424-1434
    blocks_info = stdout.decode().strip().split(',')
    print(f'blocks_info : {blocks_info}')
    blocks = []
    ind_block_id = None
    for block_info in blocks_info:
        _tmp = block_info.strip().split(':')
        if _tmp[0].strip() == '(IND)':
            ind_block_id =  int(_tmp[1])
        else:
            print(f'block_info : {block_info}')
            id_range = _tmp[0].strip().replace('(','').replace(')','').split('-')
            block_range = _tmp[1].strip().replace('(','').replace(')','').split('-')
            blocks += [id for id in range(int(block_range[0]),int(block_range[1])+1)]
    print(f' blocks : {len(blocks)} ind_block_id : {ind_block_id}')
    
    #sudo debugfs /dev/nbd0p1  -R 'cat boot/initrd.rgz' > data
    data,stderr = run_shell_command(f"debugfs {dev} -R 'cat {file}' 2> /dev/null")
    new_data = patch_kernel(data,key_dict)
    print(f'write block {len(blocks)} : [',end="")
    with open(dev,'wb') as f:
        for index,block_id in enumerate(blocks):
            print('#',end="")
            f.seek(block_id*BLOCK_SIZE)
            f.write(new_data[index*BLOCK_SIZE:(index+1)*BLOCK_SIZE])
        f.flush()
        print(']')


def patch_initrd_xz(initrd_xz:bytes,key_dict:dict,ljust=True):
    initrd = lzma.decompress(initrd_xz)
    new_initrd = initrd  
    
    original_size = len(initrd)
    
    for old_public_key,new_public_key in key_dict.items():
        new_initrd = replace_key(old_public_key,new_public_key,new_initrd,'initrd')
    
    new_size = len(new_initrd)
    if new_size != original_size:
        print(f'警告: 替换公钥后，initrd大小从 {original_size} 变为 {new_size}')
    
    compression_configs = [
        # (filters, check, description)
        ([{"id": lzma.FILTER_LZMA2, "preset": 6}], lzma.CHECK_CRC32, "preset=6, crc32"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 6}], lzma.CHECK_NONE, "preset=6, no check"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 7}], lzma.CHECK_CRC32, "preset=7, crc32"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 7}], lzma.CHECK_NONE, "preset=7, no check"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 8}], lzma.CHECK_CRC32, "preset=8, crc32"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 8}], lzma.CHECK_NONE, "preset=8, no check"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 9}], lzma.CHECK_CRC32, "preset=9, crc32"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 9}], lzma.CHECK_NONE, "preset=9, no check"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME, "dict_size": 2 * 1024 * 1024}], lzma.CHECK_CRC32, "extreme, 2MB dict"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME, "dict_size": 1 * 1024 * 1024}], lzma.CHECK_CRC32, "extreme, 1MB dict"),
        ([{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME, "dict_size": 512 * 1024}], lzma.CHECK_NONE, "extreme, 512KB dict, no check"),
    ]
    
    best_compressed = None
    best_size = float('inf')
    best_config_desc = ""
    
    for filters, check, desc in compression_configs:
        try:
            compressed = lzma.compress(new_initrd, check=check, filters=filters)
            if len(compressed) < best_size:
                best_size = len(compressed)
                best_compressed = compressed
                best_config_desc = desc
                print(f"最佳压缩: {desc}, 大小: {best_size}")
        except Exception as e:
            continue
    
    if best_compressed is None:
        raise Exception("所有压缩参数都失败！")
    
    new_initrd_xz = best_compressed
    print(f"最终使用: {best_config_desc}, 大小: {len(new_initrd_xz)}")
    
    if len(new_initrd_xz) > len(initrd_xz):
        print(f"警告: 压缩后大小 ({len(new_initrd_xz)}) 大于原始大小 ({len(initrd_xz)}), 差: {len(new_initrd_xz) - len(initrd_xz)} 字节")
        
        if len(new_initrd_xz) - len(initrd_xz) <= 16:
            print("尝试进一步优化压缩...")
            try:
                decompressor = lzma.LZMADecompressor()
                decompressor.decompress(initrd_xz, max_length=0)
                filters = decompressor._filters
                if filters:
                    compressed = lzma.compress(new_initrd, filters=filters)
                    if len(compressed) < best_size:
                        new_initrd_xz = compressed
                        print(f"使用原始过滤器重新压缩: {len(compressed)} 字节")
            except:
                pass
    
    if ljust:
        if len(new_initrd_xz) <= len(initrd_xz):
            new_initrd_xz = new_initrd_xz.ljust(len(initrd_xz), b'\0')
            print(f'ljust 填充: {len(initrd_xz) - len(best_compressed)} 字节')
        else:
            print(f'警告: 无法填充，新文件比原始大 {len(new_initrd_xz) - len(initrd_xz)} 字节')
    
    return new_initrd_xz


def find_7zXZ_data(data: bytes):
    offset1 = 0
    _data = data
    while b'\xFD7zXZ\x00\x00\x01' in _data:
        offset1 = offset1 + _data.index(b'\xFD7zXZ\x00\x00\x01') + 8
        _data = _data[offset1:]
    offset1 -= 8
    offset2 = 0
    _data = data
    while b'\x00\x00\x00\x00\x01\x59\x5A' in _data:
        offset2 = offset2 + _data.index(b'\x00\x00\x00\x00\x01\x59\x5A') + 7
        _data = _data[offset2:]
    print(f'found 7zXZ data offset:{offset1} size:{offset2-offset1}')
    return data[offset1:offset2]


def patch_elf(data: bytes, key_dict: dict):
    initrd_xz = find_7zXZ_data(data)
    new_initrd_xz = patch_initrd_xz(initrd_xz, key_dict)
    return data.replace(initrd_xz, new_initrd_xz)


def patch_pe(data: bytes, key_dict: dict):
    vmlinux_xz = find_7zXZ_data(data)
    vmlinux = lzma.decompress(vmlinux_xz)
    initrd_xz_offset = vmlinux.index(b'\xFD7zXZ\x00\x00\x01')
    initrd_xz_size = vmlinux[initrd_xz_offset:].index(
        b'\x00\x00\x00\x00\x01\x59\x5A') + 7
    initrd_xz = vmlinux[initrd_xz_offset:initrd_xz_offset+initrd_xz_size]
    new_initrd_xz = patch_initrd_xz(initrd_xz, key_dict)
    new_vmlinux = vmlinux.replace(initrd_xz, new_initrd_xz)
    new_vmlinux_xz = lzma.compress(new_vmlinux, check=lzma.CHECK_CRC32, filters=[
                                   {"id": lzma.FILTER_LZMA2, "preset": 9, }])
    assert len(new_vmlinux_xz) <= len(
        vmlinux_xz), 'new vmlinux xz size is too big'
    print(f'new vmlinux xz size:{len(new_vmlinux_xz)}')
    print(f'old vmlinux xz size:{len(vmlinux_xz)}')
    print(f'ljust size:{len(vmlinux_xz)-len(new_vmlinux_xz)}')
    new_vmlinux_xz = new_vmlinux_xz.ljust(len(vmlinux_xz), b'\0')
    new_data = data.replace(vmlinux_xz, new_vmlinux_xz)
    return new_data


def patch_netinstall(key_dict: dict, input_file, output_file=None):
    netinstall = open(input_file, 'rb').read()
    if netinstall[:2] == b'MZ':
        import pefile
        ROUTEROS_BOOT = {
            129: {'arch': 'power', 'name': 'Powerboot'},
            130: {'arch': 'e500', 'name': 'e500_boot'},
            131: {'arch': 'mips', 'name': 'Mips_boot'},
            135: {'arch': '400', 'name': '440__boot'},
            136: {'arch': 'tile', 'name': 'tile_boot'},
            137: {'arch': 'arm', 'name': 'ARM__boot'},
            138: {'arch': 'mmips', 'name': 'MMipsBoot'},
            139: {'arch': 'arm64', 'name': 'ARM64__boot'},
            143: {'arch': 'x86_64', 'name': 'x86_64boot'}
        }
        with pefile.PE(input_file) as pe:
            for resource in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                if resource.id == pefile.RESOURCE_TYPE["RT_RCDATA"]:
                    for sub_resource in resource.directory.entries:
                        if sub_resource.id in ROUTEROS_BOOT:
                            bootloader = ROUTEROS_BOOT[sub_resource.id]
                            print(f'found {bootloader["arch"]}({sub_resource.id}) bootloader')
                            rva = sub_resource.directory.entries[0].data.struct.OffsetToData
                            size = sub_resource.directory.entries[0].data.struct.Size
                            data = pe.get_data(rva, size)
                            _size = struct.unpack('<I', data[:4])[0]
                            _data = data[4:4+_size]
                            try:
                                if _data[:2] == b'MZ':
                                    new_data = patch_pe(_data, key_dict)
                                elif _data[:4] == b'\x7FELF':
                                    new_data = patch_elf(_data, key_dict)
                                else:
                                    raise Exception(f'unknown bootloader format {_data[:4].hex().upper()}')
                            except Exception as e:
                                print(f'patch {bootloader["arch"]}({sub_resource.id}) bootloader failed {e}')
                                new_data = _data
                            new_data = struct.pack(
                                "<I", _size) + new_data.ljust(len(_data), b'\0')
                            new_data = new_data.ljust(size, b'\0')
                            pe.set_bytes_at_rva(rva, new_data)
            pe.write(output_file or input_file)
    elif netinstall[:4] == b'\x7FELF':
        import re
        # 83 00 00 00 C4 68 C4 0B  5A C2 04 08 10 9E 52 00
        # 8A 00 00 00 C3 68 C4 0B  6A 60 57 08 C0 3D 54 00
        # 81 00 00 00 D3 68 C4 0B  2A 9E AB 08 5C 1B 78 00
        # 82 00 00 00 E8 6B C4 0B  86 B9 23 09 78 01 82 00
        # 87 00 00 00 ED 6B C4 0B  FE BA A5 09 44 BF 7B 00
        # 89 00 00 00 0C 6A C4 0B  42 7A 21 0A C4 1D 3E 00
        # 8B 00 00 00 1E 69 C4 0B  06 98 5F 0A 28 95 5E 00
        # 8C 00 00 00 F1 6B C4 0B  2E 2D BE 0A 78 EA 5D 00
        # 88 00 00 00 03 69 C4 0B  A6 17 1C 0B 28 55 4A 00
        # 8F 00 00 00 FC 6B C4 0B  CE 6C 66 0B E0 E8 58 00
        SECTION_HEADER_OFFSET_IN_FILE = struct.unpack_from(
            b'<I', netinstall[0x20:])[0]
        SECTION_HEADER_ENTRY_SIZE = struct.unpack_from(
            b'<H', netinstall[0x2E:])[0]
        NUMBER_OF_SECTION_HEADER_ENTRIES = struct.unpack_from(
            b'<H', netinstall[0x30:])[0]
        STRING_TABLE_INDEX = struct.unpack_from(b'<H', netinstall[0x32:])[0]
        section_name_offset = SECTION_HEADER_OFFSET_IN_FILE + \
            STRING_TABLE_INDEX * SECTION_HEADER_ENTRY_SIZE + 16
        SECTION_NAME_BLOCK = struct.unpack_from(
            b'<I', netinstall[section_name_offset:])[0]
        for i in range(NUMBER_OF_SECTION_HEADER_ENTRIES):
            section_offset = SECTION_HEADER_OFFSET_IN_FILE + i * SECTION_HEADER_ENTRY_SIZE
            name_offset, _, _, addr, offset = struct.unpack_from(
                '<IIIII', netinstall[section_offset:])
            name = netinstall[SECTION_NAME_BLOCK+name_offset:].split(b'\0')[0]
            if name == b'.text':
                print(f'found .text section at {hex(offset)} addr {hex(addr)}')
                text_section_addr = addr
                text_section_offset = offset
                break
        offset = re.search(
            rb'\x83\x00\x00\x00.{12}\x8A\x00\x00\x00.{12}\x81\x00\x00\x00.{12}', netinstall).start()
        print(f'found bootloaders offset {hex(offset)}')
        for i in range(10):
            id, name_ptr, data_ptr, data_size = struct.unpack_from(
                '<IIII', netinstall[offset+i*16:offset+i*16+16])
            name = netinstall[text_section_offset +
                              name_ptr-text_section_addr:].split(b'\0')[0]
            data = netinstall[text_section_offset+data_ptr -
                              text_section_addr:text_section_offset+data_ptr-text_section_addr+data_size]
            print(f'found {name.decode()}({id}) bootloader offset {hex(text_section_offset+data_ptr-text_section_addr)} size {data_size}')
            try:
                if data[:2] == b'MZ':
                    new_data = patch_pe(data, key_dict)
                elif data[:4] == b'\x7FELF':
                    new_data = patch_elf(data, key_dict)
                else:
                    raise Exception(f'unknown bootloader format {data[:4].hex().upper()}')
            except Exception as e:
                print(f'patch {name.decode()}({id}) bootloader failed {e}')
                new_data = data
            new_data = new_data.ljust(len(data), b'\0')
            netinstall = netinstall.replace(data, new_data)
        open(output_file or input_file, 'wb').write(netinstall)


def patch_kernel(data: bytes, key_dict):
    if data[:2] == b'MZ':
        print('patching EFI Kernel')
        if data[56:60] == b'ARM\x64':
            print('patching arm64')
            return patch_elf(data, key_dict)
        else:
            print('patching x86_64')
            return patch_bzimage(data, key_dict)
    elif data[:4] == b'\x7FELF':
        print('patching ELF')
        return patch_elf(data, key_dict)
    elif data[:5] == b'\xFD7zXZ':
        print('patching initrd')
        return patch_initrd_xz(data, key_dict)
    else:
        raise Exception('unknown kernel format')


#def patch_squashfs(path, key_dict):
#    for root, dirs, files in os.walk(path):
#        for file in files:
#            file = os.path.join(root, file)
#            if os.path.isfile(file):
#                data = open(file, 'rb').read()
#                for old_public_key, new_public_key in key_dict.items():
#                    if old_public_key in data:
#                        print(f'{file} public key patched {old_public_key[:16].hex().upper()}...')
#                        data = data.replace(old_public_key, new_public_key)
#                        open(file, 'wb').write(data)

def patch_squashfs(path, key_dict):
    # 安全获取环境变量
    mikro_url = os.getenv('MIKRO_UPGRADE_URL')
    custom_url = os.getenv('CUSTOM_UPGRADE_URL')

    for root, dirs, files in os.walk(path):
        for _file in files:
            file_path = os.path.join(root, _file)
            if os.path.isfile(file_path):
                # 1. 读取文件
                data = open(file_path, 'rb').read()
                original_data = data

                # 2. 替换公钥逻辑 (保持你原有的逻辑)
                for old_public_key, new_public_key in key_dict.items():
                    data = replace_key(old_public_key, new_public_key, data, file_path)

                # 3. 新增：替换 MIKRO_UPGRADE_URL 的逻辑
                is_ppp_worker = file_path.replace('\\', '/').endswith('bndl/ppp/nova/bin/ppp')
                
                # 如果配置了环境变量，且该文件【不是】ppp-worker，才进行替换
                if mikro_url and custom_url and not is_ppp_worker:
                    mikro_url_bytes = mikro_url.encode()
                    custom_url_bytes = custom_url.encode()
                    if mikro_url_bytes in data:
                        print(f'{file_path} upgrade url patched: {mikro_url} -> {custom_url}')
                        # (强烈建议在这里使用等长填充 \x00 的逻辑，防止文件损坏)
                        data = data.replace(mikro_url_bytes, custom_url_bytes)

                # 4. 如果内容有变动，才写回文件
                if data != original_data:
                    open(file_path, 'wb').write(data)

def run_shell_command(command):
    process = subprocess.run(
        command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process.stdout, process.stderr


def patch_npk_package(package, key_dict):
    if package[NpkPartID.NAME_INFO].data.name == 'system':
        file_container = NpkFileContainer.unserialize_from(
            package[NpkPartID.FILE_CONTAINER].data)
        for item in file_container:
            if item.name in [b'boot/EFI/BOOT/BOOTX64.EFI', b'boot/kernel', b'boot/initrd.rgz']:
                print(f'patch {item.name} ...')
                item.data = patch_kernel(item.data, key_dict)
        package[NpkPartID.FILE_CONTAINER].data = file_container.serialize()
        squashfs_file = 'squashfs-root.sfs'
        extract_dir = 'squashfs-root'
        open(squashfs_file, 'wb').write(package[NpkPartID.SQUASHFS].data)
        print(f"extract {squashfs_file} ...")
        run_shell_command(f"unsquashfs -d {extract_dir} {squashfs_file}")
        patch_squashfs(extract_dir, key_dict)
        logo_path = os.path.join(extract_dir, "nova/lib/console/logo.txt")
        if os.path.exists(logo_path):
            print(f"Cleaning logo identifiers in {logo_path}...")
            # 删除包含 github.com 或 elseif 关键字的行
            run_shell_command(f"sed -i '/github.com/d' {logo_path}")
            run_shell_command(f"sed -i '/elseif/d' {logo_path}")
        print(f"pack {extract_dir} ...")
        run_shell_command(f"rm -f {squashfs_file}")
        run_shell_command(f"mksquashfs {extract_dir} {squashfs_file} -quiet -comp xz -no-xattrs -b 512k")
        print(f"clean ...")
        run_shell_command(f"rm -rf {extract_dir}")
        package[NpkPartID.SQUASHFS].data = open(squashfs_file, 'rb').read()
        run_shell_command(f"rm -f {squashfs_file}")


def patch_npk_file(key_dict, kcdsa_private_key, eddsa_private_key, input_file, output_file=None):
    npk = NovaPackage.load(input_file)
    if len(npk._packages) > 0:
        for package in npk._packages:
            patch_npk_package(package, key_dict)
    else:
        patch_npk_package(npk, key_dict)
    npk.sign(kcdsa_private_key, eddsa_private_key)
    npk.save(output_file or input_file)


if __name__ == '__main__':
    import argparse
    import os
    parser = argparse.ArgumentParser(description='MikroTik patcher')
    subparsers = parser.add_subparsers(dest="command")
    npk_parser = subparsers.add_parser('npk', help='patch and sign npk file')
    npk_parser.add_argument('input', type=str, help='Input file')
    npk_parser.add_argument('-O', '--output', type=str, help='Output file')
    kernel_parser = subparsers.add_parser('kernel', help='patch kernel file')
    kernel_parser.add_argument('input', type=str, help='Input file')
    kernel_parser.add_argument('-O', '--output', type=str, help='Output file')
    block_parser = subparsers.add_parser('block', help='patch block file')
    block_parser.add_argument('dev', type=str, help='block device')
    block_parser.add_argument('file', type=str, help='file path')
    netinstall_parser = subparsers.add_parser(
        'netinstall', help='patch netinstall file')
    netinstall_parser.add_argument('input', type=str, help='Input file')
    netinstall_parser.add_argument(
        '-O', '--output', type=str, help='Output file')
    args = parser.parse_args()
    key_dict = {
        bytes.fromhex(os.environ['MIKRO_LICENSE_PUBLIC_KEY']): bytes.fromhex(os.environ['CUSTOM_LICENSE_PUBLIC_KEY']),
        bytes.fromhex(os.environ['MIKRO_NPK_SIGN_PUBLIC_KEY']): bytes.fromhex(os.environ['CUSTOM_NPK_SIGN_PUBLIC_KEY'])
    }
    kcdsa_private_key = bytes.fromhex(os.environ['CUSTOM_LICENSE_PRIVATE_KEY'])
    eddsa_private_key = bytes.fromhex(
        os.environ['CUSTOM_NPK_SIGN_PRIVATE_KEY'])
    if args.command == 'npk':
        print(f'patching {args.input} ...')
        patch_npk_file(key_dict, kcdsa_private_key,
                       eddsa_private_key, args.input, args.output)
    elif args.command == 'kernel':
        print(f'patching {args.input} ...')
        data = patch_kernel(open(args.input, 'rb').read(), key_dict)
        open(args.output or args.input, 'wb').write(data)
    elif args.command == 'block':
        print(f'patching {args.file} in {args.dev} ...')
        patch_block(args.dev, args.file, key_dict)
    elif args.command == 'netinstall':
        print(f'patching {args.input} ...')
        patch_netinstall(key_dict, args.input, args.output)
    else:
        parser.print_help()

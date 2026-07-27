import zlib

def krc_to_lrc(krc_file_path):
    """
    将KRC歌词文件转换为LRC格式
    :param krc_file_path: KRC文件路径
    :return: LRC格式的字符串
    """
    # kg加密密钥（与 krc_decrypt.KRC_ENCRYPT_KEY 一致）
    encrypt_key = [64, 71, 97, 119, 94, 50, 116, 71, 81, 54, 49, 45, 206, 210, 110, 105]

    try:
        with open(krc_file_path, 'rb') as f:
            krc_data = f.read()

        encrypted_content = krc_data[4:]
        decrypted_bytes = bytes(encrypted_content[i] ^ encrypt_key[i % 16]
                               for i in range(len(encrypted_content)))
        decompressed_data = zlib.decompress(decrypted_bytes)
        krc_text = decompressed_data.decode('utf-8')

        lrc_lines = []
        for line in krc_text.split('\n'):
            line = line.strip()
            if not line or not line.startswith('[') or ',' not in line:
                continue
            time_part = line[1:].split(']')[0]
            if ',' in time_part:
                start_ms = int(time_part.split(',')[0])
                minutes = start_ms // 60000
                seconds = (start_ms % 60000) / 1000.0
                time_tag = f"[{minutes:02d}:{seconds:06.3f}]".replace('.', ':')
                lyric_text = extract_lyric_text(line)
                if lyric_text:
                    lrc_lines.append(f"{time_tag}{lyric_text}")

        return '\n'.join(lrc_lines)

    except Exception as e:
        return f"转换失败: {str(e)}"

def extract_lyric_text(krc_line):
    """
    从KRC行中提取纯歌词文本
    """
    import re
    text_part = krc_line.split(']', 1)[1] if ']' in krc_line else krc_line
    clean_text = re.sub(r'<\d+,\d+,\d+>', '', text_part)
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    return clean_text.strip()

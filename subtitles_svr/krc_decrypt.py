import base64
import json
import logging
import re
import requests
import zlib

from .config import get_config
from .subtitle_struct import SubstitleWord, SubstitleLine
from typing import Union, List

logger = logging.getLogger(__name__)

# KRC 文件解密密钥（算法常量，非环境相关配置）
KRC_ENCRYPT_KEY = [64, 71, 97, 119, 94, 50, 116, 71, 81, 54, 49, 45, 206, 210, 110, 105]


class KrcDecrypt:
    def __init__(self, krc_file_path_or_encrypted_bytes: Union[str, bytes]):
        '''解密KRC文件'''
        try:
            krc_data = None
            if isinstance(krc_file_path_or_encrypted_bytes, str):
                with open(krc_file_path_or_encrypted_bytes, 'rb') as f:
                    krc_data = f.read()
            elif isinstance(krc_file_path_or_encrypted_bytes, bytes):
                krc_data = krc_file_path_or_encrypted_bytes
            encrypted_content = krc_data[4:]
            decrypted_bytes = bytes(encrypted_content[i] ^ KRC_ENCRYPT_KEY[i % 16] for i in range(len(encrypted_content)))
            decompressed_data = zlib.decompress(decrypted_bytes)
            self.krc_text = decompressed_data.decode('utf-8')
        except Exception as e:
            raise Exception(f"KRC文件解密失败: {str(e)}")

    def parse_krc_content(self, offset_ms: int = 0) -> List[SubstitleLine]:
        '''解析KRC内容'''
        lines = []
        is_first = True
        for line in self.krc_text.split('\n'):
            line = line.strip()
            if not line or not line.startswith('[') or ',' not in line:
                continue
            time_match = re.search(r'\[(\d+),(\d+)\]', line)
            if not time_match:
                continue
            start_time = int(time_match.group(1))
            duration = int(time_match.group(2))
            text_part = line.split(']', 1)[1] if ']' in line else line
            clean_text = re.sub(r'<\d+,\d+,\d+>', '', text_part)
            clean_text = re.sub(r'<[^>]+>', '', clean_text).strip()
            word_matches = re.findall(r'<(\d+),(\d+),\d+>([^<]+)', line)
            words = []
            for start_offset, word_duration, word_text in word_matches:
                word_start = start_time + int(start_offset)
                words.append(SubstitleWord(word_start, int(word_duration), word_text))
            if clean_text:
                is_first = not is_first
                lines.append(SubstitleLine(start_time, duration, words, clean_text))
        if offset_ms > 0:
            for l in lines:
                l.start_time += offset_ms
                for w in l.words:
                    w.start_time += offset_ms
        return lines


class KrcDownload:
    @staticmethod
    def process_keyword(text: Union[str, List[str]]) -> List[str]:
        res_list = []
        if isinstance(text, List):
            res_list = text
        else:
            cleaned = re.sub(r'[^a-zA-Z\u4e00-\u9fa5]', ' ', text)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            keyword_list = cleaned.split(' ')
            for word in keyword_list:
                if len(word) <= 0:
                    continue
                res_list.append(word)
        return res_list

    def __init__(self, keyword: str):
        self.keywords = KrcDownload.process_keyword(keyword)

    def search_and_download(self) -> bytes:
        bytes_list = self.search_and_download_mulit(max_krcs=1)
        return bytes_list[0] if bytes_list is not None and len(bytes_list) > 0 else None

    def search_and_download_mulit(self, max_krcs: int = 1) -> List[bytes]:
        try:
            cfg = get_config().kugou
            default_headers = {"User-Agent": cfg.user_agent}
            logger.info('start search_and_download_mulit {}'.format(self.keywords))
            search_resp = requests.get(
                cfg.search_url.format(' '.join(self.keywords)),
                headers=default_headers, timeout=cfg.timeout)
            search_res = json.loads(search_resp.content)
            if 'data' not in search_res or 'info' not in search_res['data']:
                return None
            search_res_list = search_res['data']['info']
            if len(search_res_list) <= 0 or 'sqhash' not in search_res_list[0]:
                return None
            krc_search_resp = requests.get(
                cfg.krc_search_url.format(search_res_list[0]['sqhash']),
                headers=default_headers, timeout=cfg.timeout)
            krc_search_res = json.loads(krc_search_resp.content)
            if 'candidates' not in krc_search_res or len(krc_search_res['candidates']) <= 0:
                return None
            download_list = []
            for i in range(min(max_krcs, len(krc_search_res['candidates']))):
                krc_info = krc_search_res['candidates'][i]
                krc_download_resp = requests.get(
                    cfg.krc_download_url.format(krc_info['id'], krc_info['accesskey']),
                    headers=default_headers, timeout=cfg.timeout)
                krc_download_res = json.loads(krc_download_resp.content)
                if 'content' not in krc_download_res:
                    continue
                download_list.append(base64.b64decode(krc_download_res['content']))
            logger.info('end search_and_download_mulit {} {}'.format(len(download_list), self.keywords))
            return download_list
        except Exception as e:
            return None

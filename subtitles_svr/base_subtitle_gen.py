import re
import platform
import os

from abc import ABC, abstractmethod
from opencc import OpenCC
from pathlib import Path
from .config import get_config
from .subtitle_struct import SubstitleData
from typing import List

class BaseSubtitleGen(ABC):
    @staticmethod
    def gen_keyword(text: str) -> List[str]:
        simple_cn_text = OpenCC('tw2s').convert(text)
        cleaned = re.sub(r'[^a-zA-Z\u4e00-\u9fa5]', ' ', simple_cn_text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        keyword_list = cleaned.split(' ')
        res_list = []
        for word in keyword_list:
            if len(word) <= 0:
                continue
            res_list.append(word)
        return res_list

    @staticmethod
    def ignore_index_key(key_list: List[str]):
        need_ignore_index_key = {'accompaniment', 'vocals'}
        if key_list is not None:
            while True:
                if len(key_list) >= 2 and key_list[-1] in need_ignore_index_key:
                    key_list.pop()
                else:
                    break
            return True
        return False

    @staticmethod
    def get_next_filename(folder, prefix, suffix):
        i = 0
        full_path = os.path.join(folder, '{}{}{}'.format(prefix, '.' + str(i) if i > 0 else '', suffix))
        while os.path.isfile(full_path):
            full_path = os.path.join(folder, '{}{}{}'.format(prefix, '.' + str(i) if i > 0 else '', suffix))
            i += 1
        return full_path

    @staticmethod
    def write_with_mkdir(path: str, mode, encoding: str = 'utf-8'):
        if mode in {"w", "wt", "tw", "a", "at", "ta", "x", "xt", "tx"}:
            file = Path(path)
            file.parent.mkdir(parents=True, exist_ok=True)
        return open(path, mode, encoding=encoding)

    @abstractmethod
    def __init__(self, src_filepath: str, file_extension: str, out_dir: str, max_item: int = 1):
        super().__init__()
        if platform.system() == "Linux":
            self.src_filepath = src_filepath.replace('\\', '/')
            cfg = get_config().paths
            self.src_filepath = self.src_filepath.replace(cfg.remote_prefix, cfg.local_prefix)
        else:
            self.src_filepath = src_filepath
        self.file_extension = file_extension
        self.out_dir = out_dir
        self.max_item = max_item
        self.input_file_stem, self.input_file_suffix = os.path.splitext(os.path.basename(self.src_filepath))
        if len(file_extension) <= 0 and len(self.input_file_suffix) > 1:
            file_extension = self.input_file_suffix[1:]
        if self.input_file_suffix != '.' + file_extension:
            self.input_file_stem = os.path.basename(self.src_filepath)
            self.input_file_suffix = '.' + file_extension

    @abstractmethod
    def need_skip(self) -> bool:
        return False

    @abstractmethod
    def get_index_key(self) -> List[str]:
        pass

    @abstractmethod
    def subtitles_gen(self) -> List[SubstitleData]:
        pass

import logging

from .base_subtitle_gen import BaseSubtitleGen
from .krc_decrypt import KrcDecrypt, KrcDownload
from .subtitle_struct import SubstitleData
from typing import List

logger = logging.getLogger(__name__)

class SubtitleFromKugou(BaseSubtitleGen):
    def __init__(self, src_filepath: str, file_extension: str, out_dir: str, max_item: int = 1):
        super().__init__(src_filepath, file_extension, out_dir, max_item)

    def need_skip(self) -> bool:
        return self.input_file_suffix not in {'.mp3', '.flac', '.ape', '.wav', '.vob'}

    def get_index_key(self) -> List[str]:
        key_list = BaseSubtitleGen.gen_keyword(self.input_file_stem)
        BaseSubtitleGen.ignore_index_key(key_list)
        return key_list

    def subtitles_gen(self) -> List[SubstitleData]:
        krc_down = KrcDownload(self.get_index_key())
        krc_bytes_list = krc_down.search_and_download_mulit(max_krcs=self.max_item)
        subs_list = []
        if krc_bytes_list is not None:
            for krc_bytes in krc_bytes_list:
                if krc_bytes is not None and len(krc_bytes) > 0:
                    krc = KrcDecrypt(krc_bytes)
                    name = '-'.join(self.get_index_key())
                    subs_list.append(SubstitleData(name, krc.parse_krc_content()))
                    logger.info('Download Dat SaveTo {} '.format(name))
        return subs_list

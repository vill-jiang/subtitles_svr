import logging
import os

from .ass_gen import AssGen
from .base_subtitle_gen import BaseSubtitleGen
from .config import get_config
from .krc_decrypt import KrcDecrypt, KrcDownload
from .my_cue_parse import MyCueTrack, MyCueParser
from .subtitle_struct import SubstitleData, SubstitleLine
from concurrent.futures import ThreadPoolExecutor
from typing import List

logger = logging.getLogger(__name__)

class SubtitleFromCue(BaseSubtitleGen):
    def __init__(self, src_filepath: str, file_extension: str, out_dir: str, max_item: int = 1):
        super().__init__(src_filepath, file_extension, out_dir, max_item)
        self.cue_filepath = self.src_filepath[:-len(self.input_file_suffix)] + '.cue'

    def need_skip(self) -> bool:
        return not os.path.isfile(self.cue_filepath)

    def get_index_key(self) -> List[str]:
        key_list = BaseSubtitleGen.gen_keyword(self.input_file_stem) + ['cue']
        BaseSubtitleGen.ignore_index_key(key_list)
        return key_list

    @staticmethod
    def cue_time_to_ms(time_str: str) -> int:
        if time_str is None:
            return None
        try:
            parts = time_str.strip().split(":")
            if len(parts) != 3:
                return None
            minutes = int(parts[0])
            seconds = int(parts[1])
            frames = int(parts[2])
            total_ms = round((minutes * 60000) + (seconds * 1000) + ((frames * 1000) / 75))
            return total_ms
        except (ValueError, IndexError) as e:
            return None

    @staticmethod
    def download_krc_lines(music_stem_tuple) -> List[List[SubstitleLine]]:
        performer, title, offset_ms, max_item = music_stem_tuple
        logger.info('download_krc_lines {}'.format(music_stem_tuple))
        krc_down = KrcDownload(performer + ' ' + title)
        krc_bytes_list = krc_down.search_and_download_mulit(max_item)
        if krc_bytes_list is None:
            return []
        krc_line_list = []
        for krc_bytes in krc_bytes_list:
            if krc_bytes is not None and len(krc_bytes) > 0:
                krc = KrcDecrypt(krc_bytes)
                krc_lines = krc.parse_krc_content(offset_ms)
                if krc_lines is not None and len(krc_lines) > 0:
                    krc_line_list.append(krc_lines)
        return krc_line_list

    def subtitles_gen(self) -> List[SubstitleData]:
        if self.need_skip():
            return []
        cue_parser = MyCueParser()
        cue_parser.parse_file(self.cue_filepath)
        music_stem_list = []
        for music in cue_parser.get_performer_track_list():
            music_stem_list.append((music.performer or '', music.title, music.offset_ms, self.max_item))
        logger.info('Download CueDat Start {} {}'.format(self.cue_filepath, music_stem_list))
        cue_line_list = []
        with ThreadPoolExecutor(max_workers=get_config().subtitle.cue_max_workers) as executor:
            results = executor.map(SubtitleFromCue.download_krc_lines, music_stem_list)
            for line_list in results:
                i = 0
                for lines in line_list:
                    while len(cue_line_list) <= i:
                        cue_line_list.append([])
                    cue_line_list[i].extend(lines)
                    i += 1
        if len(cue_line_list) <= 0:
            logger.info('Download CueDat Empty')
            return []
        sub_dat_list = []
        i = 0
        for cue_lines in cue_line_list:
            name = '{}{}'.format('-'.join(self.get_index_key()), ('.' + str(i)) if i > 0 else '')
            sub_dat_list.append(SubstitleData(name, cue_lines))
            logger.info('Download CueDat SaveTo {} '.format(name))
            i += 1
        return sub_dat_list

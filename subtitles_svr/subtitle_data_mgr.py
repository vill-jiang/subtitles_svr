import json
import logging
import os

from .ass_gen import AssGen
from .base_subtitle_gen import BaseSubtitleGen
from .config import get_config
from .file_index import FileIndexDatabase
from .lrc_gen import LrcGen
from .subtitle_from_cue import SubtitleFromCue
from .subtitle_from_kugou import SubtitleFromKugou
from .subtitle_struct import SubstitleData
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SEARCH_GEN_LIST: List[BaseSubtitleGen] = [
    SubtitleFromCue, SubtitleFromKugou
]

class SubtitleDbData(object):
    def __init__(self,
                 dat_id: int,
                 title: Optional[str],
                 file_name: Optional[str],
                 format: Optional[str],
                 lang: Optional[str],
                 data: Optional[bytes]):
        self.dat_id = dat_id
        self.title = title
        self.file_name = file_name
        self.format = format
        self.lang = lang
        self.data = data

    def to_dict(self) -> dict:
        return {
            'dat_id': self.dat_id,
            'title': self.title,
            'file_name': self.file_name,
            'format': self.format,
            'lang': self.lang,
            'data': self.data,
        }

class SubtitleDataMgr(object):
    def __init__(self, index_dir: str = None):
        self._index_dir = index_dir or get_config().paths.index_dir
        # 检查并创建 self._index_dir 目录
        os.makedirs(self._index_dir, exist_ok=True)
        self.index_db_path = os.path.join(self._index_dir, 'index.db')
        self._index_db = FileIndexDatabase(self.index_db_path)

    @staticmethod
    def db_dict_to_struct(raw_db_data: Optional[Dict], file_id: int = None) -> Optional[SubtitleDbData]:
        if raw_db_data is not None:
            return SubtitleDbData(
                file_id if file_id is not None else raw_db_data.get('id', 0),
                raw_db_data.get('title', ''),
                raw_db_data.get('file_name', ''),
                raw_db_data.get('format', ''),
                raw_db_data.get('lang', ''),
                raw_db_data.get('data', None)
            )
        return None

    def find(self, keywords: List[str]) -> List[SubtitleDbData]:
        id_list = self._index_db.get_ids_by_keywords(keywords, True)
        return [SubtitleDataMgr.db_dict_to_struct(self._index_db.get_file_by_id(i), i) for i in id_list]

    def search(self, file_path: str, file_extension: str = '', max_item: int = None, dis_generate: bool = False) -> List[SubtitleDbData]:
        global SEARCH_GEN_LIST
        if max_item is None:
            max_item = get_config().subtitle.default_max_item
        cfg = get_config().subtitle
        index_key = []
        id_list = []
        for gen_class in SEARCH_GEN_LIST:
            gen_obj = gen_class(file_path, file_extension, self._index_dir, max_item=max_item)
            if gen_obj.need_skip():
                continue
            index_key = gen_obj.get_index_key()
            cur_id_list = self._index_db.get_ids_by_keywords(index_key, True)
            logger.info('get_index_key {} {}'.format(index_key, cur_id_list))
            if len(cur_id_list) > 0:
                id_list.extend(cur_id_list)
                break
            if dis_generate:
                continue
            gen_dat_list = gen_obj.subtitles_gen()
            logger.info('subtitles_gen {}'.format(len(gen_dat_list)))
            for gen_dat in gen_dat_list:
                new_id = self._index_db.insert_file(
                    gen_dat.name,
                    None,
                    cfg.default_format,
                    cfg.default_lang,
                    index_key,
                    gen_dat.dumps()
                )
                id_list.append(new_id)
            if len(gen_dat_list) > 0:
                break
        search_obj_list = []
        for i in range(len(id_list)):
            sub_id = id_list[i]
            file_dict = self._index_db.get_file_by_id(sub_id, False)
            if file_dict is not None:
                search_obj_list.append(
                    SubtitleDbData(
                        sub_id,
                        file_dict.get('title', '-'.join(index_key)),
                        file_dict.get('file_name', ''),
                        file_dict.get('format', ''),
                        file_dict.get('lang', ''),
                        None
                    )
                )
        return search_obj_list

    def download(self, file_id: int, file_format: str) -> str:
        file_dict = self._index_db.get_file_by_id(file_id, True)
        if file_dict is not None:
            bin_data = file_dict.get('data', b'')
            sub_data = SubstitleData()
            sub_data.loads(bin_data)
            if file_format == 'lrc' or file_format == 'elrc':
                lrc_gen = LrcGen(sub_data.name, file_format == 'elrc')
                return lrc_gen.generate_substitle(sub_data.lines)
            elif file_format == 'json':
                return json.dumps(sub_data.to_dict(), ensure_ascii=False)
            else:
                ass_gen = AssGen()
                return ass_gen.generate_substitle(sub_data.name, sub_data.lines, True, True)
        return ''

    def delete(self, id_list: List[int]) -> int:
        return self._index_db.delete_file(id_list)

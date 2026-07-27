import json
import re
import logging

from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class MyCueTrack:
    def __init__(self, performer: str, title: str, offset_ms: int):
        self.performer = performer
        self.title = title
        self.offset_ms = offset_ms
    def __repr__(self):
        return '{} {} {}'.format(self.performer, self.title, self.offset_ms)

class MyCueParser:
    @staticmethod
    def cue_time_to_ms(time_str: str) -> int:
        if time_str is None:
            return None
        try:
            parts = time_str.strip().split(':')
            if len(parts) != 3:
                return None
            minutes = int(parts[0])
            seconds = int(parts[1])
            frames = int(parts[2])
            total_ms = round((minutes * 60000) + (seconds * 1000) + ((frames * 1000) / 75))
            return total_ms
        except (ValueError, IndexError) as e:
            return None

    '''简单的CUE文件解析器，将CUE文件转My换为JSON结构（支持编码自适应）'''
    def __init__(self):
        self.cue_data: Dict = {
            'file': {},
            'tracks': []
        }
        self.current_track: Optional[Dict] = None
        self.current_file: Optional[Dict] = None

    def _clean_line(self, line: str) -> str:
        line = re.sub(r'//.*$', '', line)
        return line.strip()

    def _parse_line(self, line: str) -> None:
        if not line:
            return
        parts = re.findall(r'"[^"]*"|\S+', line)
        if not parts:
            return
        command = str(parts[0]).upper()
        args = parts[1:]
        if command == 'CATALOG':
            self.cue_data['catalog'] = args[0] if args else None
        elif command == 'TITLE':
            title = ' '.join(args).strip('"')
            if self.current_track:
                self.current_track['title'] = title
            else:
                self.cue_data['disc_title'] = title
        elif command == 'PERFORMER':
            performer = ' '.join(args).strip('"')
            if self.current_track:
                self.current_track['performer'] = performer
            else:
                self.cue_data['disc_performer'] = performer
        elif command == 'FILE':
            if len(args) >= 2:
                file_name = ' '.join(args[:-1]).strip('"')
                file_type = args[-1]
                if len(self.cue_data['file']) <= 0:
                    self.cue_data['file']['name'] = file_name
                    self.cue_data['file']['type'] = file_type
                else:
                    self.current_file = {
                        'name': file_name,
                        'type': file_type,
                    }
        elif command == 'TRACK':
            if len(args) >= 2:
                if self.current_track and self.current_track not in self.cue_data['tracks']:
                    self.cue_data['tracks'].append(self.current_track)
                self.current_track = {
                    'number': args[0],
                    'type': args[1],
                    'indexes': []
                }
        elif command == 'INDEX':
            if self.current_track and len(args) >= 2:
                index_info = {
                    'number': args[0],
                    'time': args[1]
                }
                try:
                    index_info['number_int'] = int(args[0])
                except:
                    pass
                try:
                    index_info['time_ms'] = MyCueParser.cue_time_to_ms(args[1])
                except:
                    pass
                if self.current_file:
                    index_info['file'] = self.current_file
                self.current_track['indexes'].append(index_info)
        if command != 'FILE':
            self.current_file = None

    def _auto_detect_encoding(self, file_path: str) -> Tuple[str, str]:
        common_encodings = ['gbk', 'utf-8-sig', 'utf-8', 'gb2312', 'big5', 'utf-16-le']
        try:
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
        except FileNotFoundError:
            raise FileNotFoundError('CUE not found: {}'.format(file_path))
        for encoding in common_encodings:
            try:
                file_content = file_bytes.decode(encoding)
                core_keywords = ['FILE', 'TRACK', 'TITLE', 'INDEX']
                if any(keyword in file_content.upper() for keyword in core_keywords):
                    return file_content, encoding
            except (UnicodeDecodeError, LookupError):
                continue
        raise Exception('cannot detect codec {}'.format(file_path))

    def parse_file(self, cue_file_path: str) -> Dict:
        try:
            file_content, encoding = self._auto_detect_encoding(cue_file_path)
            logging.info('codec {}'.format(encoding))
            for line in file_content.splitlines():
                clean_line = self._clean_line(line)
                self._parse_line(clean_line)
            if self.current_track and self.current_track not in self.cue_data['tracks']:
                self.cue_data['tracks'].append(self.current_track)
            return self.cue_data
        except Exception as e:
            raise Exception('parce CUE failed {} {}'.format(cue_file_path, str(e)))

    def get_performer_track_list(self, try_simple_chinese: bool = True) -> List[MyCueTrack]:
        if 'tracks' in self.cue_data:
            track_list = []
            for track in self.cue_data['tracks']:
                performer = track.get('performer', None) or self.cue_data.get('disc_performer', '')
                title = track.get('title', None) or self.cue_data.get('disc_title', '')
                offset_ms = 0
                if 'indexes' in track and len(track['indexes']) > 0:
                    for index_item in track['indexes']:
                        indexe_ms = index_item.get('time_ms', None) or 0
                        if indexe_ms > offset_ms:
                            offset_ms = indexe_ms
                else:
                    continue
                if try_simple_chinese:
                    from opencc import OpenCC
                    performer = OpenCC('tw2s').convert(performer)
                    title = OpenCC('tw2s').convert(title)
                track_list.append(MyCueTrack(performer, title, offset_ms))
            return track_list
        return []

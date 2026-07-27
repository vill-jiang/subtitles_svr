import pickle
import lz4.frame

from typing import List

class SubstitleWord:
    '''表示一个字'''
    def __init__(self, start_time: int, duration: int, text: str):
        self.start_time = start_time  # 开始时间（毫秒）
        self.duration = duration      # 持续时间（毫秒）
        self.text = text              # 文字内容
        self.width = 0  # 初始化宽度为0
    def __repr__(self):
        return '{} {} {}'.format(self.start_time, self.duration, self.text)

    def to_dict(self) -> dict:
        return {
            'start_time': self.start_time,
            'duration': self.duration,
            'text': self.text,
            'width': self.width,
        }

class SubstitleLine:
    '''表示一行'''
    def __init__(self, start_time: int, duration: int, words: List[SubstitleWord], text: str):
        self.start_time = start_time
        self.duration = duration
        self.words = words
        self.text = text
    def __repr__(self):
        return '{} {} {} [{}]'.format(self.start_time, self.duration, self.text, self.words)

    def to_dict(self) -> dict:
        return {
            'start_time': self.start_time,
            'duration': self.duration,
            'text': self.text,
            'words': [w.to_dict() for w in self.words],
        }

class SubstitleData:
    '''表示一个字幕文件'''
    def __init__(self, name: str = '', lines: List[SubstitleWord] = []):
        self.name = name
        self.lines = lines
    def __repr__(self):
        return '{} {} {}'.format(self.name, self.lines)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'lines': [l.to_dict() for l in self.lines],
        }

    def dumps(self) -> bytes:
        return lz4.frame.compress(pickle.dumps(self))

    def loads(self, dat: bytes):
        new_obj = pickle.loads(lz4.frame.decompress(dat))
        self.name = new_obj.name
        self.lines = new_obj.lines

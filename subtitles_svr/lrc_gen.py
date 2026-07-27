from .subtitle_struct import SubstitleWord, SubstitleLine
from typing import List

class LrcGen:
    def __init__(self, name: str, use_elrc: bool = False):
        self.name = name
        self.use_elrc = use_elrc

    def generate_header(self) -> str:
        return '''[ti:{}]
[by:subtitle_svr]
[offset:0]

'''.format(self.name)

    @staticmethod
    def ms_to_lrc_time(ms) -> str:
        minutes = int(ms // 60000)
        seconds = (ms % 60000) // 1000
        milliseconds = (ms % 1000) // 10  # 保留2位毫秒（LRC标准）
        return '{:02d}:{:02d}.{:02d}'.format(minutes, seconds, milliseconds)

    @staticmethod
    def word_list_to_elrc(word_list: List[SubstitleWord], diff_ms: int = 0) -> str:
        elrc_w_str = []
        for w in word_list:
            t = w.text.replace(' ', '')
            if len(t) > 0:
                elrc_w_str.append('<{}>{}'.format(LrcGen.ms_to_lrc_time(diff_ms + w.start_time), t))
        return ''.join(elrc_w_str)

    def generate_substitle(self, lines: List[SubstitleLine]) -> str:
        lrc_header = self.generate_header()
        events = []
        for i in range(len(lines)):
            current_line = lines[i]
            base_line = '[{}]'.format(LrcGen.ms_to_lrc_time(current_line.start_time))
            if self.use_elrc:
                base_line += LrcGen.word_list_to_elrc(current_line.words)
            else:
                base_line += ''.join([w.text for w in current_line.words])
            events.append(base_line)
        return lrc_header + '\n'.join(events)

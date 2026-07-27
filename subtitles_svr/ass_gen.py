import os
DISABLE_PIL = False
try:
    from PIL import ImageFont, ImageDraw, Image
except Exception:
    DISABLE_PIL = True
from .config import get_config
from .subtitle_struct import SubstitleWord, SubstitleLine
from typing import List

# ASS 文件头注释前缀（格式标记，非环境配置）
ASS_COMMENT_PREFIX = '; FromFile-'
ASS_COMMENT_PREFIX_OLD_LIST = [ASS_COMMENT_PREFIX, '; FromKrc-']


class AssGen:
    @staticmethod
    def ms_to_ass_time(ms):
        total_seconds = ms / 1000.0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60
        return '{}:{:02d}:{:05.2f}'.format(hours, minutes, seconds)

    @staticmethod
    def word_fmt(d: int, w: str) -> str:
        d = round(d / 10)  # \K单位是0.1秒
        return '{{\\K{}}}{}'.format(d, w)

    @staticmethod
    def read_ass_comment(ass_path):
        with open(ass_path, 'r', encoding='utf-8-sig') as fp:
            i = 0
            for l in fp.readlines():
                if l is None or len(l) <= 0 or i > 2:
                    break
                l = l.strip()
                for prefix in ASS_COMMENT_PREFIX_OLD_LIST:
                    if l.startswith(prefix):
                        return l.removeprefix(prefix)
                i += 1
        return ''

    def __init__(self):
        cfg = get_config().ass
        self.font_name = cfg.font_name
        self.font_size = cfg.font_size
        self.primary_colour = cfg.primary_colour
        self.secondary_colour = cfg.secondary_colour
        self.outline_colour = cfg.outline_colour
        self.back_colour = cfg.back_colour
        self.video_width = cfg.video_width
        self.video_height = cfg.video_height
        self.margin_lr = cfg.margin_lr
        self.margin_v_up = cfg.margin_v_up
        self.margin_v_bottom = cfg.margin_v_bottom
        self.margin_safe = cfg.margin_safe
        self.tip_tri_cond_ms = cfg.tip_tri_cond_ms
        self.tip_tri_remain_ms = cfg.tip_tri_remain_ms
        self.tip_tri_ms = cfg.tip_tri_ms
        if not DISABLE_PIL:
            self.pil_font = ImageFont.truetype(self.font_name, self.font_size)
            self.temp_img = Image.new('1', (1, 1), 1)
            self.draw = ImageDraw.Draw(self.temp_img)
        self.word_length = {}

    def generate_header(self, comment: str) -> str:
        font_style = '{},{},{},{},{},{}'.format(
            self.font_name, self.font_size, self.primary_colour,
            self.secondary_colour, self.outline_colour, self.back_colour)
        ass_header = '''[Script Info]
{}{}
ScriptType: v4.00+
PlayResX: {}
PlayResY: {}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Line1,{},0,0,0,0,100,100,0,0,1,2,2,1,{},{},{},1
Style: Line2,{},0,0,0,0,100,100,0,0,1,2,2,3,{},{},{},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''.format(ASS_COMMENT_PREFIX, comment, self.video_width, self.video_height,
           font_style, self.margin_lr, self.margin_lr, self.margin_v_up,
           font_style, self.margin_lr, self.margin_lr, self.margin_v_bottom)
        return ass_header

    def generate_substitle(self, comment: str, ass_lines: List[SubstitleLine], use_ktv_tip=False, use_roll=False) -> str:
        ass_header = self.generate_header(comment)
        events = []
        is_first = True
        last_end = 0
        last_2_end = 0
        for i in range(len(ass_lines)):
            current_line = ass_lines[i]
            if len(current_line.words) <= 0:
                continue
            current_end_time = current_line.start_time + current_line.duration
            current_start_time = min(last_2_end, current_line.start_time)
            karaoke_text = ''
            lead_duration = 0
            has_long_interval = (current_line.start_time > last_2_end + self.tip_tri_cond_ms + self.tip_tri_ms and
                                 current_line.start_time > last_end + self.tip_tri_cond_ms)
            if not is_first and has_long_interval:
                is_first = not is_first
                last_2_end = last_end + self.tip_tri_remain_ms
                last_end = last_end + self.tip_tri_remain_ms
                current_start_time = last_2_end
            if current_line.start_time > last_2_end:
                if use_ktv_tip and has_long_interval and current_line.start_time > last_2_end + self.tip_tri_ms:
                    karaoke_text += AssGen.word_fmt(current_line.start_time - last_2_end - self.tip_tri_ms, ' ')
                    karaoke_text += AssGen.word_fmt(self.tip_tri_ms, '▶')
                else:
                    karaoke_text += AssGen.word_fmt(current_line.start_time - last_2_end, ' ')
                lead_duration += (current_line.start_time - last_2_end)
            for word in current_line.words:
                karaoke_text += AssGen.word_fmt(word.duration, word.text)
            roll_cmd = ''
            if use_roll and len(current_line.words) > 3:
                show_width = self.video_width - (self.margin_lr * 2) - self.margin_safe
                sum_width = 0
                for word in current_line.words:
                    if word.width == 0:
                        if word.text not in self.word_length:
                            self.word_length[word.text] = self.calculate_ass_text_width(word.text)
                        word.width = self.word_length[word.text]
                    sum_width += word.width
                if sum_width >= show_width:
                    end_x = min(show_width - sum_width + self.margin_lr, self.margin_safe)
                    roll_start_time = lead_duration
                    roll_end_time = lead_duration
                    acc_width = 0
                    for j in range(len(current_line.words)):
                        word = current_line.words[j]
                        if acc_width < show_width and acc_width + word.width >= show_width:
                            roll_start_time += sum(w.duration for w in current_line.words[:max(0, j - 2)])
                            roll_end_time += sum(w.duration for w in current_line.words[:max(j - 1, len(current_line.words) - 2)])
                            break
                        acc_width += word.width
                    line_y = (self.video_height - (self.margin_v_up if is_first else self.margin_v_bottom))
                    roll_cmd = '{{ \\q2 \\an1 \\move({},{},{},{},{},{}) }}'.format(
                        self.margin_lr, line_y, end_x, line_y, roll_start_time, roll_end_time)
            events.append(
                'Dialogue: {},{},{},{},,0,0,0,,{}{}'.format(
                    '1' if is_first else '0',
                    AssGen.ms_to_ass_time(current_start_time),
                    AssGen.ms_to_ass_time(current_end_time),
                    'Line1' if is_first else 'Line2',
                    roll_cmd,
                    karaoke_text)
            )
            is_first = not is_first
            last_2_end = last_end
            last_end = current_end_time
        return ass_header + '\n'.join(events)

    def calculate_ass_text_width(self, text) -> int:
        if not DISABLE_PIL:
            bbox = self.draw.textbbox((0, 0), text, font=self.pil_font, spacing=0)
            return round(bbox[2] - bbox[0])
        else:
            width = 0.0
            for char in text:
                if '\u4e00' <= char <= '\u9fff':
                    width += self.font_size
                elif char.isalpha():
                    width += self.font_size / 2.0
                else:
                    width += self.font_size
            return round(width)

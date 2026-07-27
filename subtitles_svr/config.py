"""应用配置：从 config.yaml 加载。

原先写死在代码里的域名、端口、远程路径、kg接口、User-Agent、超时、
索引目录、默认语言/格式以及 ASS 样式参数，统一在此以 dataclass 描述默认值，
并由 YAML 文件覆盖。
"""
import os
from dataclasses import dataclass, field, fields
from typing import List, Optional

import yaml

# 默认配置文件路径：项目根目录下的 config.yaml
# config.py 位于 <root>/subtitles_svr/config.py
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
)


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8085


@dataclass
class WatchConfig:
    # 文件监听为可选功能：留空（None 或空字符串）表示不开启监听。
    windows_folder: Optional[str] = None
    linux_folder: Optional[str] = None
    ignore_suffixes: List[str] = field(default_factory=lambda: [".!qB"])
    poll_timeout: int = 10


@dataclass
class PathConfig:
    index_dir: str = "subtitles"
    # 跨平台路径映射：Linux 下把远程前缀替换为本地挂载路径（示例占位符，按需修改）
    remote_prefix: str = "//<remote-host>/<share>"
    local_prefix: str = "/<local-mount>"


@dataclass
class KugouConfig:
    # 以下地址均为敏感信息，请勿提交真实地址；部署时务必在 config.yaml 中替换为实际地址。
    search_url: str = "http://<kugou-search-host>/api/v3/search/song?pagesize=10&tagtype=%E5%85%A8%E9%83%A8&keyword={}"
    krc_search_url: str = "https://<kugou-krc-host>/search?ver=1&man=yes&client=mobi&hash={}"
    krc_download_url: str = "https://<kugou-lyrics-host>/download?ver=1&client=pc&id={}&accesskey={}&fmt=krc&charset=utf8"
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    timeout: int = 3


@dataclass
class SubtitleConfig:
    default_lang: str = "zh-CN"
    default_format: str = "raw"
    default_max_item: int = 2
    cue_max_workers: int = 15


@dataclass
class AssStyleConfig:
    font_name: str = "simhei"
    font_size: int = 44
    primary_colour: str = "&H08FF9232"
    secondary_colour: str = "&H00FFFFFF"
    outline_colour: str = "&H00303030"
    back_colour: str = "&H80000000"
    video_width: int = 1000
    video_height: int = 720
    margin_lr: int = 60
    margin_v_up: int = 100
    margin_v_bottom: int = 50
    margin_safe: int = 26
    tip_tri_cond_ms: int = 6000
    tip_tri_remain_ms: int = 2000
    tip_tri_ms: int = 3000


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    watch: WatchConfig = field(default_factory=WatchConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    kugou: KugouConfig = field(default_factory=KugouConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)
    ass: AssStyleConfig = field(default_factory=AssStyleConfig)


def _merge_config(obj, data: dict) -> None:
    """用 YAML 字典递归覆盖 dataclass 的默认值。"""
    for f in fields(obj):
        if f.name in data and data[f.name] is not None:
            val = data[f.name]
            current = getattr(obj, f.name)
            if hasattr(current, "__dataclass_fields__"):
                _merge_config(current, val)
            else:
                setattr(obj, f.name, val)


_config: Optional[AppConfig] = None


def load_config(path: Optional[str] = None) -> AppConfig:
    """加载配置；path 为空时依次尝试环境变量 SUBTITLE_SVR_CONFIG 与默认路径。"""
    global _config
    cfg_path = path or os.environ.get("SUBTITLE_SVR_CONFIG", DEFAULT_CONFIG_PATH)
    cfg = AppConfig()
    if cfg_path and os.path.isfile(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _merge_config(cfg, data)
    _config = cfg
    return cfg


def get_config() -> AppConfig:
    """获取全局配置（懒加载，未显式加载时返回默认/文件配置）。"""
    global _config
    if _config is None:
        return load_config()
    return _config

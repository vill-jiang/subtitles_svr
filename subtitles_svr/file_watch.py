import logging
import os
import platform

from .config import get_config
from .subtitle_data_mgr import SubtitleDataMgr
from typing import Iterable
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

logger = logging.getLogger(__name__)

class AutoSearchFileWatch(object):
    class ChangeHandler(FileSystemEventHandler):
        def set_mgr_obj(self, mgr_obj: SubtitleDataMgr):
            self._mgr_obj = mgr_obj

        def set_ignore(self, file_set: Iterable[str], file_suffix: Iterable[str]):
            self.file_set = {os.path.abspath(f) for f in file_set}
            if self._mgr_obj is not None:
                for f in [self._mgr_obj.index_db_path, self._mgr_obj.index_db_path + '-journal']:
                    self.file_set.add(os.path.abspath(f))
            self.file_suffix = {f.lower() if f.startswith('.') else '.' + f.lower() for f in file_suffix}
            logger.info(f'set_ignore: {self.file_set} {self.file_suffix}')

        def is_ignore(self, src_path: str):
            if self.file_set is not None:
                src_abs_path = os.path.abspath(src_path)
                if src_abs_path in self.file_set:
                    return True
            if self.file_suffix is not None:
                _, suffix = os.path.splitext(src_path)
                if suffix.lower() in self.file_suffix:
                    return True
            return False

        def on_created_or_moved(self, file_path: str):
            if self.is_ignore(file_path):
                logger.debug(f'ignore {file_path}')
                return
            logger.info('on_created_or_moved {}'.format(file_path))
            _, file_extension = os.path.splitext(file_path)
            if len(file_extension) >= 1 and file_extension[0] == '.':
                file_extension = file_extension[1:]
            db_data_list = self._mgr_obj.search(os.path.abspath(file_path), file_extension,
                                                get_config().subtitle.default_max_item, False)
            for db_data in db_data_list:
                logger.info('on_created_or_moved search {}'.format(db_data.to_dict()))

        def on_created(self, event):
            if event.is_directory:
                return
            self.on_created_or_moved(event.src_path)

        def on_moved(self, event):
            if event.is_directory:
                return
            self.on_created_or_moved(event.dest_path)

    def __init__(self, watch_folder: str, mgr_obj: SubtitleDataMgr = None, ignore_file_set: set = {}):
        self.watch_folder = watch_folder
        self._event_handler = AutoSearchFileWatch.ChangeHandler()
        if mgr_obj is None:
            self._event_handler.set_mgr_obj(SubtitleDataMgr())
            logger.info(f'create new SubtitleDataMgr')
        else:
            self._event_handler.set_mgr_obj(mgr_obj)
        self.ignore_file_set = ignore_file_set
        cfg = get_config().watch
        self._event_handler.set_ignore(ignore_file_set, cfg.ignore_suffixes)
        if platform.system() == "Windows":
            self._observer = PollingObserver(timeout=cfg.poll_timeout)
        else:
            self._observer = Observer()
        # 设为守护线程：主线程退出（如 Ctrl+C）时进程即可终止，
        # 否则 watchdog 的非守护后台线程会让程序关不掉、端口一直被占用。
        self._observer.daemon = True
        self._observer.schedule(self._event_handler, self.watch_folder, recursive=True)
        self._observer.start()

    def stop_and_join(self):
        self._observer.stop()
        self._observer.join()

"""歌词字幕 HTTP 服务：搜索 / 下载 / 删除 接口，并监听目录自动生成字幕。"""
import argparse
import json
import logging
import platform
import signal
import sys
import time

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote

from .config import get_config, load_config
from .file_watch import AutoSearchFileWatch
from .subtitle_data_mgr import SubtitleDataMgr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EXIT_FLAG = False
SUBTITLE_DATA_MGR = None
AUTO_SEARCH_FILE_WATCH = None


def get_params_first_val(params: dict, key: str, default=None):
    if key in params:
        val = params[key]
        if isinstance(val, list) and len(val) > 0:
            return val[0]
        return val
    return default


def search_handler(params: dict) -> str:
    global SUBTITLE_DATA_MGR
    file_path = get_params_first_val(params, 'filename', '')
    if file_path == '':
        return json.dumps({'status': -1, 'error': 'filename empty'}, ensure_ascii=False)
    cfg = get_config().subtitle
    try:
        max_item = int(get_params_first_val(params, 'max_item', cfg.default_max_item))
    except (TypeError, ValueError):
        max_item = cfg.default_max_item
    file_extension = get_params_first_val(params, 'meta_fileExtension', '')
    db_data_list = SUBTITLE_DATA_MGR.search(file_path, file_extension, max_item)
    search_resp_map = {'status': 0, 'sub': {'subs': []}}
    for i in range(len(db_data_list)):
        dat = db_data_list[i]
        search_resp_map['sub']['subs'].append({
            'id': dat.dat_id,
            'native_name': dat.title + ('.' + str(i) if len(db_data_list) > 1 else ''),
            'fileName': dat.file_name,
            'title': dat.title,
            'format': dat.format,
            'url': '/download?id={}'.format(dat.dat_id),
            'lang': dat.lang,
        })
    return json.dumps(search_resp_map, ensure_ascii=False)


def download_handler(params: dict) -> str:
    global SUBTITLE_DATA_MGR
    file_id = get_params_first_val(params, 'id', '0')
    file_format = get_params_first_val(params, 'format', '0')
    int_id = 0
    try:
        int_id = int(file_id)
    except Exception:
        return ''
    return SUBTITLE_DATA_MGR.download(int_id, file_format)


def delete_handler(params: dict) -> str:
    global SUBTITLE_DATA_MGR
    keys = get_params_first_val(params, 'keys', '')
    double_check = get_params_first_val(params, 'double_check', '')
    index_key = keys.split('-')
    data_list = SUBTITLE_DATA_MGR.find(index_key)
    delete_rol = 0
    if double_check == 'yes':
        delete_rol = SUBTITLE_DATA_MGR.delete([d.dat_id for d in data_list])
    return json.dumps({'data_list': [d.to_dict() for d in data_list], 'delete_rol': delete_rol}, ensure_ascii=False)


PATH_HANDLER = {
    '/search': search_handler,
    '/download': download_handler,
    '/delete': delete_handler,
}


class GetParamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        url_path = str(parsed_url.path)
        if url_path not in PATH_HANDLER:
            self.send_response(404)
            self.end_headers()
            return
        start = time.perf_counter()
        params = parse_qs(parsed_url.query)
        txt_content = PATH_HANDLER[url_path](params)
        if txt_content is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write('{}'.encode('utf-8'))
            return
        self.send_response(200)
        self.send_header('Content-type', 'text/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(txt_content.encode('utf-8'))
        elapsed = time.perf_counter() - start
        logger.info('elapsed {:.6f}s\n{}\nresponse:\n{}'.format(
            elapsed, unquote(self.path),
            txt_content if txt_content.startswith('{') else txt_content[:100] + '...'))


def handle_exit_signal(signum, frame):
    global AUTO_SEARCH_FILE_WATCH
    if AUTO_SEARCH_FILE_WATCH is not None:
        AUTO_SEARCH_FILE_WATCH.stop_and_join()
    sys.exit(0)


def run_server(host: str, port: int, watch_folder: str, mgr: SubtitleDataMgr):
    global SUBTITLE_DATA_MGR, AUTO_SEARCH_FILE_WATCH
    SUBTITLE_DATA_MGR = mgr
    if watch_folder:
        AUTO_SEARCH_FILE_WATCH = AutoSearchFileWatch(watch_folder, mgr)
    signal.signal(signal.SIGTERM, handle_exit_signal)
    signal.signal(signal.SIGINT, handle_exit_signal)
    server_address = (host, port)
    httpd = HTTPServer(server_address, GetParamHandler)
    logger.info("服务器已启动，监听 {}:{} ...".format(host, port))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        if AUTO_SEARCH_FILE_WATCH is not None:
            AUTO_SEARCH_FILE_WATCH.stop_and_join()
        logger.info("\n正在关闭...")
        httpd.server_close()
        logger.info("服务器已关闭")


def main():
    parser = argparse.ArgumentParser(description="歌词字幕搜索与 ASS 生成服务")
    parser.add_argument("--config", default=None, help="YAML 配置文件路径")
    parser.add_argument("--host", default=None, help="监听地址（覆盖配置）")
    parser.add_argument("--port", type=int, default=None, help="监听端口（覆盖配置）")
    args = parser.parse_args()

    config = load_config(args.config)
    host = args.host or config.server.host
    port = args.port or config.server.port
    watch_folder = (config.watch.windows_folder
                    if platform.system() == "Windows" else config.watch.linux_folder) or None
    mgr = SubtitleDataMgr(index_dir=config.paths.index_dir)

    logger.info("使用配置: host=%s port=%s watch=%s index=%s",
                host, port, watch_folder or "(未开启监听)", config.paths.index_dir)
    run_server(host, port, watch_folder, mgr)


if __name__ == '__main__':
    main()

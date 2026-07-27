import json
import logging
import sqlite3
import time

from typing import Dict, List, Optional, Any, Union, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class FileIndexDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._check_and_create_tables()

    @contextmanager
    def _get_cursor(self):
        '''获取数据库游标的上下文管理器'''
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def _check_and_create_tables(self):
        '''检查并创建必要的表'''
        with self._get_cursor() as cursor:
            cursor.execute('SELECT name FROM sqlite_master WHERE type=\'table\'')
            existing_tables = {row[0] for row in cursor.fetchall()}
            required_tables = {'metadata', 'files', 'keywords', 'file_keywords'}
            if not required_tables.issubset(existing_tables):
                logger.info('缺少必要的表，正在创建表结构...')
                self._create_tables(cursor)

    def _create_tables(self, cursor):
        cursor.execute('''CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    int_value INTEGER,
    str_value TEXT
) WITHOUT ROWID''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    title TEXT,
    file_name TEXT,
    format TEXT,
    lang TEXT,
    data BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_title ON files(title)')
        cursor.execute('''CREATE TABLE IF NOT EXISTS keywords (
    keyword TEXT PRIMARY KEY
) WITHOUT ROWID''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS file_keywords (
    file_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    PRIMARY KEY (file_id, keyword),
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    FOREIGN KEY (keyword) REFERENCES keywords(keyword) ON DELETE CASCADE
) WITHOUT ROWID''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_keywords_keyword ON file_keywords(keyword)')
        cursor.execute('INSERT OR IGNORE INTO metadata (key, int_value, str_value) VALUES (\'ver\', 0, NULL)')
        logger.info('数据库表创建完成')

    def _get_table_schema(self) -> Dict[str, str]:
        with self._get_cursor() as cursor:
            cursor.execute('SELECT name, sql FROM sqlite_master WHERE type=\'table\'')
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_metadata(self) -> Dict[str, Tuple[int, str]]:
        with self._get_cursor() as cursor:
            cursor.execute('SELECT * FROM metadata')
            return {row['key']: (row['int_value'], row['str_value']) for row in cursor.fetchall()}

    def get_file_by_id(self, file_id: int, need_data: bool = False) -> Optional[Dict]:
        with self._get_cursor() as cursor:
            fields_str = 'id,title,file_name,format,lang'
            if need_data:
                fields_str += ',data'
            cursor.execute("SELECT {} FROM files WHERE id = ?".format(fields_str), (file_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_ids_by_keywords(self, keywords: List[str], match_all: bool = True) -> List[int]:
        if not keywords or len(keywords) == 0:
            return []
        with self._get_cursor() as cursor:
            placeholders = ''
            if len(keywords) == 1:
                placeholders = 'fk.keyword = ?'
            else:
                placeholders = 'fk.keyword IN ({})'.format(','.join(['?'] * len(keywords)))
            if match_all:
                cursor.execute(f'''SELECT fk.file_id FROM file_keywords fk WHERE {placeholders} GROUP BY fk.file_id HAVING COUNT(fk.keyword) = ?''', keywords + [len(keywords)])
            else:
                cursor.execute(f'SELECT DISTINCT fk.file_id FROM file_keywords fk WHERE {placeholders}', keywords)
            return [row['file_id'] for row in cursor.fetchall()]

    def get_files_by_keywords(self, keywords: List[str], match_all: bool = True) -> List[Dict]:
        if not keywords:
            return []
        with self._get_cursor() as cursor:
            placeholders = ''
            if len(keywords) == 1:
                placeholders = 'fk.keyword = ?'
            else:
                placeholders = 'fk.keyword IN ({})'.format(','.join(['?'] * len(keywords)))
            if match_all:
                cursor.execute(f'''SELECT f.* FROM files f WHERE f.id IN ( SELECT fk.file_id FROM file_keywords fk WHERE {placeholders} GROUP BY fk.file_id HAVING COUNT(fk.keyword) = ?)''', keywords + [len(keywords)])
            else:
                cursor.execute(f'SELECT DISTINCT f.* FROM files f JOIN file_keywords fk ON f.id = fk.file_id WHERE {placeholders}', keywords)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def insert_file_with_cursor(cursor: sqlite3.Cursor, title: str, file_name: str, format: str, lang: str, keywords: Union[str, List[str]], dat_bin: bytes) -> int:
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split('-') if k.strip()]
        cursor.execute('''INSERT INTO files (title,file_name,format,lang,data) VALUES (?,?,?,?,?)''', (title, file_name, format, lang, sqlite3.Binary(dat_bin)))
        new_id = cursor.lastrowid
        for keyword in keywords:
            cursor.execute("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (keyword,))
            cursor.execute(
                "INSERT OR IGNORE INTO file_keywords (file_id,keyword) VALUES (?,?)",
                (new_id, keyword)
            )
        return new_id

    @staticmethod
    def delete_file_with_cursor(cursor: sqlite3.Cursor, file_id: int) -> int:
        cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
        cursor.execute("DELETE FROM file_keywords WHERE file_id = ?", (file_id,))
        return cursor.rowcount

    def insert_file(self, title: str, file_name: str, format: str, lang: str, keywords: Union[str, List[str]], dat_bin: bytes) -> int:
        with self._get_cursor() as cursor:
            return FileIndexDatabase.insert_file_with_cursor(cursor, title, file_name, format, lang, keywords, dat_bin)

    def delete_file(self, id_or_list: Union[int, List[int]]) -> int:
        if isinstance(id_or_list, int):
            id_or_list = [id_or_list]
        with self._get_cursor() as cursor:
            rowcount = 0
            for i in id_or_list:
                rowcount += FileIndexDatabase.delete_file_with_cursor(cursor, i)
            return rowcount

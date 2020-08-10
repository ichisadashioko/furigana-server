#!/usr/bin/env python3
# encoding=utf-8
import os
import re
import time
import shutil
import posixpath
import mimetypes
import html
import io
import email.utils
import datetime
import json
from typing import List

import http
from http.server import BaseHTTPRequestHandler, HTTPServer

import urllib
import urllib.parse


g_hostname = '0.0.0.0'
g_server_port = 8080

g_script_dir, script_filename = os.path.split(__file__)
if len(g_script_dir) == 0:
    g_script_dir = '.'

g_served_directory = g_script_dir

if not mimetypes.inited:
    mimetypes.init()  # try to read system mime.tyeps

g_extensions_map = mimetypes.types_map.copy()
g_extensions_map.update({
    '': 'application/octet-stream',  # default
    # '.html': 'text/html',
    # '.htm': 'text/html',
    # '.css': 'text/css',
    # TODO flag to enable or disable ES module
    '.js': 'application/javascript',
    '.py': 'text/plain',
    '.c': 'text/plain',
    '.h': 'text/plain',
    '.tsv': 'text/plain',
})

# dlt -> directory listing template
g_dlt_filepath = os.path.join(
    g_script_dir,
    'statics',
    'directory-listing-template.html',
)

if not os.path.exists(g_dlt_filepath):
    raise Exception((
        f'-> {g_dlt_filepath}\n'
        f'Directory listing template does not exist!'
    ))

g_dlt = open(
    g_dlt_filepath,
    mode='r',
    encoding='utf-8',
).read()

g_dlt_displayname_placeholder = r'{%displayname%}'

if not g_dlt_displayname_placeholder in g_dlt:
    raise Exception((
        f'-> {g_dlt_filepath}\n'
        f'Directory listing template does not contain displayname placeholder string ({g_dlt_displayname_placeholder})!'
    ))

g_dlt_body_placeholder = r'{%body%}'

if not g_dlt_body_placeholder in g_dlt:
    raise Exception((
        f'-> {g_dlt_filepath}\n'
        f'Directory listing template does not contain displayname placeholder string ({g_dlt_body_placeholder})!'
    ))


class FuriganaRecord:
    HEADERS = ['word', 'furigana', 'meaning', 'note', 'ruby']

    @classmethod
    def headers_to_tsv(cls):
        cells = map(lambda cell: FuriganaRecord.escape(cell), cls.HEADERS)
        return '\t'.join(cells)

    def __init__(self):
        self.word = ''
        self.furigana = ''
        self.ruby = ''
        self.note = ''
        self.meaning = ''

    def to_dict(self):
        return {
            'word': self.word,
            'furigana': self.furigana,
            'meaning': self.meaning,
            'note': self.note,
            'ruby': self.ruby,
        }

    @staticmethod
    def escape(s: str):
        s = s.replace('\t', '\\t')
        s = s.replace('\n', '\\n')
        return s

    @staticmethod
    def unescape(s: str):
        s = s.replace('\\t', '\t')
        s = s.replace('\\n', '\n')
        return s

    def to_list(self):
        return [self.word, self.furigana, self.meaning, self.note, self.ruby]

    def to_tsv_row(self):
        cells = self.to_list()
        cells = map(lambda cell: self.escape(cell), cells)
        return '\t'.join(cells)

    def __repr__(self):
        return repr(self.to_dict())


g_furigana_database: List[FuriganaRecord] = []
g_tsv_filepath = os.path.join(g_script_dir, 'database.tsv')

if not os.path.exists(g_tsv_filepath):
    open(g_tsv_filepath, mode='w', encoding='utf-8').write(FuriganaRecord.headers_to_tsv() + '\n')

tsv_lines = open(g_tsv_filepath, mode='r', encoding='utf-8').readlines()
tsv_lines = map(lambda line: line.replace('\n', ''), tsv_lines)
# filter empty lines
tsv_lines = filter(lambda line: len(line) > 0, tsv_lines)

tsv_lines: List[str] = list(tsv_lines)
num_tsv_lines = len(tsv_lines)

if num_tsv_lines == 0:
    # empty file
    open(g_tsv_filepath, mode='w', encoding='utf-8').write(FuriganaRecord.headers_to_tsv() + '\n')
else:
    # check headers
    first_line = tsv_lines[0]
    print('first_line:', repr(first_line))

    header_line = FuriganaRecord.headers_to_tsv()
    if header_line == first_line:
        max_num_cols = len(FuriganaRecord.HEADERS)
        row_idx = 1
        while row_idx < num_tsv_lines:
            line = tsv_lines[row_idx]
            cells = line.split('\t')

            if len(cells) > max_num_cols:
                print(line)
                raise Exception(f'The TSV file is not compatible with the current code!')
            else:
                while len(cells) < max_num_cols:
                    cells.append('')

            record = FuriganaRecord()
            record.word = FuriganaRecord.unescape(cells[0])
            record.furigana = FuriganaRecord.unescape(cells[1])
            record.meaning = FuriganaRecord.unescape(cells[2])
            record.note = FuriganaRecord.unescape(cells[3])
            record.ruby = FuriganaRecord.unescape(cells[4])

            g_furigana_database.append(record)

            row_idx += 1
    else:
        raise Exception(f'The TSV file is not compatible with the current code!')


class FuriganaServer(BaseHTTPRequestHandler):

    def translate_path(self, path: str):
        words = path.split('/')
        words = filter(None, words)
        words = filter(lambda word: len(word) > 0, words)
        # decode every path components because there might be some
        # spaces or some hash characters in the file name but those
        # characters are not able to represent as they are in the url
        # components
        words = map(lambda word: urllib.parse.unquote(word), words)

        path = '/'
        local_path = g_served_directory

        for word in words:
            if os.path.dirname(word) or (word in (os.curdir, os.pardir)):
                # ignore components that are not simple file/directory name
                continue

            path = posixpath.join(path, word)
            local_path = os.path.join(local_path, word)

        return path, local_path

    def list_directory(self, displayname: str, local_path: str):
        try:
            file_list = os.listdir(local_path)
        except OSError:
            self.send_error(http.HTTPStatus.NOT_FOUND, 'No permission to list directory!')
            return None

        # TODO options to sort by name, creation date, or last modified date

        # TODO learn about how quote=False will affect us
        encoded_displayname = html.escape(displayname, quote=False)
        document = g_dlt.replace(g_dlt_displayname_placeholder, encoded_displayname)

        body = []
        body.append(f'<h1>Directory listing for {encoded_displayname}</h1>')
        body.append(f'<hr>')
        body.append(f'<ul>')

        for child_filename in file_list:
            child_filepath = os.path.join(local_path, child_filename)
            child_displayname = linkname = child_filename
            # append / for directories or @ for symbalic links
            if os.path.isdir(child_filepath):
                child_displayname = child_filename + '/'
                linkname = child_filename + '/'
            if os.path.islink(child_filepath):
                child_displayname = child_filename + '@'

            quoted_linkname = urllib.parse.quote(linkname, errors='surrogatepass')
            html_encoded_child_displayname = html.escape(child_displayname, quote=False)
            body.append(f'<li><a href="{quoted_linkname}">{html_encoded_child_displayname}</a></li>')

        body.append(f'</ul>')
        body = '\n'.join(body)
        document = document.replace(g_dlt_body_placeholder, body)

        encoded_document = document.encode('utf-8', 'surrogateescape')
        f = io.BytesIO()
        f.write(encoded_document)
        f.seek(0)
        self.send_response(http.HTTPStatus.OK)
        self.send_header('Content-Type', 'text/html; charset=UTF-8')
        self.send_header('Content-Length', str(len(encoded_document)))
        self.end_headers()
        return f

    def send_head(self):
        parts = urllib.parse.urlsplit(self.path)
        path, local_path = self.translate_path(parts.path)

        query_dict = urllib.parse.parse_qs(parts.query, keep_blank_values=True)

        f = None
        if os.path.isdir(local_path):
            if not parts.path.endswith('/'):
                self.send_response(http.HTTPStatus.MOVED_PERMANENTLY)
                new_parts = (parts[0], parts[1], parts[2] + '/', parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header('Location', new_url)
                self.end_headers()
                return None

            # if there is a query parameter named 'listdir' then force directory listing instead of seeking for index document
            if 'listdir' in query_dict:
                return self.list_directory(displayname=path, local_path=local_path)
            else:
                for index in ('index.html', 'index.htm'):
                    index = os.path.join(local_path, index)
                    if os.path.exists(index):
                        local_path = index
                        break
                else:
                    return self.list_directory(displayname=path, local_path=local_path)

        # if the execution reaches here then that means we have to send a file
        if not os.path.exists(local_path):
            self.send_error(http.HTTPStatus.NOT_FOUND, 'File not found!')
            return None

        # TODO check extension and send Content-Type in headers
        ctype = self.guess_type(local_path)
        f = open(local_path, 'rb')
        try:
            fs = os.fstat(f.fileno())
            # use browser cache if possible
            if ('If-Modified-Since' in self.headers) and ('If-None-Match' not in self.headers):
                # compare If-Modified-Since and time of the last file modification
                try:
                    ims = email.utils.parsedate_to_datetime(self.headers['If-Modified-Since'])
                except (TypeError, IndexError, OverflowError, ValueError):
                    # ignore ill-formed values
                    pass
                else:
                    if ims.tzinfo is None:
                        # obsolete format with no timezone, cf
                        # https://tools.ietf.org/html/rfc7231#section-7.1.1.1
                        ims = ims.replace(tzinfo=datetime.timezone.utc)
                    if ims.tzinfo is datetime.timezone.utc:
                        # compare to UTC datetime of last modification
                        last_modif = datetime.datetime.fromtimestamp(fs.st_mtime, datetime.timezone.utc)
                        # remove microseconds, like in If-Modified-Since
                        last_modif = last_modif.replace(microsecond=0)

                        if last_modif <= ims:
                            self.send_response(http.HTTPStatus.NOT_MODIFIED)
                            self.end_headers()
                            f.close()
                            return None

            self.send_response(http.HTTPStatus.OK)
            self.send_header('Content-Type', ctype)
            # TODO handle symbolic link
            self.send_header('Content-Length', str(fs.st_size))
            self.send_header('Last-Modified', self.date_time_string(fs.st_mtime))
            self.end_headers()
            return f
        except:
            f.close()
            raise

    def date_time_string(self, timestamp=None):
        if timestamp is None:
            timestamp = time.time()

        return email.utils.formatdate(timestamp, usegmt=True)

    def guess_type(self, path: str):
        base, ext = posixpath.splitext(path)
        if ext in g_extensions_map:
            return g_extensions_map[ext]

        ext = ext.lower()
        if ext in g_extensions_map:
            return g_extensions_map[ext]
        else:
            return g_extensions_map['']

    def do_GET(self):
        f = self.send_head()
        if f:
            try:
                shutil.copyfileobj(f, self.wfile)
            finally:
                f.close()

    def list_all(self):
        serialized_records = []
        for record in g_furigana_database:
            serialized_records.append(record.to_dict())

        f = io.BytesIO()
        serialized_json_str = json.dumps(serialized_records, ensure_ascii=False)
        encoded_json_str = serialized_json_str.encode('utf-8')
        f.write(encoded_json_str)
        f.seek(0)

        self.send_response(http.HTTPStatus.OK)
        self.send_header('Content-Type', 'application/json; charset=UTF-8')
        self.send_header('Content-Length', str(len(encoded_json_str)))
        self.end_headers()

        return f

    def do_POST(self):
        """
        All the API will be accessed via POST method so that we can
        still keep the static file serving.
        """
        split_result = urllib.parse.urlsplit(self.path)
        path = split_result.path

        if path == '/api/all':
            f = self.list_all()
        else:
            self.send_error(http.HTTPStatus.NOT_FOUND, 'API endpoint does not exist!')
            f = None
        if f:
            try:
                shutil.copyfileobj(f, self.wfile)
            finally:
                f.close()


web_server = HTTPServer((g_hostname, g_server_port), FuriganaServer)
print(f'Serving server at http://{g_hostname}:{g_server_port}')

try:
    web_server.serve_forever()
except KeyboardInterrupt:
    pass

web_server.server_close()

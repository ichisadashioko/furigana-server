#!/usr/bin/env python3
# encoding=utf-8
import os
import re
import time

import http
from http.server import BaseHTTPRequestHandler, HTTPServer

import urllib
import urllib.parse


def convert_to_unix_style_path(path: str):
    retval = re.sub(f'[\/]+', '/')
    return retval


HOST_NAME = 'localhost'
SERVER_PORT = 8080
ROOT_DIR = '.'
ROOT_DIR = os.path.abspath(ROOT_DIR)
ROOT_DIR = convert_to_unix_style_path(ROOT_DIR)

script_dir, script_filename = os.path.split(__file__)

listing_page_path = os.path.join(script_dir, 'statics', 'listing-page.html')
if not os.path.exists(listing_page_path):
    raise Exception((
        f'{listing_page_path}\n'
        f'Listing page template does not exist!'
    ))

listing_page_template = open(listing_page_path, mode='r', encoding='utf-8').read()


def create_directory_listing_page(title: str, body: str):
    retval = listing_page_path.replace('{title}', title)
    retval = retval.replace('{body}', body)
    return retval


def trim_path_separators(s: str):
    return re.sub('/+', '/', s)


class KanjiServer(BaseHTTPRequestHandler):
    def do_GET(self):
        print(self.__dict__)

        parse_result = urllib.parse.urlparse(self.path)
        requested_path = parse_result.path
        requested_path_components = requested_path.split('/')
        requested_path_components = list(filter(lambda x: len(x) > 0, requested_path_components))
        # decode every path components
        requested_path_components = list(map(lambda x: urllib.parse.unquote(x), requested_path_components))
        requested_path = '/'.join(requested_path_components)

        requested_local_path = f'{ROOT_DIR}/{requested_path}'
        requested_local_path = os.path.abspath(requested_local_path)
        requested_local_path = convert_to_unix_style_path(requested_local_path)

        # check for attempts to access system path outside of authorized path
        if os.name == 'nt':
            if not ROOT_DIR.lower() in requested_local_path.lower():
                self.send_response(int(http.HTTPStatus.FORBIDDEN), f'You are not suppose to access {requested_path}')
                return
        elif not ROOT_DIR in requested_local_path:
            self.send_response(int(http.HTTPStatus.FORBIDDEN), f'You are not suppose to access {requested_path}')
            return

        if not os.path.exists(requested_local_path):
            self.send_response(int(http.HTTPStatus.NOT_FOUND), f'{requested_path} does not exist!')
            return

        self.send_response(int(http.HTTPStatus.OK))

        if os.path.isdir(requested_local_path):
            index_doc = trim_path_separators(f'{requested_local_path}/index.html')
            if os.path.exists(index_doc):
                self.send_header('Content-Type', 'text/html')
                self.end_headers()

                doc_bs = open(index_doc, mode='rb').read()
                self.wfile.write(doc_bs)
                return
            else:
                self.send_header('Content-Type', 'text/html')
                self.end_headers()

                body_html_text = '<ul>'
                file_list = os.listdir(requested_local_path)
                for child_name in file_list:
                    child_anchor = f'<a href="./{child_name}">{child_name}</a>'
                    body_html_text += child_anchor
                body_html_text += '</ul>'
                doc = create_directory_listing_page(requested_path, body_html_text)
                self.wfile.write(doc.encode('utf-8'))
                return
        else:
            file_ext = os.path.splitext(requested_local_path)[0]
            file_ext = file_ext.lower()
            if file_ext == '.js':
                self.send_header('Content-Type', 'text/javascript')
            elif file_ext == '.css':
                self.send_header('Content-Type', 'text/css')

            self.end_headers()
            file_bs = open(requested_local_path, mode='rb').read()
            self.wfile.write(file_bs)
            return


web_server = HTTPServer((HOST_NAME, SERVER_PORT), KanjiServer)
print(f'http://{HOST_NAME}:{SERVER_PORT}')

try:
    web_server.serve_forever()
except KeyboardInterrupt:
    pass

web_server.server_close()

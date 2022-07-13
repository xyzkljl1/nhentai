# coding: utf-8

import sys
import re
import os
import zipfile
import shutil
import requests
import sqlite3

from nhentai import constant
from nhentai.logger import logger
from nhentai.serializer import serialize_json, serialize_comic_xml, set_js_database


def request(method, url, **kwargs):
    session = requests.Session()
    session.headers.update({
        'Referer': constant.LOGIN_URL,
        'User-Agent': constant.CONFIG['useragent'],
        'Cookie': constant.CONFIG['cookie']
    })

    if not kwargs.get('proxies', None):
        kwargs['proxies'] = constant.CONFIG['proxy']

    return getattr(session, method)(url, verify=False, **kwargs)


def check_cookie():
    response = request('get', constant.BASE_URL)
    if response.status_code == 503 and 'cf-browser-verification' in response.text:
        logger.error('Blocked by Cloudflare captcha, please set your cookie and useragent')
        exit(-1)

    username = re.findall('"/users/\d+/(.*?)"', response.text)
    if not username:
        logger.warning('Cannot get your username, please check your cookie or use `nhentai --cookie` to set your cookie')
    else:
        logger.info('Login successfully! Your username: {}'.format(username[0]))


class _Singleton(type):
    """ A metaclass that creates a Singleton base class when called. """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Singleton(_Singleton(str('SingletonMeta'), (object,), {})):
    pass


def urlparse(url):
    try:
        from urlparse import urlparse
    except ImportError:
        from urllib.parse import urlparse

    return urlparse(url)


def readfile(path):
    loc = os.path.dirname(__file__)

    with open(os.path.join(loc, path), 'r') as file:
        return file.read()


def generate_html(output_dir='.', doujinshi_obj=None, template='default'):
    image_html = ''

    if doujinshi_obj is not None:
        doujinshi_dir = os.path.join(output_dir, doujinshi_obj.filename)
    else:
        doujinshi_dir = '.'

    if not os.path.exists(doujinshi_dir):
        logger.warning('Path \'{0}\' does not exist, creating.'.format(doujinshi_dir))
        try:
            os.makedirs(doujinshi_dir)
        except EnvironmentError as e:
            logger.critical('{0}'.format(str(e)))

    file_list = os.listdir(doujinshi_dir)
    file_list.sort()

    for image in file_list:
        if not os.path.splitext(image)[1] in ('.jpg', '.png'):
            continue

        image_html += '<img src="{0}" class="image-item"/>\n' \
            .format(image)
    html = readfile('viewer/{}/index.html'.format(template))
    css = readfile('viewer/{}/styles.css'.format(template))
    js = readfile('viewer/{}/scripts.js'.format(template))

    if doujinshi_obj is not None:
        serialize_json(doujinshi_obj, doujinshi_dir)
        name = doujinshi_obj.name
        if sys.version_info < (3, 0):
            name = doujinshi_obj.name.encode('utf-8')
    else:
        name = {'title': 'nHentai HTML Viewer'}

    data = html.format(TITLE=name, IMAGES=image_html, SCRIPTS=js, STYLES=css)
    try:
        if sys.version_info < (3, 0):
            with open(os.path.join(doujinshi_dir, 'index.html'), 'w') as f:
                f.write(data)
        else:
            with open(os.path.join(doujinshi_dir, 'index.html'), 'wb') as f:
                f.write(data.encode('utf-8'))

        logger.log(15, 'HTML Viewer has been written to \'{0}\''.format(os.path.join(doujinshi_dir, 'index.html')))
    except Exception as e:
        logger.warning('Writing HTML Viewer failed ({})'.format(str(e)))


def generate_main_html(output_dir='./'):
    """
    Generate a main html to show all the contain doujinshi.
    With a link to their `index.html`.
    Default output folder will be the CLI path.
    """

    image_html = ''

    main = readfile('viewer/main.html')
    css = readfile('viewer/main.css')
    js = readfile('viewer/main.js')

    element = '\n\
            <div class="gallery-favorite">\n\
                <div class="gallery">\n\
                    <a href="./{FOLDER}/index.html" class="cover" style="padding:0 0 141.6% 0"><img\n\
                            src="./{FOLDER}/{IMAGE}" />\n\
                        <div class="caption">{TITLE}</div>\n\
                    </a>\n\
                </div>\n\
            </div>\n'

    os.chdir(output_dir)
    doujinshi_dirs = next(os.walk('.'))[1]

    for folder in doujinshi_dirs:
        files = os.listdir(folder)
        files.sort()

        if 'index.html' in files:
            logger.info('Add doujinshi \'{}\''.format(folder))
        else:
            continue

        image = files[0]  # 001.jpg or 001.png
        if folder is not None:
            title = folder.replace('_', ' ')
        else:
            title = 'nHentai HTML Viewer'

        image_html += element.format(FOLDER=folder, IMAGE=image, TITLE=title)
    if image_html == '':
        logger.warning('No index.html found, --gen-main paused.')
        return
    try:
        data = main.format(STYLES=css, SCRIPTS=js, PICTURE=image_html)
        if sys.version_info < (3, 0):
            with open('./main.html', 'w') as f:
                f.write(data)
        else:
            with open('./main.html', 'wb') as f:
                f.write(data.encode('utf-8'))
        shutil.copy(os.path.dirname(__file__) + '/viewer/logo.png', './')
        set_js_database()
        logger.log(
            15, 'Main Viewer has been written to \'{0}main.html\''.format(output_dir))
    except Exception as e:
        logger.warning('Writing Main Viewer failed ({})'.format(str(e)))


def generate_cbz(output_dir='.', doujinshi_obj=None, rm_origin_dir=False, write_comic_info=True):
    if doujinshi_obj is not None:
        doujinshi_dir = os.path.join(output_dir, doujinshi_obj.filename)
        if write_comic_info:
            serialize_comic_xml(doujinshi_obj, doujinshi_dir)
        cbz_filename = os.path.join(os.path.join(doujinshi_dir, '..'), '{}.cbz'.format(doujinshi_obj.filename))
    else:
        cbz_filename = './doujinshi.cbz'
        doujinshi_dir = '.'

    file_list = os.listdir(doujinshi_dir)
    file_list.sort()

    logger.info('Writing CBZ file to path: {}'.format(cbz_filename))
    with zipfile.ZipFile(cbz_filename, 'w') as cbz_pf:
        for image in file_list:
            image_path = os.path.join(doujinshi_dir, image)
            cbz_pf.write(image_path, image)

    if rm_origin_dir:
        shutil.rmtree(doujinshi_dir, ignore_errors=True)

    logger.log(15, 'Comic Book CBZ file has been written to \'{0}\''.format(doujinshi_dir))


def generate_pdf(output_dir='.', doujinshi_obj=None, rm_origin_dir=False):
    try:
        import img2pdf

        """Write images to a PDF file using img2pdf."""
        if doujinshi_obj is not None:
            doujinshi_dir = os.path.join(output_dir, doujinshi_obj.filename)
            pdf_filename = os.path.join(
                os.path.join(doujinshi_dir, '..'),
                '{}.pdf'.format(doujinshi_obj.filename)
            )
        else:
            pdf_filename = './doujinshi.pdf'
            doujinshi_dir = '.'

        file_list = os.listdir(doujinshi_dir)
        file_list.sort()

        logger.info('Writing PDF file to path: {}'.format(pdf_filename))
        with open(pdf_filename, 'wb') as pdf_f:
            full_path_list = (
                [os.path.join(doujinshi_dir, image) for image in file_list]
            )
            pdf_f.write(img2pdf.convert(full_path_list))

        if rm_origin_dir:
            shutil.rmtree(doujinshi_dir, ignore_errors=True)

        logger.log(15, 'PDF file has been written to \'{0}\''.format(doujinshi_dir))

    except ImportError:
        logger.error("Please install img2pdf package by using pip.")


def unicode_truncate(s, length, encoding='utf-8'):
    """https://stackoverflow.com/questions/1809531/truncating-unicode-so-it-fits-a-maximum-size-when-encoded-for-wire-transfer
    """
    encoded = s.encode(encoding)[:length]
    return encoded.decode(encoding, 'ignore')


def format_filename(s):
    """
    It used to be a whitelist approach allowed only alphabet and a part of symbols.
    but most doujinshi's names include Japanese 2-byte characters and these was rejected.
    so it is using blacklist approach now.
    if filename include forbidden characters (\'/:,;*?"<>|) ,it replace space character(' '). 
    """
    # maybe you can use `--format` to select a suitable filename
    ban_chars = '\\\'/:,;*?"<>|\t'
    filename = s.translate(str.maketrans(ban_chars, ' ' * len(ban_chars))).strip()
    filename = ' '.join(filename.split())

    while filename.endswith('.'):
        filename = filename[:-1]

    # limit 254 chars
    if len(filename) >= 255:
        filename = filename[:254] + u'…'

    # Remove [] from filename
    filename = filename.replace('[]', '').strip()
    return filename


def signal_handler(signal, frame):
    logger.error('Ctrl-C signal received. Stopping...')
    exit(1)


def paging(page_string):
    # 1,3-5,14 -> [1, 3, 4, 5, 14]
    if not page_string:
        return []

    page_list = []
    for i in page_string.split(','):
        if '-' in i:
            start, end = i.split('-')
            if not (start.isdigit() and end.isdigit()):
                raise Exception('Invalid page number')
            page_list.extend(list(range(int(start), int(end) + 1)))
        else:
            if not i.isdigit():
                raise Exception('Invalid page number')
            page_list.append(int(i))

    return page_list


def generate_metadata_file(output_dir, table, doujinshi_obj=None):
    logger.info('Writing Metadata Info')

    if doujinshi_obj is not None:
        doujinshi_dir = os.path.join(output_dir, doujinshi_obj.filename)
    else:
        doujinshi_dir = '.'

    logger.info(doujinshi_dir)

    f = open(os.path.join(doujinshi_dir, 'info.txt'), 'w', encoding='utf-8')

    fields = ['TITLE', 'ORIGINAL TITLE', 'AUTHOR', 'ARTIST', 'CIRCLE', 'SCANLATOR',
              'TRANSLATOR', 'PUBLISHER', 'DESCRIPTION', 'STATUS', 'CHAPTERS', 'PAGES',
              'TAGS', 'TYPE', 'LANGUAGE', 'RELEASED', 'READING DIRECTION', 'CHARACTERS',
              'SERIES', 'PARODY', 'URL']
    special_fields = ['PARODY', 'TITLE', 'ORIGINAL TITLE', 'CHARACTERS', 'AUTHOR',
                      'LANGUAGE', 'TAGS', 'URL', 'PAGES']

    for i in range(len(fields)):
        f.write('{}: '.format(fields[i]))
        if fields[i] in special_fields:
            f.write(str(table[special_fields.index(fields[i])][1]))
        f.write('\n')

    f.close()


class DB(object):
    conn = None
    cur = None

    def __enter__(self):
        self.conn = sqlite3.connect(constant.NHENTAI_HISTORY)
        self.cur = self.conn.cursor()
        self.cur.execute('CREATE TABLE IF NOT EXISTS download_history (id text)')
        self.conn.commit()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    def clean_all(self):
        self.cur.execute('DELETE FROM download_history WHERE 1')
        self.conn.commit()

    def add_one(self, data):
        self.cur.execute('INSERT INTO download_history VALUES (?)', [data])
        self.conn.commit()

    def get_all(self):
        data = self.cur.execute('SELECT id FROM download_history')
        return [i[0] for i in data]

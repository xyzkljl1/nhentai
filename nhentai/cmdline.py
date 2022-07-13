# coding: utf-8

import os
import sys
import json
from optparse import OptionParser

try:
    from itertools import ifilter as filter
except ImportError:
    pass

import nhentai.constant as constant
from nhentai import __version__
from nhentai.utils import urlparse, generate_html, generate_main_html, DB
from nhentai.logger import logger


def banner():
    logger.info(u'''nHentai ver %s: あなたも変態。 いいね?
       _   _            _        _
 _ __ | | | | ___ _ __ | |_ __ _(_)
| '_ \| |_| |/ _ \ '_ \| __/ _` | |
| | | |  _  |  __/ | | | || (_| | |
|_| |_|_| |_|\___|_| |_|\__\__,_|_|
''' % __version__)


def load_config():
    if not os.path.exists(constant.NHENTAI_CONFIG_FILE):
        return

    try:
        with open(constant.NHENTAI_CONFIG_FILE, 'r') as f:
            constant.CONFIG.update(json.load(f))
    except json.JSONDecodeError:
        logger.error('Failed to load config file.')
        write_config()


def write_config():
    if not os.path.exists(constant.NHENTAI_HOME):
        os.mkdir(constant.NHENTAI_HOME)

    with open(constant.NHENTAI_CONFIG_FILE, 'w') as f:
        f.write(json.dumps(constant.CONFIG))


def cmd_parser(para):
    #load_config()

    parser = OptionParser('\n  nhentai --search [keyword] --download'
                          '\n  NHENTAI=http://h.loli.club nhentai --id [ID ...]'
                          '\n  nhentai --file [filename]'
                          '\n\nEnvironment Variable:\n'
                          '  NHENTAI                 nhentai mirror url')
    # operation options
    parser.add_option('--download', '-D', dest='is_download', action='store_true',
                      help='download doujinshi (for search results)')
    parser.add_option('--show', '-S', dest='is_show', action='store_true', help='just show the doujinshi information')

    # doujinshi options
    parser.add_option('--id', type='string', dest='id', action='store', help='doujinshi ids set, e.g. 1,2,3')
    parser.add_option('--search', '-s', type='string', dest='keyword', action='store',
                      help='search doujinshi by keyword')
    parser.add_option('--favorites', '-F', action='store_true', dest='favorites',
                      help='list or download your favorites.')

    # page options
    parser.add_option('--page-all', dest='page_all', action='store_true', default=False,
                      help='all search results')
    parser.add_option('--page', '--page-range', type='string', dest='page', action='store', default='',
                      help='page number of search results. e.g. 1,2-5,14')
    parser.add_option('--sorting', dest='sorting', action='store', default='recent',
                      help='sorting of doujinshi (recent / popular / popular-[today|week])',
                      choices=['recent', 'popular', 'popular-today', 'popular-week', 'date'])

    # download options
    parser.add_option('--output', '-o', type='string', dest='output_dir', action='store', default='./',
                      help='output dir')
    parser.add_option('--threads', '-t', type='int', dest='threads', action='store', default=5,
                      help='thread count for downloading doujinshi')
    parser.add_option('--timeout', '-T', type='int', dest='timeout', action='store', default=30,
                      help='timeout for downloading doujinshi')
    parser.add_option('--delay', '-d', type='int', dest='delay', action='store', default=0,
                      help='slow down between downloading every doujinshi')
    parser.add_option('--proxy', type='string', dest='proxy', action='store',
                      help='store a proxy, for example: -p \'http://127.0.0.1:1080\'')
    parser.add_option('--file', '-f', type='string', dest='file', action='store', help='read gallery IDs from file.')
    parser.add_option('--format', type='string', dest='name_format', action='store',
                      help='format the saved folder name', default='[%i][%a][%t]')
    parser.add_option('--dry-run', '-r', action='store_true', dest='dryrun', help='Dry run, skip file download.')

    # generate options
    parser.add_option('--html', dest='html_viewer', action='store_true',
                      help='generate a html viewer at current directory')
    parser.add_option('--no-html', dest='is_nohtml', action='store_true',
                      help='don\'t generate HTML after downloading')
    parser.add_option('--gen-main', dest='main_viewer', action='store_true',
                      help='generate a main viewer contain all the doujin in the folder')
    parser.add_option('--cbz', '-C', dest='is_cbz', action='store_true',
                      help='generate Comic Book CBZ File')
    parser.add_option('--pdf', '-P', dest='is_pdf', action='store_true',
                      help='generate PDF file')
    parser.add_option('--rm-origin-dir', dest='rm_origin_dir', action='store_true', default=False,
                      help='remove downloaded doujinshi dir when generated CBZ or PDF file.')
    parser.add_option('--meta', dest='generate_metadata', action='store_true',
                      help='generate a metadata file in doujinshi format')
    parser.add_option('--regenerate-cbz', dest='regenerate_cbz', action='store_true', default=False,
                      help='regenerate the cbz file if exists')

    # nhentai options
    parser.add_option('--cookie', type='str', dest='cookie', action='store',
                      help='set cookie of nhentai to bypass Cloudflare captcha')
    parser.add_option('--useragent', '--user-agent', type='str', dest='useragent', action='store',
                      help='set useragent to bypass Cloudflare captcha')
    parser.add_option('--language', type='str', dest='language', action='store',
                      help='set default language to parse doujinshis')
    parser.add_option('--clean-language', dest='clean_language', action='store_true', default=False,
                      help='set DEFAULT as language to parse doujinshis')
    parser.add_option('--save-download-history', dest='is_save_download_history', action='store_true',
                      default=False, help='save downloaded doujinshis, whose will be skipped if you re-download them')
    parser.add_option('--clean-download-history', action='store_true', default=False, dest='clean_download_history',
                      help='clean download history')
    parser.add_option('--template', dest='viewer_template', action='store',
                      help='set viewer template', default='')

    try:
        sys.argv = [unicode(i.decode(sys.stdin.encoding)) for i in sys.argv]
    except (NameError, TypeError):
        pass
    except UnicodeDecodeError:
        exit(0)

    args, _ = parser.parse_args(para)

    if args.html_viewer:
        generate_html(template=constant.CONFIG['template'])
        exit(0)

    if args.main_viewer and not args.id and not args.keyword and not args.favorites:
        generate_main_html()
        exit(0)

    if args.clean_download_history:
        with DB() as db:
            db.clean_all()

        logger.info('Download history cleaned.')
        exit(0)

    # --- set config ---
    if args.cookie is not None:
        constant.CONFIG['cookie'] = args.cookie
        write_config()
        logger.info('Cookie saved.')
        exit(0)
    elif args.useragent is not None:
        constant.CONFIG['useragent'] = args.useragent
        write_config()
        logger.info('User-Agent saved.')
        exit(0)
    elif args.language is not None:
        constant.CONFIG['language'] = args.language
        write_config()
        logger.info('Default language now set to \'{0}\''.format(args.language))
        exit(0)
        # TODO: search without language

    if args.proxy is not None:
        proxy_url = urlparse(args.proxy)
        if not args.proxy == '' and proxy_url.scheme not in ('http', 'https', 'socks5', 'socks5h', 'socks4', 'socks4a'):
            logger.error('Invalid protocol \'{0}\' of proxy, ignored'.format(proxy_url.scheme))
            exit(0)
        else:
            constant.CONFIG['proxy'] = {
                'http': args.proxy,
                'https': args.proxy,
            }
            logger.info('Proxy now set to \'{0}\'.'.format(args.proxy))
            write_config()
            exit(0)

    if args.viewer_template is not None:
        if not args.viewer_template:
            args.viewer_template = 'default'

        if not os.path.exists(os.path.join(os.path.dirname(__file__),
                                           'viewer/{}/index.html'.format(args.viewer_template))):
            logger.error('Template \'{}\' does not exists'.format(args.viewer_template))
            exit(1)
        else:
            constant.CONFIG['template'] = args.viewer_template
            write_config()

    # --- end set config ---

    if args.favorites:
        if not constant.CONFIG['cookie']:
            logger.warning('Cookie has not been set, please use `nhentai --cookie \'COOKIE\'` to set it.')
            exit(1)

    if args.id:
        _ = [i.strip() for i in args.id.split(',')]
        args.id = set(int(i) for i in _ if i.isdigit())

    if args.file:
        with open(args.file, 'r') as f:
            _ = [i.strip() for i in f.readlines()]
            args.id = set(int(i) for i in _ if i.isdigit())

    if (args.is_download or args.is_show) and not args.id and not args.keyword and not args.favorites:
        logger.critical('Doujinshi id(s) are required for downloading')
        parser.print_help()
        exit(1)

    if not args.keyword and not args.id and not args.favorites:
        parser.print_help()
        exit(1)

    if args.threads <= 0:
        args.threads = 1

    elif args.threads > 15:
        logger.critical('Maximum number of used threads is 15')
        exit(1)

    if args.dryrun and (args.is_cbz or args.is_pdf):
        logger.critical('Cannot generate PDF or CBZ during dry-run')
        exit(1)

    return args

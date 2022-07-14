#!/usr/bin/env python2.7
# coding: utf-8

import sys
import signal
import platform
import time

from nhentai import constant
from nhentai.cmdline import cmd_parser, banner
from nhentai.parser import doujinshi_parser, search_parser, print_doujinshi, favorites_parser
from nhentai.doujinshi import Doujinshi
from nhentai.downloader import Downloader
from nhentai.logger import logger
from nhentai.constant import BASE_URL
from nhentai.utils import generate_html, generate_cbz, generate_main_html, generate_pdf, generate_metadata_file, \
    paging, check_cookie, signal_handler, DB


def main(proxy,cookie,useragent,para):
    constant.CONFIG['proxy']={'http':proxy,'https':proxy}
    constant.CONFIG['cookie']=cookie
    constant.CONFIG['useragent']=useragent

    #banner()

    if sys.version_info < (3, 0, 0):
        logger.error('nhentai now only support Python 3.x')
        exit(1)

    options = cmd_parser(para)
    logger.info('Using mirror: {0}'.format(BASE_URL))

    # CONFIG['proxy'] will be changed after cmd_parser()
    if constant.CONFIG['proxy']['http']:
        logger.info('Using proxy: {0}'.format(constant.CONFIG['proxy']['http']))

    if not constant.CONFIG['template']:
        constant.CONFIG['template'] = 'default'

    logger.info('Using viewer template "{}"'.format(constant.CONFIG['template']))

    # check your cookie
    check_cookie()

    doujinshis = []
    doujinshi_ids = []
    doujinshi_list = []

    page_list = paging(options.page)

    if options.favorites:
        if not options.is_download:
            logger.warning('You do not specify --download option')

        doujinshis = favorites_parser(page=page_list)

    elif options.keyword:
        if constant.CONFIG['language']:
            logger.info('Using default language: {0}'.format(constant.CONFIG['language']))
            options.keyword += ' language:{}'.format(constant.CONFIG['language'])
        doujinshis = search_parser(options.keyword, sorting=options.sorting, page=page_list,
                                   is_page_all=options.page_all)

    elif not doujinshi_ids:
        doujinshi_ids = options.id

    print_doujinshi(doujinshis)
    if options.is_download and doujinshis:
        doujinshi_ids = [i['id'] for i in doujinshis]

    if options.is_save_download_history:
        with DB() as db:
            data = map(int, db.get_all())

        doujinshi_ids = list(set(map(int, doujinshi_ids)) - set(data))

    if doujinshi_ids:
        for i, id_ in enumerate(doujinshi_ids):
            if options.delay:
                time.sleep(options.delay)

            doujinshi_info = doujinshi_parser(id_)

            if doujinshi_info:
                doujinshi_list.append(Doujinshi(name_format=options.name_format, **doujinshi_info))

            if (i + 1) % 10 == 0:
                logger.info('Progress: %d / %d' % (i + 1, len(doujinshi_ids)))

    if not options.is_show:
        downloader = Downloader(path=options.output_dir, size=options.threads,
                                timeout=options.timeout, delay=options.delay)

        for doujinshi in doujinshi_list:
            if not options.dryrun:
                doujinshi.downloader = downloader
                doujinshi.download(regenerate_cbz=options.regenerate_cbz)

            if options.generate_metadata:
                table = doujinshi.table
                generate_metadata_file(options.output_dir, table, doujinshi)

            if options.is_save_download_history:
                with DB() as db:
                    db.add_one(doujinshi.id)

            if not options.is_nohtml and not options.is_cbz and not options.is_pdf:
                generate_html(options.output_dir, doujinshi, template=constant.CONFIG['template'])
            elif options.is_cbz:
                generate_cbz(options.output_dir, doujinshi, options.rm_origin_dir)
            elif options.is_pdf:
                generate_pdf(options.output_dir, doujinshi, options.rm_origin_dir)

        if options.main_viewer:
            generate_main_html(options.output_dir)

        if not platform.system() == 'Windows':
            logger.log(15, '🍻 All done.')
        else:
            logger.log(15, 'All done.')

    else:
        [doujinshi.show() for doujinshi in doujinshi_list]


signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    main()

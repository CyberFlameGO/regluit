"""
doab_utils.py

"""
import logging
import re
from ssl import SSLError
from urllib.parse import urljoin

import requests

from oaipmh.metadata import MetadataReader

from django.conf import settings

from regluit.core import models
from regluit.utils.lang import lang_to_language_code
from .soup import get_soup


logger = logging.getLogger(__name__)

def doab_lang_to_iso_639_1(lang):
    lang = lang_to_language_code(lang)
    return lang if lang else 'xx'


doab_reader = MetadataReader(
    fields={
        'title': ('textList', 'oai_dc:dc/datacite:title/text()'),
        'creator': ('textList', 'oai_dc:dc/datacite:creator/text()'),
        'subject': ('textList', 'oai_dc:dc/datacite:subject/text()'),
        'description': ('textList', 'oai_dc:dc/dc:description/text()'),
        'publisher': ('textList', 'oai_dc:dc/dc:publisher/text()'),
        'editor': ('textList', 'oai_dc:dc/datacite:contributor[@type="Editor"]/text()'),
        'date': ('textList', 'oai_dc:dc/datacite:date[@type="Issued"]/text()'),
        'type': ('textList', 'oai_dc:dc/oaire:resourceType/text()'),
        'format': ('textList', 'oai_dc:dc/dc:format/text()'),
        'identifier': ('textList', 'oai_dc:dc/dc:identifier/text()'),
        'source': ('textList', 'oai_dc:dc/dc:source/text()'),
        'language': ('textList', 'oai_dc:dc/dc:language/text()'),
        'relation': ('textList', 'oai_dc:dc/dc:relation/text()'),
        'coverage': ('textList', 'oai_dc:dc/dc:coverage/text()'),
        'rights': ('textList', 'oai_dc:dc/oaire:licenseCondition/@uri'),
        'isbn': ('textList', 'oai_dc:dc/datacite:alternateIdentifier[@type="ISBN"]/text()'),
        'doi': ('textList', 'oai_dc:dc/datacite:alternateIdentifier[@type="DOI"]/text()'),
    },
    namespaces={
        'oai_dc': 'http://www.openarchives.org/OAI/2.0/oai_dc/',
        'dc' : 'http://purl.org/dc/elements/1.1/',
        'grantor': 'http://purl.org/dc/elements/1.1/',
        'publisher': 'http://purl.org/dc/elements/1.1/',
        'oapen': 'http://purl.org/dc/elements/1.1/',
        'oaire': 'https://raw.githubusercontent.com/rcic/openaire4/master/schemas/4.0/oaire.xsd',
        'datacite': 'https://schema.datacite.org/meta/kernel-4.1/metadata.xsd',
        'doc': 'http://www.lyncode.com/xoai'
    }
)

BOOKSHOP_PROVIDERS = [
    'placedeslibraires.fr',
    '7switch.com',
    'duncker-humblot.de',
    'bloomsbury.com',
    'usu.edu',
    'sci.fo',
    'e-elgar.com',
    'nomos-shop.de',
]

def online_to_download(url):
    urls = []
    if not url or models.Ebook.infer_provider(url) in BOOKSHOP_PROVIDERS:
        return urls
    if url.find(u'books.scielo.org/') >= 0:
        if url[-4:] in ['epub', '.pdf']:
            return [url]
        doc = get_soup(url)
        if doc:
            obj = doc.find('a', class_='pdf_file')
            if obj:
                urls.append(urljoin(url, obj['href']))
            obj = doc.find('a', class_='epub_file')
            if obj:
                urls.append(urljoin(url, obj['href']))
    elif url.find(u'edp-open.org/books-in-') >= 0:
        # pages needing multi-scrape
        return urls
    else:
        urls.append(url)
    if not urls:
        logging.warning('no valid download urls for %s', url)
    return urls


STREAM_QUERY = 'https://directory.doabooks.org/rest/search?query=handle:{}&expand=bitstreams'

def get_streamdata(handle):
    url = STREAM_QUERY.format(handle)
    try:
        response = requests.get(url, headers={"User-Agent": settings.USER_AGENT})
        items = response.json()
        if items:
            for stream in items[0]['bitstreams']:
                if stream['bundleName'] == "THUMBNAIL":
                    stream['handle'] = handle
                    return stream
        else:
            logger.error("No items in streamdata for %s", handle)
    except requests.exceptions.RequestException as e:
        logger.error(e)
    except SSLError as e:
        logger.error(e)
    except ValueError as e:
        # decoder error
        logger.error(e)

COVER_FSTRING = "https://directory.doabooks.org/bitstream/handle/{handle}/{name}?sequence={sequenceId}&isAllowed=y"
def doab_cover(doab_id):
    stream_data = get_streamdata(doab_id)
    if not stream_data:
        logger.error('get_streamdata failed for %s', doab_id)
        return None
    return COVER_FSTRING.format(**stream_data)


import argparse
import codecs
import datetime as dt
import django
import glob
import logging
import os
import random
import re
import sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "litlong.local_settings")
from api.models import (
    Author,
    Collection,
    Document,
    Document_Author,
    Document_Genre,
    Genre,
    Location,
    LocationMention,
    Page,
    Publisher,
    Sentence,
    PartOfSpeech,
    POSMention,
)
from calendar import monthrange
from datetime import date, datetime
from django.core.exceptions import MultipleObjectsReturned
from django.contrib.gis.geos import Point
from django.contrib.gis.geos import Polygon
from django.db import connection
from xml.etree import cElementTree as ET
from titlecase import titlecase

VERSION = '0.7'

log = logging.getLogger('parser')
django.setup()

reload(sys)
sys.setdefaultencoding('utf8')

def timer(f):
    """ Decorator for determining the runtime for a function """

    def deco(self, *args):
        then = datetime.now()
        d = f(self, *args)

        td = datetime.now() - then

        if td.seconds < 60:
            print '\nCOMPLETE: Parse took: %d secs' % td.seconds
        else:
            print '\nCOMPLETE: Parse took: %d hour(s): %d mins: %d secs' % (
                td.seconds / 3600,
                (td.seconds / 60) % 60,
                td.seconds % 60)
        return d
    return deco


class Parser():
    """
    Palimpsest document parser.

    Attributes:
        document_path: The full path to either an individual document XML file
            or a folder containing document XML files.
        start: Start document to be parsed, only applies to a folder of
            documents parse. If no document given start from 0.
        end: End document to be parsed. Only applies to a folder of documents
            parse. If no end document is given the parse process will contine
            until the last document in the folder is processed.
        verbose: Print detailed output. False by default.
        threshold: Location confidence threshold, if defined any i-score below
            this value will be ignored by the parser.
    """

    __current_file = None
    __page_element = 0

    def __init__(self,
                 document_path,
                 start=0,
                 end=9999,
                 verbose=False,
                 threshold=None):
        self.document_path = document_path
        self.start = int(start)
        self.end = int(end)
        self.verbose = verbose
        self.pos = PartOfSpeech.objects.all()
        self.threshold = threshold

    @timer
    def run_parser(self):
        """
        Parse the Palimpsest XML documents
        """

        documents = self._get_listing()
        for document in documents:
            self._parse_document(document)
            #exit(0)
        return

    def _get_listing(self):
        """
        Determine whether document_path is a file or directory
        """

        if os.path.isdir(self.document_path):
            os.chdir(self.document_path)
            return glob.glob('*.xml')[self.start:self.end]
        else:
            self.document_path, filename = os.path.split(self.document_path)
            return [filename]

    def _parse_document(self, filename):
        """
        Parses a single XML document

        Parses a single XML document and saves the extracted Collection,
        Document, Location, and LocationMention objects to the database.

        Args:
            filename: a string representing an XML document filename
        """

        print 'Parsing %s ' % filename
        self.__current_file = filename

        root_element = self._get_root_element_from_xml(filename)
        # Parse the metadata element block and store in new document
        document = self._process_metadata_and_create_document(root_element)
        if document is not None:
            if self.verbose:
                self._print_metadata(document)

            # Parse and store the location elements
            locations = self._process_locations(root_element, document)
            from django.db.models import Count
            if self.verbose:
                print '\tLocations mentions'.upper()
                for location in LocationMention.objects.filter(document=document).values('text').annotate(total=Count('text')) :
                    print '\t- {0} {1}'.format(location['text'], location['total'])
                print '\tLocations ignored'.upper()
                print '\t- ',self.__ignored_locations
                print ''
        return

    def _process_metadata_and_create_document(self, root_element):
        """
        Parses an Element and create a Document object

        Args:
            root_element: an elementtree Element object

        Returns:
            document: a Document object
        """

        # Determine if a Collection object exists or if one needs to be created
        collection_text = self._get_element_text(
            root_element, 'meta', 'collection')
        try:
            collection, created = Collection.objects.get_or_create(
                text=collection_text)
        except Exception, e:
            log.error(
                "%s (%s): creating Collection for file %s" %
                (type(e).__name__, e.message, self.__current_file))
            connection._rollback()
            exit(0)

        title = self._get_element_text(root_element, 'meta', 'title')
        docid = self._get_element_text(root_element, 'meta', 'docid')

        try:
            #print title, docid, collection, '<-'
            doc, created = Document.objects.get_or_create(
                title=title, docid=docid, collection=collection)
            doc.active = True
            doc.url = self._get_element_text(root_element, 'meta', 'url')
            doc.type = self._get_element_text(root_element, 'meta', 'type')
            doc.majlang = self._get_element_text(
                root_element, 'meta', 'doclang')
            doc.pubdate = self._get_element_date(
                root_element, 'meta', 'pubdate')

            # publisher
            publisher_name = self._get_element_text(root_element, 'meta', 'publisher')
            if publisher_name:
                publisher, created = Publisher.objects.get_or_create(name=publisher_name)
                doc.publisher = publisher

            # author
            author_name   = self._get_element_text(root_element, 'meta', 'author')
            author_gender = self._get_element_text(root_element, 'meta', 'author1gender')
            parts = author_name.split(',')
            author, created = Author.objects.get_or_create(
                forenames=parts[1].strip(),
                surname=parts[0].strip())
            if author_gender == 'female':
                author.gender = 'f'
            elif author_gender == 'male':
                author.gender = 'm'
            else:
                print 'Unknown gender', author_gender
                exit(0)
            da, exists = Document_Author.objects.get_or_create(author=author, document=doc)

            # genre
            def add_genre(doc, genre):
                genre, exists = Genre.objects.get_or_create(name=genre)
                Document_Genre.objects.get_or_create(genre=genre, document=doc)

            genre1 = self._get_element_text(root_element, 'meta', 'genre1')
            genre2 = self._get_element_text(root_element, 'meta', 'genre2')
            genre3 = self._get_element_text(root_element, 'meta', 'genre3')

            if genre1:
                add_genre(doc, genre1)
            if genre2:
                add_genre(doc, genre2)
            if genre3:
                add_genre(doc, genre3)

            author.save()
            doc.save()

            return doc
        except Exception, e:
            log.error(
                "%s (%s): creating Document for file %s" %
                (type(e).__name__, e.message, self.__current_file))
            connection._rollback()
            exit(0)

        return doc

    def _print_metadata(self, document):
        """ Print out the various metadata values parsed """

        print '\tProcessing metadata:'.upper()
        print '\t- id = %s' % (document.id)
        print '\t- docid = %s' % (document.docid)
        print '\t- title = %s' % (document.title)
        print '\t- url = %s' % (document.url)
        print '\t- pubdate = %s' % (document.pubdate)
        print '\t- collection = %s' % (document.collection)
        print '\t- type = %s' % (document.type)

        publisher = 'None' if document.publisher is None else document.publisher.name
        print '\t- publisher = %s' % publisher

        document_author = Document_Author.objects.get(document=document)
        author = document_author.author
        print '\t- author = %s, %s ' % (author.surname, author.forenames)
        print '\t- majlang = %s' % (document.majlang)

        document_genres = Document_Genre.objects.filter(document=document)
        genres = [da.genre.name for da in document_genres]
        print '\t- genres = %s' % ', '.join(genres)

        return

    def _process_page(self, url, lang, document):
        """
        Create or return existing Page object

        Args:
            url: a String that represents the url of the Page
            lang: a String representing the language of the Page
            document: a Document object

        Returns:
            page: a Page object
        """
        # Create new Page object
        try:
            page, created = Page.objects.get_or_create(
                url=url,
                lang=lang,
                document=document)
        except Exception, e:
            log.error(
                "%s (%s): creating Page <%s> for file %s" %
                (type(e).__name__,
                 e.message,
                 url,
                 self.__current_file))
            connection._rollback()
            exit(0)
            return None
        return page

    def _process_locations(self, root_element, document):
        """
        Parse an Element for LocationMentions

        Method to find all the elements of type 'location' in the XML document
        being parsed and for each one create a LocationMention in the
        database.

        Additionally for each element of type 'location' a lookup of the
        Location entries in the database should be carried out to see if this
        Location already exists. If the Location does exist then the newly
        created LocationMention should be related to this Location. If no
        Location exists then a new Location entry should be created and this
        newly created Location should be related to the LocationMention.

        Args:
            root_element: an elementtree Element object
            document: a Document object

        Returns:
            unique_locations: a list of Location objects
        """
        # Keep track of the unique locations in this document
        unique_locations = []

        # Find all page elements
        pages = root_element.findall(".//page")

        # Find all location elements
        location_elements = \
            root_element.findall("./standoff/ents/ent[@type='location']")

        # Parse each found element
        self.__page_element = 0
        self.__ignored_locations = 0

        all_edinburghs = Location.objects.filter(text='Edinburgh').exclude(id=91)

        for location_element in location_elements:
            gazref = location_element.attrib.get('gazref')

            # ignore locations not in edinburgh
            if gazref == None or not gazref.startswith('pg'):
                continue

            if self.threshold > 0 and isinstance(self.threshold[0], float):
                # check location meets threshold
                i_score = float(location_element.find('./pal-snippet').get('i-score'))
                if i_score < self.threshold[0]:
                    #print 'Ignore ', gazref, ' with i-score of ', i_score
                    self.__ignored_locations = self.__ignored_locations + 1
                    continue

            # Create new LocationMention object
            loc = LocationMention()
            loc.text = location_element.find('./parts/part').text
            lat = location_element.attrib.get('lat')
            lon = location_element.attrib.get('long')

            # Only generate a geom value if lat and lon exist
            if self._is_empty(lat) or self._is_empty(lon):
                lat = lon = geom = None
            else:
                geom = Point(float(lon), float(lat), srid=4326)

            # process mined polygon
            poly = ptype = None
            mined_poly = location_element.attrib.get('polygon')
            if mined_poly:
                latlons = re.findall('[0-9\-]+\.[0-9\-]+ [0-9\-]+\.[0-9\-]+',
                        mined_poly)
                poly_tuple = ()
                for latlon in latlons:
                    poly_tuple += (tuple(map(float,
                        reversed(latlon.split()))),)
                try:
                    poly = Polygon(poly_tuple)
                    ptype = location_element.attrib.get('ptype')
                except Exception, e:
                    log.error(
                        "%s (%s): creating Polygon <%s> for file %s" %
                        (type(e).__name__,
                         e.message,
                         poly_tuple,
                         self.__current_file))
            in_country = location_element.attrib.get('in-country')
            feature_type = location_element.attrib.get('feat-type')
            pop_size = location_element.attrib.get('pop-size')
            pop_size = int(pop_size) \
                if not self._is_empty(pop_size) else None

            try:
                # Get existing or create new Location then add relation
                cleaned_location_text = ' '.join(titlecase(
                    re.sub('[[Ss][Tt]+\.', 'St. ', re.sub(
                        '[\t\n\r]+', ' ', loc.text).lower())).split())
                if cleaned_location_text == 'Edinburgh':
                    loc.location, created = Location.objects.get_or_create(id=random.choice(all_edinburghs).id)
                else:
                    loc.location, created = Location.objects.get_or_create(text=cleaned_location_text)

                if created:
                    loc.location.lat          = lat
                    loc.location.lon          = lon
                    loc.location.geom         = geom
                    loc.location.poly         = poly
                    loc.location.ptype        = ptype
                    loc.location.in_country   = in_country
                    loc.location.gazref       = gazref
                    loc.location.feature_type = feature_type
                    loc.location.pop_size     = pop_size

                    unique_locations.append(loc.text.title())
            except Exception, e:
                # can't get or create Location; don't create LocationMention
                log.error(
                    "%s (%s): creating Location <%s> for file %s" %
                    (type(e).__name__,
                     e.message,
                     loc.text,
                     self.__current_file))
                connection._rollback()
                print e
                exit(0)
            loc.start_word = \
                location_element.find('./parts/part').attrib.get('sw')
            loc.end_word = \
                location_element.find('./parts/part').attrib.get('ew')

            # Find or Create a Page for this mention
            p_id = location_element.attrib.get('p_id')
            if len(pages) == 0:
                page_url = p_id
            else:
                for page in pages:
                    if page.find("p[@id='{0}']".format(p_id)) is not None:
                        page_url = page.attrib.get('url')
                        break;
            page_lang = location_element.attrib.get('p_lang')
            loc.page = self._process_page(page_url, page_lang, document)

            # Find or Create a Sentence for this mention
            palsnip = False # Boolean that flags a snippet as a pal-snippet
            snippet = location_element.find('./pal-snippet')
            if snippet is None:
                snippet = location_element.find('./snippet')
            else:
                palsnip = True
            loc.sentence = self._process_sentence(snippet, loc.page, palsnip)
            location_id = location_element.attrib.get('id')

            # Add Document relation
            loc.document = document

            try:
                loc.save()
                loc.location.save()

                # Keep a track of parsed LocationMentions to enable contruction
                # of Trade relations
                document.parsed_locations[location_id] = loc
            except Exception, e:
                log.error(
                    "%s (%s): creating LocationMention <%s> for file %s" %
                    (type(e).__name__,
                     e.message,
                     location_id,
                     self.__current_file))
                connection._rollback()
                exit(0)

        unique_locations.sort()
        return unique_locations

    def _process_sentence(self, element, page, palsnippet):
        """
        Create or return existing Sentence object

        Args:
            element: snippet element relating to this mention
            page: a Page object
            palsnippet: a Boolean that when True identifies element as a
                        pal-snippet element

        Returns:
            sentence: a Sentence objects
        """

        text = ET.tostring(element, encoding="UTF-8", method="text")
        i_score = element.get("i-score")

        # Get existing or create new sentence object
        try:
            sentence = Sentence.objects.create(
                identifier="", text=text, xml="", page=page, i_score=i_score,
                palsnippet=palsnippet)

            # Parse out parts of speech of interest
            word_elements = element.findall(".//w")
            for word_element in word_elements:
                pos = self.pos.filter(tag=word_element.get('p'))
                if pos:
                    POSMention.objects.create(
                        text = word_element.text,
                        pos = pos[0],
                        sentence = sentence)
        except Exception, e:
            # can't get or create Sentence
            log.error(
                "%s (%s): creating Sentence '<%s>' for file %s" %
                (type(e).__name__,
                 e.message,
                 text,
                 self.__current_file))
            connection._rollback()
            return None

        return sentence

    def _is_empty(self, string):
        """
        Is a string empty?

        Utility function to take a string and determine whether it is None or
        an empty string

        Args:
            string: the string to be analysed

        Returns:
            boolean
        """

        if not string or not len(string) > 0:
            return True
        else:
            return False

    def _get_parent_element(self, root_element, element, tag):
        """
        Traverese up the element tree to find the parent element of the
        element with
        with the tag 'tag'

        Args:
            root_element: the root ElementTree Element
            element: an ElementTree Element
            tag: a string representing the Element tag to find

        Returns:
            parent: the found parent Element instance or None
        """
        parent_element = root_element
        find_string = ".//%s[@id='%s']/.." % (element.tag, element.get('id'))
        while parent_element is not None:
            parent_element = root_element.find(find_string)
            try:
                if parent_element.tag is tag:
                    parent = parent_element
                    parent_element = None
                else:
                    find_string = "%s/.." % find_string
            except:
                continue

        return parent

    def _get_root_element_from_xml(self, filename):
        """
        Open an XML file and determine and return it's root Element

        Args:
            filename: a string representing an XML document filename

        Returns:
            root: the Element instance at the root of the tree
        """
        # Open file as an ElementTree object
        file = os.path.join(self.document_path, filename)
        try:
            tree = ET.parse(file)
        except ET.ParseError, e:
            log.error(
                "%s (%s): file %s" %
                (type(e).__name__, e.message, self.__current_file))
            return
        except IOError, e:
            log.error(
                "%s (%s): file %s" %
                (type(e).__name__, e.message, self.__current_file))
            return
        root = tree.getroot()
        return root

    def _get_element_text(self, root_element, block, element):
        """
        Get the text value for a given Element

        Find the supplied element within the supplied element tree root element
        and return None if the element text is empty or doesn't exist

        Args:
            root_element: an elementtree Element
            block: a string used to filter how the xpath_string is created
            element: a string representing the name attribute of the element
                for which we wish to extract the text

        Returns:
            a string represnting the found text or None if element doesn't
            exist
        """
        xpath_string = ""
        if (block is 'meta'):
            xpath_string = "./meta/attr[@name='%s']" % element
        elif (block is 'part'):
            xpath_string = "./parts/part"
        else:
            return None
        found_element = root_element.find(xpath_string)
        return found_element.text if found_element is not None else None

    def _get_element_date(self, root_element, block, element):
        """
        Get a date value for a given Element

        Find the supplied element within the supplied element tree root element
        and return a python datetime.date representing the found date
        attributes or None if no date attributes are found.

        Args:
            root_element: an elementtree Element
            block: a string used to filter how the xpath_string is created
            element: a string representing the name attribute of the element
                for which we wish to extract the text

        Returns:
            a python datetime.date representing the found date attributes or
            None if no date attributes are found
        """
        xpath_string = ""

        if (block is 'meta'):
            xpath_string = "./meta/attr[@name='%s']" % element
        found_element = root_element.find(xpath_string)
        if found_element is not None:
            # check for valid year; if none found don't return a date
            year_text = found_element.attrib.get("year")
            month = day = 1
            if year_text is not None:
                year = int(year_text.replace('-', '0'))
                if not dt.MINYEAR <= year <= dt.MAXYEAR:
                    log.warn("Year not valid: file %s" %
                             self.__current_file)
                else:
                    # Year valid so see if month and day exist

                    # check for valid month; if invalid set to 1
                    month_text = found_element.attrib.get("month")
                    if month_text is not None:
                        month = int(month_text)
                        if not 1 <= month <= 12:
                            log.warn("Month not valid: file %s" %
                                     self.__current_file)
                            month = 1

                    # check for valid day; if invalid set to 1
                    day_text = found_element.attrib.get("date")
                    if day_text is not None:
                        day = int(day_text)
                        if not 1 <= day <= monthrange(year, month)[1]:
                            log.warn("Day not valid: file %s" %
                                     self.__current_file)
                            day = 1
            else:
                year = self._get_element_text(root_element, 'meta', 'pubdate')
                if year:
                    year = re.sub('(?![0-9]+).', '', year.replace('-','0'))[:4]
                    if year:
                        year = int(year)
                    else:
                        return None
                else:
                    return None
            try:
                return date(year, month, day)
            except ValueError, e:
                log.error(
                    "%s (%s): file %s" %
                    (type(e).__name__, e.message, self.__current_file))
                return None
        else:
            return None


def _get_version():
    """ Return the version number of the parser """
    return VERSION


def _run_parser():
    """
    Process any command line arguements then kick off the parser process.
    """

    # print unicode to std out
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)

    # parse commandline arguments
    arg_parser = argparse.ArgumentParser(
        description='Tool for parsing Palimpsest XML documents')

    arg_parser.add_argument('-v', '--verbose',
                            action='store_true',
                            help='print detailed output')
    arg_parser.add_argument('-V', '--version',
                            action='store_true',
                            help='print parser version')

    parse_group = arg_parser.add_argument_group('Parse Options')
    parse_group.add_argument(
        '-f', '--file',
        help='single XML document to be parsed')
    parse_group.add_argument(
        '-d', '--directory',
        nargs=1,
        help='directory of XML documents to be parsed')
    parse_group.add_argument(
        '-s', '--start',
        default=0,
        type=int,
        help="""Start document to be parsed (only applies to -d). If no start
                page given start from 0.""")
    parse_group.add_argument(
        '-e', '--end',
        default=9999,
        type=int,
        help="""End document to be parsed (only applies to -d), If no end
                document given parse until last.""")
    parse_group.add_argument(
        '-t', '--threshold',
        nargs=1,
        type=float,
        default=None,
        help="""Location confidence threshold, if defined any i-score below this
                value will be ignored by the parser""")

    args = arg_parser.parse_args()

    if args.version:
        print _get_version()
        sys.exit(0)

    if args.directory:
        directory = args.directory[0]
    elif args.file:
        directory = args.file
    else:
        print '*** No file or directory given ***'
        print arg_parser.print_help()
        sys.exit(1)

    #if args.threshold
    # kick off parsing of XML document(s)
    Parser(document_path=directory,
           start=args.start,
           end=args.end,
           verbose=args.verbose,
           threshold=args.threshold).run_parser()

    sys.exit(0)


if __name__ == "__main__":
    """ Execute parser as command line process """

    _run_parser()

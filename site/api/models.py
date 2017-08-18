from django.contrib.gis.db import models


class Collection(models.Model):
    text = models.CharField(max_length=64, null=False)

    def __unicode__(self):
        return self.text

class Publisher(models.Model):
    name = models.TextField(null=False)

class Document(models.Model):
    docid = models.CharField(max_length=96, null=False)
    title = models.TextField(null=False)
    url = models.CharField(max_length=128, null=True, db_column='url')
    pubdate = models.DateField(null=True)
    type = models.CharField(max_length=32, null=True)
    majlang = models.CharField(max_length=3, null=True)
    collection = models.ForeignKey(Collection, null=False, default=0,
            related_name='documents')
    publisher = models.ForeignKey(Publisher, null=True)
    active = models.BooleanField(null=False)

    def __unicode__(self):
        return self.title

    # for use by parser only
    pages = {}
    parsed_locations = {}

class Page(models.Model):
    url = models.URLField(null=True, db_column='url')
    lang = models.CharField(max_length=16, null=True)
    document = models.ForeignKey(Document, null=False, related_name='pages')

    def __unicode__(self):
        return self.identifier


class Sentence(models.Model):
    identifier = models.CharField(max_length=10, null=False)
    text = models.TextField(null=False)
    xml = models.TextField(null=False)
    page = models.ForeignKey(Page, null=False, default=0,
            related_name='sentences')
    i_score = models.FloatField(null=True)
    palsnippet = models.BooleanField(null=False, default=False)

    def __unicode__(self):
        return self.text


class Location(models.Model):
    text = models.CharField(max_length=128, null=False)
    lat = models.FloatField(null=True)
    lon = models.FloatField(null=True)
    geom = models.PointField(null=True, srid=4326, db_column='geom')
    poly = models.PolygonField(null=True, srid=4326, db_column='poly')
    ptype = models.CharField(max_length=32, null=True, db_column='ptype')
    in_country = models.CharField(max_length=2, null=True)
    gazref = models.CharField(max_length=32, null=True)
    feature_type = models.CharField(max_length=32, null=True)
    pop_size = models.BigIntegerField(null=True)
    objects = models.GeoManager()

    def __unicode__(self):
        return self.text


class LocationMention(models.Model):
    text = models.CharField(max_length=128, null=False)
    start_word = models.CharField(max_length=10, null=False)
    end_word = models.CharField(max_length=10, null=False)
    document = models.ForeignKey(Document, null=False, default=0)
    page = models.ForeignKey(Page, null=False, default=0)
    sentence = models.ForeignKey(Sentence, null=False, default=0)
    location = models.ForeignKey(Location, null=False, default=0,
            related_name='location-mentions')

    def __unicode__(self):
        return self.text


class PartOfSpeech(models.Model):
    tag = models.CharField(max_length=4, null=False)
    description = models.CharField(max_length=40, null=True)

    def __unicode__(self):
        return self.description


class POSMention(models.Model):
    text = models.CharField(max_length=128, null=False)
    pos = models.ForeignKey(PartOfSpeech, null=False, default=0)
    sentence = models.ForeignKey(Sentence, null=False, default=0)

    def __unicode__(self):
        return self.text

class Author(models.Model):
    id = models.AutoField(primary_key=True)
    forenames = models.TextField(null=True)
    surname = models.TextField(null=False)
    gender = models.CharField(null=False, default='u')
    link = models.TextField(null=True)
    ol_id = models.CharField(null=True)

    def __unicode__(self):
        return "{0}, {1}".format(self.surname, self.forenames)

class Document_Author(models.Model):
    author = models.ForeignKey(Author, primary_key=True)
    document = models.ForeignKey(Document, primary_key=True)

class Genre(models.Model):
    name = models.TextField(null=False)

class Document_Genre(models.Model):
    genre = models.ForeignKey(Genre, primary_key=True)
    document = models.ForeignKey(Document, primary_key=True)

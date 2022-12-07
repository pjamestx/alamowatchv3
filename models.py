from marshmallow import Schema, fields, post_load
from marshmallow.fields import Nested


class Settings(object):
    def __init__(self, CinemaId, CinemaName, EmailsToNotify, ShortenedUrl, TwitterAccessToken, TwitterAccessSecret):
        self.CinemaId = CinemaId
        self.CinemaName = CinemaName
        self.EmailsToNotify = EmailsToNotify
        self.ShortenedUrl = ShortenedUrl
        self.TwitterAccessToken = TwitterAccessToken
        self.TwitterAccessSecret = TwitterAccessSecret


class Cinema(object):
    def __init__(self, CinemaId, CinemaName, Films=None):
        self.CinemaId = CinemaId
        self.CinemaName = CinemaName
        # dict of film_id and film
        self.Films = Films or []
        self.settings = None

    def __eq__(self, other):
        return self.CinemaId == other.CinemaId

    def __repr__(self):
        return self.CinemaName

    def add_film_if_new(self, film):
        if film not in self.Films:
            self.Films.append(film)


class Film(object):
    def __init__(self, FilmId, FilmName, DateId, AlertSent=False):
        self.FilmId = FilmId
        self.FilmName = FilmName
        self.DateId = DateId
        self.AlertSent = AlertSent

    def __eq__(self, other):
        return self.FilmId == other.FilmId


class SettingsSchema(Schema):
    CinemaId = fields.Str()
    CinemaName = fields.Str()
    EmailsToNotify = fields.List(fields.Str())
    ShortenedUrl = fields.Str()
    TwitterAccessToken = fields.Str()
    TwitterAccessSecret = fields.Str()

    @post_load
    def post_load(self, data, **kwargs):
        return Settings(**data)


class FilmSchema(Schema):
    FilmId = fields.Str()
    FilmName = fields.Str()
    DateId = fields.Str()
    AlertSent = fields.Bool()

    @post_load
    def post_load(self, data, **kwargs):
        return Film(**data)


class CinemaSchema(Schema):
    CinemaId = fields.Str()
    CinemaName = fields.Str()
    Films = fields.List(Nested(FilmSchema))

    @post_load
    def post_load(self, data, **kwargs):
        return Cinema(**data)

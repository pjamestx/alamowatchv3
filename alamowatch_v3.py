import json
import os
import smtplib
import twitter
import logging
import time

from models import Cinema, Film, CinemaSchema, SettingsSchema
from private_keys import TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, GMAIL_USER, GMAIL_PASSWORD
from util import download_json, prepare_film_name

# if set to true, alerts will go to the log file and no data will saved
DEBUG_MODE = True

log_name = 'alamowatchv3-{}.log'.format(time.strftime("%Y%m%d"))
log_name = os.path.join('logs', log_name)

if DEBUG_MODE:
    # write logs to console
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)
else:
    logging.basicConfig(filename=log_name, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

THEATER_DIR = os.path.join(os.getcwd(), 'theaters')
SETTINGS_DIR = os.path.join(os.getcwd(), 'settings')

MARKET_START = 0000
MARKET_END = 2500  # TODO - add automated check above this range and alert if new market is found
MARKET_TEMPLATE = 'https://feeds.drafthouse.com/adcService/showtimes.svc/market/{:04d}/'

#
MAX_TWEET_LENGTH = 125

# ignore these files when loading json files
SKIP_FILES = ['.DS_Store', '_template.json']


class AlamoWatch(object):
    def __init__(self):
        self.cinemas = dict()
        self.Pancake = None

    def load_cinemas(self):
        """
        Loads the cinema json files (containing the history of movies shown at each theater) in the THEATER_DIR
        Populates the `cinemas` collection, along with `Pancake` for Mr. Pancake showings
        """
        schema = CinemaSchema()
        json_files = [f for f in os.listdir(THEATER_DIR) if os.path.isfile(os.path.join(THEATER_DIR, f))]
        for json_file in json_files:
            try:
                if json_file in SKIP_FILES:
                    continue
                with open(os.path.join(THEATER_DIR, json_file), 'r') as fp:
                    logger.info("Loading theater {}".format(json_file))
                    data = json.load(fp)
                    cinema = schema.load(data)
                    self.cinemas[cinema.CinemaId] = cinema
                    if cinema.CinemaName == 'Pancake':
                        self.Pancake = cinema
            except Exception as ex:
                logger.error("Error loading file {}: {}".format(json_file, ex))

    def load_settings(self):
        """
        Loads the settings for each theater, including Twitter credentials and emails to notify
        """
        schema = SettingsSchema()
        json_files = [f for f in os.listdir(SETTINGS_DIR) if os.path.isfile(os.path.join(SETTINGS_DIR, f))]
        for json_file in json_files:
            try:
                if json_file in SKIP_FILES:
                    continue
                with open(os.path.join(SETTINGS_DIR, json_file), 'r') as fp:
                    data = json.load(fp)
                    settings = schema.load(data)
                    cinema = self.cinemas.get(settings.CinemaId)
                    if cinema:
                        cinema.settings = settings
            except Exception as ex:
                logger.error("Error reading settings {}: {}".format(json_file, ex))

    def update_theaters(self):
        """
        Loops through the theaters, gets the latest data from the movie listings, and store them on the appropriate
        objects in the cinemas collection
        """
        for i in range(MARKET_START, MARKET_END, 100):
            url = MARKET_TEMPLATE.format(i)
            logger.info('Processing ' + url)
            payload = download_json(url)
            if payload is None:
                logger.info('No data for url ' + url)
                continue
            market = payload['Market']
            for dates in market['Dates']:
                date_id = dates['DateId']
                for cinema in dates['Cinemas']:
                    cinema_id = cinema['CinemaId']
                    cin = self.cinemas.get(cinema_id)
                    if cin is None:
                        logger.warning(f"Found new theater {cinema['CinemaName']}")
                        cin = Cinema(cinema_id, cinema['CinemaName'])
                        self.cinemas[cinema_id] = cin
                    for film in cinema['Films']:
                        film = Film(film['FilmId'], film['FilmName'], date_id)
                        # adds the film to the cinema, if it doesn't already contain it
                        cin.add_film_if_new(film)
                        # special case, if the movie also has "Master Pancake" in the title, save it here as well
                        if 'Master Pancake' in film.FilmName:
                            self.Pancake.add_film_if_new(film)

    def send_tweets(self, cinema, films):
        """
        Send out tweets for a cinema for the new films that we haven't tweeted about
        Will span multiple tweets for a single theater if necessary
        Sets the "AlertSet" flag on the films as well (unless DEBUG_MODE is enabled)
        """
        if not films:
            return
        template = 'Now On Sale ' + cinema.settings.ShortenedUrl + '\n'
        twitter_buffer = template
        for film in films:
            film_name = prepare_film_name(film.FilmName)
            if len(twitter_buffer + film_name + '\n') > MAX_TWEET_LENGTH:
                self.send_tweet(cinema.settings, twitter_buffer)
                twitter_buffer = template

            twitter_buffer += film_name + '\n'
            if not DEBUG_MODE:
                film.AlertSent = True

        if len(twitter_buffer) > len(template):
            self.send_tweet(cinema.settings, twitter_buffer)

    @staticmethod
    def send_tweet(cinema_settings, payload):
        """
        Sends a single tweet (contained in the payload) using the given Twitter info for the specified cinema
        """
        if DEBUG_MODE:
            logger.debug(f"Sending tweet for {cinema_settings.CinemaName}: {payload}")
            return

        api = twitter.Api(consumer_key=TWITTER_CONSUMER_KEY,
                          consumer_secret=TWITTER_CONSUMER_SECRET,
                          access_token_key=cinema_settings.TwitterAccessToken,
                          access_token_secret=cinema_settings.TwitterAccessSecret,
                          sleep_on_rate_limit=True)
        logger.info('{}: {}'.format(cinema_settings.CinemaName, payload))
        try:
            ret = api.PostUpdate(payload)
        except Exception as ex:
            logger.error('Failed to send tweet {}: {}'.format(len(payload), payload))
            raise ex

    def send_emails(self, cinema, films):
        """
        If the cinema is configured to send emails, then compose and send an email about the new films
        """
        if not films:
            return
        email_buffer = 'Now On Sale at ' + cinema.settings.ShortenedUrl + '\n'
        for film in films:
            email_buffer += '{}\t{}\n'.format(film.DateId, prepare_film_name(film.FilmName))
        self.send_email(cinema.settings, email_buffer)

    @staticmethod
    def send_email(cinema_settings, payload):
        """
        Sends an email (contained in payload) using the given cinema's details
        """
        if not cinema_settings.EmailsToNotify:
            return
        if DEBUG_MODE:
            logger.debug(f"Sending email for {cinema_settings.CinemaName}: {payload}")
            return

        # TODO: could do this with comma-separated email addresses
        for to_addr in cinema_settings.EmailsToNotify:
            # SMTP_SSL Example
            server_ssl = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server_ssl.ehlo()  # optional, called by login()
            server_ssl.login(GMAIL_USER, GMAIL_PASSWORD)
            # ssl server doesn't support or need tls, so don't call server_ssl.starttls()
            message = "From: AlamoWatch ({})\nTo: {}\nSubject: [AlamoWatch] Now On Sale at {}\n\n{}"\
                .format(GMAIL_USER, to_addr, cinema_settings.CinemaName, payload)
            server_ssl.sendmail(GMAIL_USER, to_addr, message)
            # server_ssl.quit()
            server_ssl.close()

    @staticmethod
    def write_theater(cinema):
        """
        Saves the cinema json for the specified theater
        """
        if DEBUG_MODE:
            logger.debug("DEBUG_MODE is true, not saving theater info")
            return

        schema = CinemaSchema()
        file_name = os.path.join(THEATER_DIR, cinema.CinemaName) + '.json'
        with open(file_name, 'w') as fp:
            foo = schema.dump(cinema)
            fp.write(json.dumps(foo, sort_keys=True, indent=4))

    def run(self):
        """
        Main entry point
        Loads data/settings, pulls down new movie listings, sends tweets/emails for new movies
        """
        self.load_cinemas()
        self.load_settings()
        self.update_theaters()
        for cinema in self.cinemas.values():
            try:
                if cinema.settings is None:
                    logger.warning("No settings found for {}".format(cinema.CinemaName))
                    continue
                films = [x for x in cinema.Films if not x.AlertSent]
                self.send_tweets(cinema, films)
                self.send_emails(cinema, films)
                self.write_theater(cinema)
            except Exception as ugh:
                logger.error("Exception: {}".format(ugh))


if __name__ == "__main__":
    aw = AlamoWatch()
    try:
        aw.run()
    except Exception as run_ex:
        logger.error("Exception: {}".format(run_ex))

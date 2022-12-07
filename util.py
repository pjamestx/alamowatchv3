import requests
from titlecase import titlecase


def download_json(url):
    """
    Returns json response if a 200 status was received, empty string otherwise
    """
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.json()
    return ''


def prepare_film_name(film_name):
    """
    Formats film name into title case, makes a few simple replacements, and truncates strings over 90 char long
    """
    ret = titlecase(film_name)
    ret = ret.replace('2d ', '2D ')
    ret = ret.replace('3d ', '3D ')

    # make sure it's not too long
    if len(ret) > 90:
        ret = ret[:87] + '...'
    return ret

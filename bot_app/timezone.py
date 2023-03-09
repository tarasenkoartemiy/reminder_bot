from requests import ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError, get
from datetime import datetime


def getting_coordinates(city: str):
    nominatim_api_link = "https://nominatim.openstreetmap.org/search?"
    try:
        if not (response := get(nominatim_api_link, params={"q": city, "limit": 1, "format": "json"}).json()):
            return False
    except (ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError) as coordinates_exception:
        print(coordinates_exception)
        return None

    def getting_timezone():
        time_api_link = "https://www.timeapi.io/api/Time/current/coordinate?"
        lat = response[0].get("lat")
        lon = response[0].get("lon")
        try:
            return get(time_api_link, params={"latitude": lat, "longitude": lon}).json()["timeZone"]
        except (ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError) as timezone_exception:
            print(timezone_exception)
            return None
        except KeyError:
            return False

    return getting_timezone


def is_time_format(value: str):
    try:
        datetime.strptime(value, '%H:%M')
        return True
    except ValueError:
        return False

from datetime import datetime
import requests


def getting_coordinates(city: str):
    nominatim_api_link = "https://nominatim.openstreetmap.org/search?"
    try:
        if not (response := requests.get(nominatim_api_link, params={"q": city, "limit": 1, "format": "json"}).json()):
            return False
    except requests.exceptions:
        return None

    def getting_timezone():
        time_api_link = "https://www.timeapi.io/api/Time/current/coordinate?"
        lat = response[0]["lat"]
        lon = response[0]["lon"]
        try:
            return requests.get(time_api_link, params={"latitude": lat, "longitude": lon}).json()["timeZone"]
        except requests.exceptions:
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

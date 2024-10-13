import csv, pytz, io, requests, os
from datetime import datetime
from dotenv import load_dotenv

class ArchiveIndices:
    YEAR = 0
    MONTH = 1
    TITLE = 4
    CHANNEL = 5
    ALT_LINK = 8

# TODO remove the below classes and make the variables part of
# the scheduler classes since they are different in each
class ScheduleIndices:
    TITLE = 0
    ID = 1
    TIMESTAMP = 2

class Indicators:
    GAP_CHILD_COUNT = 2

load_dotenv()

# Retrieve environment variables
instance_url = os.getenv("instance_url")
access_token = os.getenv("access_token")

default_tz = "US/Eastern"
default_hr_type = "AM"

visibility = "public"

archive: list = None
schedules: dict[str, list] = {"DailyT10": [], "General": []}


def fetch_schedules(selected_timezone):
    """Set the global 'schedule' variable with the csv data obtained by making a get request to the actual archive"""
    global schedules

    auth_header = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"https://{instance_url}/api/v1/scheduled_statuses?limit=40&max_id=999999", headers=auth_header)
    schedule_chunk = response.json()
    
    schedule: list = schedule_chunk

    while len(schedule_chunk) == 40:
        response = requests.get(response.links["next"]["url"], headers=auth_header)
        schedule_chunk = response.json()
        schedule.extend(schedule_chunk)

    schedule.sort(key=lambda entry: entry["scheduled_at"], reverse=True)

    daily_t10_indicator = "The randomly selected top pony video of the day is"
    
    # Yep, 2 passes, but I also dislike the thought of a pure python loop and i'm too lazy to benchmark it
    schedules["DailyT10"] = [
        {
            "title": post["params"]["text"].split(": \"", 1)[1].split("\" from \"", 1)[0],
            "post_id": post["id"],
            "scheduled_time": pytz.utc.localize(datetime.strptime(post["scheduled_at"], "%Y-%m-%dT%H:%M:%S.%fZ")).astimezone(selected_timezone)
        } for post in schedule[::-1] if daily_t10_indicator in post["params"]["text"]
    ]

    schedules["General"] = [
        {
            "post_id": post["id"],
            "content": post["params"]["text"],
            "scheduled_time": pytz.utc.localize(datetime.strptime(post["scheduled_at"], "%Y-%m-%dT%H:%M:%S.%fZ")).astimezone(selected_timezone)
        } for post in schedule if daily_t10_indicator not in post["params"]["text"]
    ]
 
def fetch_archive():
    """Set the global 'archive' variable using the csv data obtained by making a get request to the actual archive"""
    global archive

    csv_str: str = requests.get("https://docs.google.com/spreadsheets/d/1rEofPkliKppvttd8pEX8H6DtSljlfmQLdFR-SlyyX7E/export?format=csv").content.decode()
    reader = csv.reader(io.StringIO(csv_str))

    archive = [entry for entry in reader if "[BLACKLIST]" not in entry[ArchiveIndices.CHANNEL]]
    del archive[0] # remove header

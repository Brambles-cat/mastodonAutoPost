import csv #csv file handling
import random #randomizing post selection
import time #time stuff
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, timezone #time stuff
from mastodon import Mastodon #mastodon post gen
import os # dot environment variables
from dotenv import load_dotenv #dot environment variables
import calendar #displaying month as name
from constants import ArchiveIndices as ARC_I, ScheduleIndices as SCH_I
import tkinter as tk #UI
from tkinter import ttk #UI
import threading #UI
import pytz  #timezone handling
import io
import requests

load_dotenv()

# Retrieve environment variables
instance_url = os.getenv("instance_url")
access_token = os.getenv("access_token")

archive = None

# These are also the default values
prev_selected_tz = "US/Eastern"
prev_selected_hr_type = "AM"

mastodon = Mastodon(
    access_token=access_token,
    api_base_url=instance_url
)

# For whatever reason a version error is raised when not connected to the internet instead of a connection error idk why
if mastodon.retrieve_mastodon_version() == "1.0.0":
    print("\033[93m", "Couldn't connect to Mastodon", "\033[00m")
    quit()

def fetch_archive():
    """Initialize the global 'archive' variable with the csv data obtained by making a get request to the actual archive"""
    global archive

    csv_str: str = requests.get("https://docs.google.com/spreadsheets/d/1rEofPkliKppvttd8pEX8H6DtSljlfmQLdFR-SlyyX7E/export?format=csv").content.decode()

    reader = csv.reader(io.StringIO(csv_str))
    archive = [entry for entry in reader if "[BLACKLIST]" not in entry[5]] # 5 is the channel index

    del archive[0] # remove header

    if not archive:
        print("\033[93m", "No eligible videos found in the CSV file", "\033[00m")
        quit()

def create_post_message(video_data: list):
    """Create the message that will be used for the mastodon post with the provided video data"""
    
    title = video_data[4]
    channel = video_data[5]
    numeric_month = int(video_data[1])
    month_name = calendar.month_name[numeric_month]
    year = video_data[0]
    alternatelink = video_data[8]

    message = f'The randomly selected top pony video of the day is: "{title}" from "{channel}" from {month_name} {year}:\n{alternatelink}'
    return message

def schedule_mastodon_post(message, scheduled_time_utc):
    scheduled_time = datetime.fromtimestamp(scheduled_time_utc, tz=timezone.utc)
    response = mastodon.status_post(message, scheduled_at=scheduled_time, visibility='public')

    return response.id

def bulk_post_to_mastodon(num_posts, scheduled_time: datetime):
    for i in range(num_posts):
        random_video = random.choice(archive)
        message = create_post_message(random_video)

        scheduled_time_utc = int(scheduled_time.timestamp())
        post_id = schedule_mastodon_post(message, scheduled_time_utc)
        add_schedule_row(random_video[4], post_id, scheduled_time)

        print(f'Post {i + 1} scheduled on Mastodon for {str(scheduled_time)[:-9]}.')
        
        scheduled_time += timedelta(days=1)
        time.sleep(1)

def get_base_scheduled_time():
    """Get the next time that a video should be scheduled determined
    by the latest currently scheduled post if any"""

    rows = schedule_rows_frame.winfo_children()
    selected_timezone = pytz.timezone(timezone_combo.get())
    hour, minute = int(hour_entry.get()), int(minute_entry.get())

    hour = (hour % 12) + 12 if am_pm_combo.get() == "PM" else hour % 12 if am_pm_combo.get() == "AM" else hour

    if len(rows) == 0:
        current_time = datetime.now(tz=selected_timezone)
        scheduled_time = current_time.replace(hour=hour, minute=minute, second=0)

        return scheduled_time + timedelta(days=1) if (scheduled_time - current_time).total_seconds() <= 0 else scheduled_time
    
    prev_scheduled_time = selected_timezone.localize(
        datetime.strptime(rows[-1].winfo_children()[2].cget("text"), "%Y-%m-%d %H:%M" if am_pm_combo.get() == "24 hr" else "%Y-%m-%d %I:%M %p")
    )
    
    scheduled_time = prev_scheduled_time.replace(hour=hour, minute=minute, second=0)
    
    # Return same time next day if the scheduled time already passed
    return scheduled_time + timedelta(days=1) if (scheduled_time - prev_scheduled_time).total_seconds() <= 0 else scheduled_time

def last_day_of_month(date: datetime):
    return date.replace(day=calendar.monthrange(date.year, date.month)[1])

def init_schedule_rows(rows: list[dict[str, any]]):
    """Initialize the schedule display with a list of rows sorted from oldest to newest."""
    
    # The rows here are added to the display such a way
    # that the latest sheduled posts appear at the top
    # while the order in scheduled_rows_frame.winfo_children()
    # is oldest first latest last
    # This is important because newly scheduled rows are added only to the
    # end of the list meaning the way the latest row is accessed would
    # otherwise differ between the initialization and normal phases

    if len(rows) == 0:
        return

    schedule_data = []

    now = datetime.now(tz=pytz.timezone(timezone_combo.get())) # TODO adjust for currently selected time

    gap_amount = (rows[0]["scheduled_time"] - now).days

    for i in range(len(rows) - 1):
        if gap_amount > 1:
            schedule_data.append(gap_amount - 1)

        schedule_data.append(rows[i])

        gap_amount = (rows[i + 1]["scheduled_time"] - rows[i]["scheduled_time"]).days

    if gap_amount - 1 > 1:
        schedule.append(gap_amount - 1)

    schedule_data.append(rows[-1])

    row_index = len(schedule_data)

    for data in schedule_data:
        row_index -= 1

        if isinstance(data, int):
            frame = tk.Frame(schedule_rows_frame, highlightbackground="gray", highlightthickness=1, pady=5)
            tk.Label(frame, text=f"{data} day gap").pack()
            frame.grid(row=row_index, sticky="ew")
            continue

        frame = tk.Frame(schedule_rows_frame, highlightbackground="gray", highlightthickness=1, pady=5)
        frame.grid(row=row_index, sticky="ew")

        title_label = tk.Label(frame, text=data["title"], width=20, wraplength=150)
        title_label.pack(side="left")

        id_label = tk.Label(frame, text=data["post_id"], width=5)
        id_label.pack(side="left", padx=5)
        
        time_label = tk.Label(frame, width=18, text =
            data["scheduled_time"].strftime("%Y-%m-%d %I:%M %p") if am_pm_combo.get() != "24 hr" else data["scheduled_time"].strftime("%Y-%m-%d %H:%M")
        )
        time_label.pack(side="left", padx=5)

        reroll_button = tk.Button(frame, text="Re-Roll", command=lambda row=frame: reroll(row), state=tk.DISABLED)
        reroll_button.pack(side="left", padx=5)
        
        remove_button = tk.Button(frame, text="Remove", command=lambda row=frame: remove_row(row))
        remove_button.pack(side="left", padx=5)

def add_schedule_row(title, post_id, schedule_time: datetime):
    for row in schedule_rows_frame.winfo_children():
        row.grid_configure(row=row.grid_info()["row"] + 1)
        
    row_frame = tk.Frame(schedule_rows_frame, highlightbackground="gray", highlightthickness=1, pady=5)
    row_frame.grid(row=0, sticky="ew")
    
    title_label = tk.Label(row_frame, text=title, width=20, wraplength=150)
    title_label.pack(side="left")

    id_label = tk.Label(row_frame, text=post_id, width=5)
    id_label.pack(side="left", padx=5)

    time_label_text = schedule_time.astimezone(tz=pytz.timezone(timezone_combo.get()))
    time_label_text = time_label_text.strftime("%Y-%m-%d %I:%M %p") if am_pm_combo.get() != "24 hr" else time_label_text.strftime("%Y-%m-%d %H:%M")
    
    time_label = tk.Label(row_frame, text=time_label_text, width=18)
    time_label.pack(side="left", padx=5)

    reroll_button = tk.Button(row_frame, text="Re-Roll", command=lambda row=row_frame: reroll(row), state=tk.DISABLED)
    reroll_button.pack(side="left", padx=5)
    
    remove_button = tk.Button(row_frame, text="Remove", command=lambda row=row_frame: remove_row(row))
    remove_button.pack(side="left", padx=5)

def ordinal_suffix(num):
    suffixes = {1: 'st', 2: 'nd', 3: 'rd'}

    return 'th' if 11 <= num <= 13 else suffixes.get(num % 10, 'th')

def update_gap(gap: tk.Frame, second_gap: tk.Frame = None):
    gap_days = int(gap.winfo_children()[0].cget("text").split(" ")[0])

    if second_gap:
        gap2_days = int(second_gap.winfo_children()[0].cget("text").split(" ")[0])
        return gap.winfo_children()[0].config(text=f"{gap_days + 1 + gap2_days} day gap")
    
    gap.winfo_children()[0].config(text=f"{gap_days + 1} day gap")

def fix_row_nums(row_index):
    rows = schedule_rows_frame.winfo_children()

    for i in range(row_index):
        # - 1 since rows is already shortened by having them being destroyed
        rows[i].grid_configure(row=len(rows) - i - 1)

def create_gap(row: tk.Frame):
    for child in row.winfo_children(): # RIP childs
        child.destroy()
    
    label = tk.Label(row, text="1 day gap")
    label.pack()

# Tkinter UI functions
def generate_posts():
    if not archive:
        fetch_archive()

    base_time = get_base_scheduled_time()
    time_units = time_units_combo.get().lower()

    num_posts = int(posts_entry.get())

    if time_units == "weeks":
        num_posts *= 7
    elif time_units == "*months":
        end_date = last_day_of_month(base_time + relativedelta(months=num_posts - 1))
        num_posts = (end_date - base_time).days + 1

    generate_button["state"] = tk.DISABLED

    def run_generate_posts():
        bulk_post_to_mastodon(num_posts, base_time)
        posts_entry_updated(None)
        generate_button["state"] = "normal"

    generation_thread = threading.Thread(target=run_generate_posts)
    generation_thread.start()

def clamp_min(e):
    minutes = minute_entry.get()
    minute_entry.delete(0, tk.END)

    try:
        minutes = min(59, max(0, int(minutes)))
    except:
        return minute_entry.insert(0, "00")
    
    minute_entry.insert(0, f"0{minutes}" if minutes < 10 else minutes)

def clamp_hour(e):
    hour = hour_entry.get()
    hour_entry.delete(0, tk.END)
    hr_24 = am_pm_combo.get().lower() == "24 hr"

    try:
        hour = min(23 if hr_24 else 12, max(0, int(hour)))
        assert hr_24 or hour != 0
    except:
        return hour_entry.insert(0, "00" if hr_24 else "12")
    
    hour_entry.insert(0, f"0{hour}" if hour < 10 else hour)

def posts_entry_updated(e):
    amount = posts_entry.get()
    posts_entry.delete(0, tk.END)

    try:
        amount = int(amount)
    except:
        posts_entry.insert(0, 1)
    
    units = time_units_combo.get().lower()
    
    # Yes, that 10 at the end is me being lazy. I don't give a flying feather about datetimes anymore
    posts_entry.insert(0, min(300 if units == "days" else 42 if units == "weeks" else 10, max(1, amount)))

    # update amount to clamped value
    amount = int(posts_entry.get())
    base_time = get_base_scheduled_time()

    # Apparently removing trailing 0s with strftime might work differently across os's

    if amount == 1 and units == "days":
        return range_details_label.config(text=f"Scheduling for {base_time.strftime("%b")} {base_time.day}{ordinal_suffix(base_time.day)}")

    to = last_day_of_month(base_time + relativedelta(months=amount - 1)) if units == "*months" else base_time + timedelta(days=(amount if units == "days" else amount * 7) - 1)

    range_details_label.config(
        text=f"Scheduling from {base_time.strftime("%b")} {base_time.day}{ordinal_suffix(base_time.day)} to {to.strftime("%b")} {to.day}{ordinal_suffix(to.day)}"
    )

def remove_row(row: tk.Frame):
    schedule_rows = schedule_rows_frame.winfo_children()
    row_count = len(schedule_rows)

    # Weird index since first row is last child and last row is first child
    # due to reversed insertion order
    row_index = row_count - row.grid_info()["row"] - 1
    
    mastodon.scheduled_status_delete(row.winfo_children()[1].cget("text"))
    
    if row_count == 1:
        return row.destroy()

    if row_index + 1 == len(schedule_rows): # First row     
        row.destroy()   
        gap_below = len(schedule_rows[row_index - 1].winfo_children()) == 1

        if gap_below:
            schedule_rows[row_index - 1].destroy()

        if row_count == 2: return
        
        return fix_row_nums(row_index - 1 if gap_below else row_index)

    elif row_index == 0: # Last row
        if len(schedule_rows[1].winfo_children()) == 1:
            update_gap(schedule_rows[row_index - 1])
            row.destroy()
        else:
            create_gap(row)
        return


    lower_gap, upper_gap = len(schedule_rows[row_index - 1].winfo_children()) == 1, len(schedule_rows[row_index + 1].winfo_children()) == 1
    
    if upper_gap and lower_gap:
       update_gap(schedule_rows[row_index - 1], schedule_rows[row_index + 1])
       schedule_rows[row_index + 1].destroy()
       row.destroy()
       return fix_row_nums(row_index)
    
    if not (upper_gap or lower_gap):
        return create_gap(row)
    else:
        update_gap(schedule_rows[row_index + (1 if upper_gap else -1)])
        row.destroy()
        fix_row_nums(row_index)

def changed_timezone(e):
    global prev_selected_tz

    if timezone_combo.get() == prev_selected_tz: return

    prev_tz, selected_tz = pytz.timezone(prev_selected_tz), pytz.timezone(timezone_combo.get())
    hr_24 = am_pm_combo.get() == "24 hr"

    for row in schedule_rows_frame.winfo_children():
        data = row.winfo_children()

        if len(data) == 1: continue

        old_time = prev_tz.localize(datetime.strptime(data[2].cget("text"), "%Y-%m-%d %H:%M" if hr_24 else "%Y-%m-%d %I:%M %p"))
        data[2].config(text=old_time.astimezone(selected_tz).strftime("%Y-%m-%d %H:%M" if hr_24 else "%Y-%m-%d %I:%M %p"))
    
    prev_selected_tz = timezone_combo.get()

def changed_hour_type(e):
    global prev_selected_hr_type
    
    if am_pm_combo.get() == prev_selected_hr_type: return

    clamp_hour(None)
    prev_hr_24, curr_hr_24 = prev_selected_hr_type == "24 hr", am_pm_combo.get() == "24 hr"

    for row in schedule_rows_frame.winfo_children():
        data = row.winfo_children()

        if len(data) == 1: continue

        old_time = datetime.strptime(data[2].cget("text"), "%Y-%m-%d %H:%M" if prev_hr_24 else "%Y-%m-%d %I:%M %p")
        data[2].config(text=old_time.strftime("%Y-%m-%d %H:%M" if curr_hr_24 else "%Y-%m-%d %I:%M %p"))
    
    prev_selected_hr_type = am_pm_combo.get()

def select_all(e: tk.Event):
    e.widget.select_range(0, tk.END)
    e.widget.icursor(0)

def on_frame_configure(e):
    canvas.configure(scrollregion=canvas.bbox("all"))

def reroll(row: tk.Frame):
    if not archive:
        fetch_archive()
    
    widgets = row.winfo_children()
    mastodon.scheduled_status_delete(widgets[SCH_I.ID].cget("text"))
    random_video = random.choice(archive)
    message = create_post_message(random_video)
    scheduled_time = datetime.strptime(widgets[SCH_I.TIMESTAMP].cget("text"), "%Y-%m-%d %H:%M" if am_pm_combo.get() == "24 hr" else "%Y-%m-%d %I:%M %p")

    new_id = schedule_mastodon_post(message, int(scheduled_time.timestamp()))

    widgets[SCH_I.TITLE].config(text=random_video[ARC_I.TITLE])
    widgets[SCH_I.ID].config(text=new_id)

# UI Window
root = tk.Tk()
root.geometry("625x650")
root.title("Mastodon Post Generator")

posts_label = tk.Label(root, text="Schedule videos for the next:")
posts_label.pack(pady=5)

posts_frame = tk.Frame(root)
posts_frame.pack()

posts_entry = tk.Entry(posts_frame)
posts_entry.insert(0, 1)
posts_entry.bind("<Return>", posts_entry_updated)
posts_entry.bind("<FocusOut>", posts_entry_updated)
posts_entry.grid(row=0, column=0, padx=(0, 10))

time_units_combo = ttk.Combobox(posts_frame, values=["Days", "Weeks", "*Months"], width=8, state="readonly")
time_units_combo.set("Days")
time_units_combo.bind("<<ComboboxSelected>>", posts_entry_updated)
time_units_combo.grid(row=0, column=1)

range_details_label = tk.Label(root)
range_details_label.pack()

scheduled_time_label = tk.Label(root, text="Enter scheduled time")
scheduled_time_label.pack(pady=(15, 0))

time_frame = tk.Frame(root)
time_frame.pack()

hour_label = tk.Label(time_frame, text="Hour")
hour_label.grid(row=0, column=0, padx=4)
hour_entry = tk.Entry(time_frame, width=6)
hour_entry.insert(0, 12)
hour_entry.bind("<Return>", clamp_hour)
hour_entry.bind("<FocusOut>", clamp_hour)
hour_entry.bind("<FocusIn>", select_all)
hour_entry.grid(row=1, column=0, padx=4)

separator_label = tk.Label(time_frame, text=":")
separator_label.grid(row=1, column=1, padx=4)

minute_label = tk.Label(time_frame, text="Minute")
minute_label.grid(row=0, column=2, padx=4)
minute_entry = tk.Entry(time_frame, width=6)
minute_entry.insert(0, "00")
minute_entry.bind("<Return>", clamp_min)
minute_entry.bind("<FocusOut>", clamp_min)
minute_entry.bind("<FocusIn>", select_all)
minute_entry.grid(row=1, column=2, padx=4)

am_pm_combo = ttk.Combobox(time_frame, values=["AM", "PM", "24 hr"], width=5, state="readonly")
am_pm_combo.set(prev_selected_hr_type)
am_pm_combo.bind("<<ComboboxSelected>>", changed_hour_type)
am_pm_combo.grid(row=1, column=3, padx=4)

timezone_label = tk.Label(root, text="Select timezone:")
timezone_label.pack(pady=10)
timezone_combo = ttk.Combobox(root, values=pytz.all_timezones, state="readonly")
timezone_combo.set(prev_selected_tz)
timezone_combo.bind("<<ComboboxSelected>>", changed_timezone)
timezone_combo.pack()

generate_button = tk.Button(root, text="Generate Posts", command=generate_posts)
generate_button.pack(pady=10)

scroll_frame = tk.Frame(root, borderwidth=5, highlightthickness=2, highlightbackground="gray")
scroll_frame.pack(fill="y", expand=True)

canvas = tk.Canvas(scroll_frame, height=300, width=465)
canvas.pack(side="left", fill="both", expand=True)

schedule_rows_frame = tk.Frame(canvas)
schedule_rows_frame.bind("<Configure>", on_frame_configure)

scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
scrollbar.pack(side="right", fill="y")

canvas.create_window((0, 0), window=schedule_rows_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

auth_header = {"Authorization": f"Bearer {access_token}"}
response = requests.get(f"https://{instance_url}/api/v1/scheduled_statuses?limit=40&max_id=999999", headers=auth_header)
schedule_chunk = response.json()

# Having the actul schedule may make some previous
# code getting data from the rows redundant
# Might revisit later
schedule: list = schedule_chunk

temp_timezone = pytz.timezone(prev_selected_tz)

while len(schedule_chunk) == 40:
    response = requests.get(response.links["next"]["url"], headers=auth_header)
    schedule_chunk = response.json()
    schedule.extend(schedule_chunk)

init_schedule_rows([
    {
        "title": post["params"]["text"].split(": \"", 1)[1].split("\" from \"" ,1)[0],
        "post_id": post["id"],
        "scheduled_time": pytz.utc.localize(datetime.strptime(post["scheduled_at"], "%Y-%m-%dT%H:%M:%S.%fZ")).astimezone(temp_timezone)
    } for post in schedule[::-1]
])

del temp_timezone

if len(schedule_rows_frame.winfo_children()):
    hr_24 = am_pm_combo.get() == "24 hr";

    date = datetime.strptime(schedule_rows_frame.winfo_children()[-1].winfo_children()[2].cget("text"), "%Y-%m-%d %H:%M" if am_pm_combo.get() == "24 hr" else "%Y-%m-%d %I:%M %p")
    hour_entry.delete(0, tk.END)

    if hr_24:
        hour_entry.insert(0, f"0{date.hour}" if date.hour < 10 else date.hour)
    else:
        am_pm_combo.set("AM" if date.hour < 12 else "PM")
        hr_12 = 12 if date.hour == 0 else date.hour if date.hour <= 12 else date.hour - 12
        hour_entry.insert(0, f"0{hr_12}" if hr_12 < 10 else hr_12)

    minute_entry.delete(0, tk.END)
    minute_entry.insert(0, f"0{date.minute}" if date.minute < 10 else date.min)

posts_entry_updated(None)

root.mainloop()

# TODO
# Re-roll - unschedule row's video, then schedule a new one at the same date and replace row data
# not available if it's scheduled within 5 minutes in the future

# Each unscheduled time period row should have a generate button to fill in the gap with random vids

# When creating a gap for the bottom entry in the schedule, take selected time into consideration for displaying gap length

# Display rate limit counter and time until refresh, allow much quicker scheduling up until the limit is reached
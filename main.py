from data import fetch_schedules, access_token, instance_url, default_tz
from schedulers import DailyT10Scheduler, GeneralScheduler
from mastodon import Mastodon
from tkinter.font import Font
import tkinter as tk
import pytz, data


mastodon = Mastodon(
    access_token=access_token,
    api_base_url=instance_url
)

# For whatever reason a version error is raised when not connected to the internet instead of a connection error idk why
if mastodon.retrieve_mastodon_version() == "1.0.0":
    print("\033[93m", "Couldn't connect to Mastodon", "\033[00m")
    quit()

# The objects used to change the ui between daily t10 and general scheduing
daily_t10_scheduling, general_scheduling = DailyT10Scheduler(mastodon), GeneralScheduler(mastodon)

# Initialize the schedules variable in data.py
fetch_schedules(pytz.timezone(default_tz))


def change_scheduling_type(s1, s2, s3):
    for widget in scheduler_container.winfo_children():
        widget.destroy()

    if post_type_var.get():
        daily_t10_scheduling.set_active(scheduler_container)
    else:
        general_scheduling.set_active(scheduler_container)

def toggle_visibility():
    data.visibility = "public" if data.visibility == "private" else "private"
    visibility_button.config(text=data.visibility)


# UI Window
root = tk.Tk()
root.geometry("625x650")
root.title("Mastodon Post Generator")

scheduler_container = tk.Frame()
scheduler_container.pack()

daily_t10_scheduling.set_active(scheduler_container)

settings_frame = tk.Frame(root)
settings_frame.place(x=5, y=0)

post_type_frame = tk.Frame(settings_frame)
post_type_frame.pack()

post_type_label = tk.Label(post_type_frame, text="Post Type:")
post_type_label.pack()

post_type_var = tk.BooleanVar(value=True)
post_type_var.trace_add("write", change_scheduling_type)

t10_radio_button = tk.Radiobutton(post_type_frame, text="Daily T10", variable=post_type_var, value=True, indicatoron=0, width=7, padx=2, pady=1, font=Font(size=9))
t10_radio_button.pack(side="left")

general_radio_button = tk.Radiobutton(post_type_frame, text="General", variable=post_type_var, value=False, indicatoron=0, width=7, padx=2, pady=1, font=Font(size=9))
general_radio_button.pack()

visibility_frame = tk.Frame(settings_frame)
visibility_frame.pack()

visibility_label = tk.Label(visibility_frame, text="Visibility:")
visibility_label.pack()

visibility_button = tk.Button(visibility_frame, text=data.visibility, font=Font(size=9), width=7, padx=2, pady=1, command=toggle_visibility)
visibility_button.pack()

root.mainloop()

# TODO
# Display rate limit counter and time until refresh, allow much quicker scheduling up until the limit is reached

# Highlighting pattern to indicate when rows have multiple videos scheduled on the same day
# Although this is unlikely for any day after the current current day (or perhaps visibility)

# If the post to schedule is within 5 mins of current time only, schedule for the next day

# Refresh buttons for archive and scheduled mastodon posts

# Display pub/priv visibility on schedule rows with an option to change (delete then reschedule with changed setting)

# For genreral scheduling, add emoji support, other visibility options, media attachments, sensitivity option, maybe even custom emoji

# Switch id and content positions in schedule rows and allow more space for long content posts

# The more I look at it, the more schdulers.py looks like it could really use some
# untangling, more abstraction, and general cleaning up, since it was kind of built with bad foundations

# Also the date entry has no safe guards against past dates and should also dynamically update
# to offset the date by 1 if it's on the current day AND the selected time is in te past
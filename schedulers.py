import random, time, calendar, pytz, threading, data
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date, time as dt_time
from data import ArchiveIndices as ARC_I, ScheduleIndices as SCH_I, Indicators as IND
from data import default_tz, default_hr_type
from mastodon import Mastodon
from tkinter.font import Font
from tkinter import ttk
import tkinter as tk
import tkcalendar


prev_selected_tz = default_tz
prev_selected_hr_type = default_hr_type


def last_day_of_month(date: datetime):
    return date.replace(day=calendar.monthrange(date.year, date.month)[1])

def ordinal_suffix(num):
    suffixes = {1: 'st', 2: 'nd', 3: 'rd'}

    return 'th' if 11 <= num <= 13 else suffixes.get(num % 10, 'th')


class Scheduler:
    def __init__(self, mastodon: Mastodon):
        self.mastodon = mastodon

    def _on_frame_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _init_schedule_rows_frame(self, ui_container):
        scroll_frame = tk.Frame(ui_container, borderwidth=5, highlightthickness=2, highlightbackground="gray")
        scroll_frame.pack(fill="y", expand=True)

        self.canvas = tk.Canvas(scroll_frame, height=300, width=405)
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.schedule_rows_frame = tk.Frame(self.canvas)
        self.schedule_rows_frame.bind("<Configure>", self._on_frame_configure)

        scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        
        self.canvas.create_window((0, 0), window=self.schedule_rows_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
    
    def _changed_timezone(self, e):
        global prev_selected_tz

        if self.timezone_combo.get() == prev_selected_tz: return

        prev_tz, selected_tz = pytz.timezone(prev_selected_tz), pytz.timezone(self.timezone_combo.get())
        hr_24 = self.am_pm_combo.get() == "24 hr"

        for row in self.schedule_rows_frame.winfo_children():
            row_data = row.winfo_children()

            if len(row_data) == IND.GAP_CHILD_COUNT: continue

            old_time = prev_tz.localize(datetime.strptime(row_data[2].cget("text"), "%Y-%m-%d %H:%M" if hr_24 else "%Y-%m-%d %I:%M %p"))
            row_data[2].config(text=old_time.astimezone(selected_tz).strftime("%Y-%m-%d %H:%M" if hr_24 else "%Y-%m-%d %I:%M %p"))
        
        prev_selected_tz = self.timezone_combo.get()

    def _changed_hour_type(self, e):
        global prev_selected_hr_type
        
        if self.am_pm_combo.get() == prev_selected_hr_type: return

        self._clamp_hour(None)
        prev_hr_24, curr_hr_24 = prev_selected_hr_type == "24 hr", self.am_pm_combo.get() == "24 hr"

        for row in self.schedule_rows_frame.winfo_children():
            row_data = row.winfo_children()

            if len(row_data) == IND.GAP_CHILD_COUNT: continue

            old_time = datetime.strptime(row_data[2].cget("text"), "%Y-%m-%d %H:%M" if prev_hr_24 else "%Y-%m-%d %I:%M %p")
            row_data[2].config(text=old_time.strftime("%Y-%m-%d %H:%M" if curr_hr_24 else "%Y-%m-%d %I:%M %p"))
        
        prev_selected_hr_type = self.am_pm_combo.get()

    def _select_all(self, e: tk.Event):
        e.widget.select_range(0, tk.END)
        e.widget.icursor(0)

    def _add_schedule_row(self, text, post_id, schedule_time: datetime):
        for row in self.schedule_rows_frame.winfo_children():
            row.grid_configure(row=row.grid_info()["row"] + 1)
            
        row_frame = tk.Frame(self.schedule_rows_frame, highlightbackground="gray", highlightthickness=1, pady=5)
        row_frame.grid(row=0, sticky="ew")
        
        title_label = tk.Label(row_frame, text=text, width=20, wraplength=150)
        title_label.pack(side="left")

        id_label = tk.Label(row_frame, text=post_id, width=5)
        id_label.pack(side="left", padx=5)

        time_label_text = schedule_time.astimezone(tz=pytz.timezone(self.timezone_combo.get()))
        time_label_text = time_label_text.strftime("%Y-%m-%d %I:%M %p") if self.am_pm_combo.get() != "24 hr" else time_label_text.strftime("%Y-%m-%d %H:%M")
        
        time_label = tk.Label(row_frame, text=time_label_text, width=18)
        time_label.pack(side="left", padx=5)
        
        remove_button = tk.Button(row_frame, text="Remove", command=lambda row=row_frame: self._remove_row(row))
        remove_button.pack(side="left", padx=5)

    def _fix_row_nums(self, row_index):
        rows = self.schedule_rows_frame.winfo_children()

        for i in range(row_index):
            # - 1 since rows is already shortened by having them being destroyed
            rows[i].grid_configure(row=len(rows) - i - 1)

    def _schedule_mastodon_post(self, message, scheduled_time: datetime):
        response = self.mastodon.status_post(message, scheduled_at=scheduled_time, visibility=data.visibility)

        return response.id
    
    def _clamp_min(self, e):
        minutes = self.minute_entry.get()
        self.minute_entry.delete(0, tk.END)

        try:
            minutes = min(59, max(0, int(minutes)))
        except:
            return self.minute_entry.insert(0, "00")
        
        self.minute_entry.insert(0, f"0{minutes}" if minutes < 10 else minutes)

    def _clamp_hour(self, e):
        hour = self.hour_entry.get()
        self.hour_entry.delete(0, tk.END)
        hr_24 = self.am_pm_combo.get().lower() == "24 hr"

        try:
            hour = min(23 if hr_24 else 12, max(0, int(hour)))
            assert hr_24 or hour != 0
        except:
            return self.hour_entry.insert(0, "00" if hr_24 else "12")
        
        self.hour_entry.insert(0, f"0{hour}" if hour < 10 else hour)

    def _insert_scheduler_components(self, ui_container: tk.Frame):
        scheduled_time_label = tk.Label(ui_container, text="Enter scheduled time")
        scheduled_time_label.pack(pady=(15, 0))

        time_frame = tk.Frame(ui_container)
        time_frame.pack()

        hour_label = tk.Label(time_frame, text="Hour")
        hour_label.grid(row=0, column=0, padx=4)
        self.hour_entry = tk.Entry(time_frame, width=6)
        self.hour_entry.insert(0, 12)
        self.hour_entry.bind("<Return>", self._clamp_hour)
        self.hour_entry.bind("<FocusOut>", self._clamp_hour)
        self.hour_entry.bind("<FocusIn>", self._select_all)
        self.hour_entry.grid(row=1, column=0, padx=4)

        separator_label = tk.Label(time_frame, text=":")
        separator_label.grid(row=1, column=1, padx=4)

        minute_label = tk.Label(time_frame, text="Minute")
        minute_label.grid(row=0, column=2, padx=4)
        self.minute_entry = tk.Entry(time_frame, width=6)
        self.minute_entry.insert(0, "00")
        self.minute_entry.bind("<Return>", self._clamp_min)
        self.minute_entry.bind("<FocusOut>", self._clamp_min)
        self.minute_entry.bind("<FocusIn>", self._select_all)
        self.minute_entry.grid(row=1, column=2, padx=4)

        self.am_pm_combo = ttk.Combobox(time_frame, values=["AM", "PM", "24 hr"], width=5, state="readonly")
        self.am_pm_combo.set(prev_selected_hr_type)
        self.am_pm_combo.bind("<<ComboboxSelected>>", self._changed_hour_type)
        self.am_pm_combo.grid(row=1, column=3, padx=4)

        tz_frame = tk.Frame(ui_container)
        tz_frame.pack(pady=8)

        timezone_label = tk.Label(tz_frame, text="Select timezone:")
        timezone_label.grid(row=0, sticky="w")
        self.timezone_combo = ttk.Combobox(tz_frame, values=pytz.all_timezones, state="readonly")
        self.timezone_combo.set(prev_selected_tz)
        self.timezone_combo.bind("<<ComboboxSelected>>", self._changed_timezone)
        self.timezone_combo.grid(row=1)


class DailyT10Scheduler(Scheduler):
    def _remove_row(self, row: tk.Frame):
        schedule_rows = self.schedule_rows_frame.winfo_children()
        row_count = len(schedule_rows)

        # Weird index since first row is last child and last row is first child
        # due to reversed insertion order
        row_index = row_count - row.grid_info()["row"] - 1
        post_id = row.winfo_children()[1].cget("text")
        
        self.mastodon.scheduled_status_delete(post_id)
        del data.schedules["DailyT10"][row_index - len([row for row in schedule_rows if len(row.winfo_children()) == IND.GAP_CHILD_COUNT])]
        
        if row_count == 1:
            row.destroy()
            return self._posts_entry_updated(None)

        if row_index + 1 == len(schedule_rows): # First row     
            row.destroy()
            gap_below = len(schedule_rows[row_index - 1].winfo_children()) == IND.GAP_CHILD_COUNT

            if gap_below:
                schedule_rows[row_index - 1].destroy()

            self._posts_entry_updated(None)

            if row_count == 2: return
            
            return self._fix_row_nums(row_index - 1 if gap_below else row_index)

        elif row_index == 0: # Last row
            if len(schedule_rows[1].winfo_children()) == IND.GAP_CHILD_COUNT:
                self._update_gap(schedule_rows[1])
                row.destroy()
            else:
                self._create_gap(row)
            return


        lower_gap = len( schedule_rows[row_index - 1].winfo_children()) == IND.GAP_CHILD_COUNT
        upper_gap = len(schedule_rows[row_index + 1].winfo_children()) == IND.GAP_CHILD_COUNT
        
        if upper_gap and lower_gap:
            self._update_gap(schedule_rows[row_index - 1], schedule_rows[row_index + 1])
            schedule_rows[row_index + 1].destroy()
            row.destroy()
            return self._fix_row_nums(row_index)
        
        if not (upper_gap or lower_gap):
            return self._create_gap(row)
        else:
            self._update_gap(schedule_rows[row_index + (1 if upper_gap else -1)])
            row.destroy()
            self._fix_row_nums(row_index)

    def _posts_entry_updated(self, e):
        amount = self.posts_entry.get()
        self.posts_entry.delete(0, tk.END)

        try:
            amount = int(amount)
        except:
            self.posts_entry.insert(0, 1)
        
        units = self.time_units_combo.get().lower()
        
        # Yes, that 10 at the end is me being lazy. I don't give a flying feather about datetimes anymore
        self.posts_entry.insert(0, min(300 if units == "days" else 42 if units == "weeks" else 10, max(1, amount)))

        # update amount to clamped value
        amount = int(self.posts_entry.get())
        base_time = self._get_base_scheduled_time()

        # Apparently removing trailing 0s with strftime might work differently across os's

        if amount == 1 and units == "days":
            return self.range_details_label.config(text=f"Scheduling for {base_time.strftime("%b")} {base_time.day}{ordinal_suffix(base_time.day)}")

        to = last_day_of_month(base_time + relativedelta(months=amount - 1)) if units == "*months" else base_time + timedelta(days=(amount if units == "days" else amount * 7) - 1)

        self.range_details_label.config(
            text=f"Scheduling from {base_time.strftime("%b")} {base_time.day}{ordinal_suffix(base_time.day)} to {to.strftime("%b")} {to.day}{ordinal_suffix(to.day)}"
        )

    def _update_gap(self, gap: tk.Frame, second_gap: tk.Frame = None):
        gap_days = int(gap.winfo_children()[0].cget("text").split(" ")[0])

        if second_gap:
            gap2_days = int(second_gap.winfo_children()[0].cget("text").split(" ")[0])
            return gap.winfo_children()[0].config(text=f"{gap_days + 1 + gap2_days} day gap")
        
        gap.winfo_children()[0].config(text=f"{gap_days + 1} day gap")

    def _fill_gap(self, gap: tk.Frame):
        pass

    def _init_schedule_rows(self, rows: list[dict[str, any]]):
        """Initialize the schedule display with a list of rows sorted from oldest to newest."""
        
        # The rows here are added to the display in such a way
        # that the latest scheduled posts appear at the top
        # while the order in scheduled_rows_frame.winfo_children()
        # is oldest first latest last
        # This is important because newly scheduled rows are added only to the
        # end of the list meaning the way the latest row is accessed would
        # otherwise differ between the initialization and normal phases

        if len(rows) == 0:
            return

        schedule_data = []

        now = datetime.now(tz=pytz.timezone(self.timezone_combo.get())) # TODO adjust for currently selected time
        selected_timezone = pytz.timezone(self.timezone_combo.get())

        gap_amount = (rows[0]["scheduled_time"] - now).days

        for i in range(len(rows) - 1):
            if gap_amount > 1:
                schedule_data.append(gap_amount - 1)

            schedule_data.append(rows[i])

            gap_amount = (rows[i + 1]["scheduled_time"] - rows[i]["scheduled_time"]).days

        if gap_amount - 1 > 1:
            schedule_data.append(gap_amount - 1)

        schedule_data.append(rows[-1])

        row_index = len(schedule_data)

        for row_data in schedule_data:
            row_index -= 1

            frame = tk.Frame(self.schedule_rows_frame, highlightbackground="gray", highlightthickness=1, pady=5)
            frame.grid(row=row_index, sticky="ew")

            if isinstance(row_data, int):
                frame.grid_columnconfigure(0, weight=1)
                tk.Label(frame, text=f"{row_data} day gap").grid(row=0, column=0)
                tk.Button(frame, text="Fill", width=6, command=lambda gap=frame: self._fill_gap(gap)).grid(row=0, column=1, padx=5, sticky="e")
                continue

            title_label = tk.Label(frame, text=row_data["title"], width=20, wraplength=150)
            title_label.pack(side="left")

            id_label = tk.Label(frame, text=row_data["post_id"], width=5)
            id_label.pack(side="left", padx=5)
            
            # TODO move this in _changed_timezone
            row_data["scheduled_time"] = row_data["scheduled_time"].astimezone(selected_timezone)

            time_label = tk.Label(frame, width=18, text =
                row_data["scheduled_time"].strftime("%Y-%m-%d %I:%M %p") if self.am_pm_combo.get() != "24 hr" else row_data["scheduled_time"].strftime("%Y-%m-%d %H:%M")
            )
            time_label.pack(side="left", padx=5)
            
            remove_button = tk.Button(frame, text="Remove", command=lambda row=frame: self._remove_row(row))
            remove_button.pack(side="left", padx=5)

    def _create_gap(self, row: tk.Frame):
        for child in row.winfo_children(): # RIP childs
            child.destroy()
        
        row.grid_columnconfigure(0, weight=1)
        tk.Label(row, text="1 day gap").grid(row=0, column=0)
        tk.Button(row, text="Fill", width=6, command=lambda gap=row: self._fill_gap(gap)).grid(row=0, column=1, padx=5, sticky="e")


    def _get_base_scheduled_time(self):
        """Get the next time that a video should be scheduled determined
        by the latest currently scheduled post if any"""

        rows = self.schedule_rows_frame.winfo_children()
        selected_timezone = pytz.timezone(self.timezone_combo.get())
        hour, minute = int(self.hour_entry.get()), int(self.minute_entry.get())

        hour = (hour % 12) + 12 if self.am_pm_combo.get() == "PM" else hour % 12 if self.am_pm_combo.get() == "AM" else hour

        if len(rows) == 0:
            current_time = datetime.now(tz=selected_timezone)
            scheduled_time = current_time.replace(hour=hour, minute=minute, second=0)

            return scheduled_time + timedelta(days=1) if (scheduled_time - current_time).total_seconds() <= 0 else scheduled_time
        
        prev_scheduled_time = selected_timezone.localize(
            datetime.strptime(rows[-1].winfo_children()[2].cget("text"), "%Y-%m-%d %H:%M" if self.am_pm_combo.get() == "24 hr" else "%Y-%m-%d %I:%M %p")
        )
        
        scheduled_time = prev_scheduled_time.replace(hour=hour, minute=minute, second=0)
        
        # Return same time next day if the scheduled time already passed
        return scheduled_time + timedelta(days=1) if (scheduled_time - prev_scheduled_time).total_seconds() <= 0 else scheduled_time

    def _bulk_post_to_mastodon(self, num_posts, scheduled_time: datetime):
        for i in range(num_posts):
            random_video = random.choice(data.archive)
            message = self._create_post_message(random_video)

            post_id = self._schedule_mastodon_post(message, scheduled_time)

            self._add_schedule_row(random_video[ARC_I.TITLE], post_id, scheduled_time)
            data.schedules["DailyT10"].append(
                {
                    "title": random_video[ARC_I.TITLE],
                    "post_id": post_id,
                    "scheduled_time": scheduled_time
                }
            )

            print(f'Post {i + 1} scheduled on Mastodon for {str(scheduled_time)[:-9]}.')
            
            scheduled_time += timedelta(days=1)
            time.sleep(1)

    def _create_post_message(self, video_data: list):
        """Create the message that will be used for the mastodon post with the provided video data"""
        
        title = video_data[4]
        channel = video_data[5]
        numeric_month = int(video_data[1])
        month_name = calendar.month_name[numeric_month]
        year = video_data[0]
        alternatelink = video_data[8]

        message = f'The randomly selected top pony video of the day is: "{title}" from "{channel}" from {month_name} {year}:\n{alternatelink}'
        return message

    def _generate_posts(self):
        if not data.archive:
            data.fetch_archive()

        base_time = self._get_base_scheduled_time()
        time_units = self.time_units_combo.get().lower()

        num_posts = int(self.posts_entry.get())

        if time_units == "weeks":
            num_posts *= 7
        elif time_units == "*months":
            end_date = last_day_of_month(base_time + relativedelta(months=num_posts - 1))
            num_posts = (end_date - base_time).days + 1

        self.generate_button["state"] = tk.DISABLED

        def run_generate_posts():
            self._bulk_post_to_mastodon(num_posts, base_time)
            self._posts_entry_updated(None)
            self.generate_button["state"] = "normal"

        generation_thread = threading.Thread(target=run_generate_posts)
        generation_thread.start()
    
    def _min_updated(self, e):
        self._clamp_min(e)
        self._posts_entry_updated(None)

    def _hr_updated(self, e):
        self._clamp_hour(e)
        self._posts_entry_updated(None)
    
    def _hr_type_updated(self, e):
        self._changed_hour_type(e)
        self._posts_entry_updated(None)
    
    def _tz_updated(self, e):
        self._changed_timezone(e)
        self._posts_entry_updated(None)

    def set_active(self, ui_container: tk.Frame):
        posts_label = tk.Label(ui_container, text="Schedule videos for the next:")
        posts_label.pack(pady=5)

        posts_frame = tk.Frame(ui_container)
        posts_frame.pack()

        self.posts_entry = tk.Entry(posts_frame)
        self.posts_entry.insert(0, 1)
        self.posts_entry.bind("<Return>", self._posts_entry_updated)
        self.posts_entry.bind("<FocusOut>", self._posts_entry_updated)
        self.posts_entry.grid(row=0, column=0, padx=(0, 10))

        self.time_units_combo = ttk.Combobox(posts_frame, values=["Days", "Weeks", "*Months"], width=8, state="readonly")
        self.time_units_combo.set("Days")
        self.time_units_combo.bind("<<ComboboxSelected>>", self._posts_entry_updated)
        self.time_units_combo.grid(row=0, column=1)

        self.range_details_label = tk.Label(ui_container)
        self.range_details_label.pack()

        self._insert_scheduler_components(ui_container)

        # Add additional functionality to these so that the displayed time range stays accurate
        self.minute_entry.bind("<Return>", self._min_updated)
        self.minute_entry.bind("<FocusOut>", self._min_updated)

        self.hour_entry.bind("<Return>", self._hr_updated)
        self.hour_entry.bind("<FocusOut>", self._hr_updated)

        self.am_pm_combo.bind("<<ComboboxSelected>>", self._hr_type_updated)
        self.timezone_combo.bind("<<ComboboxSelected>>", self._tz_updated)

        self.generate_button = tk.Button(ui_container, text="Generate Posts", command=self._generate_posts)
        self.generate_button.pack(pady=10)

        self._init_schedule_rows_frame(ui_container)

        self._init_schedule_rows(data.schedules["DailyT10"])
        
        # Make the input fields' initial values match those of the latest scheduled item
        if len(self.schedule_rows_frame.winfo_children()):
            hr_24 = self.am_pm_combo.get() == "24 hr";

            date = datetime.strptime(self.schedule_rows_frame.winfo_children()[-1].winfo_children()[2].cget("text"), "%Y-%m-%d %H:%M" if self.am_pm_combo.get() == "24 hr" else "%Y-%m-%d %I:%M %p")
            self.hour_entry.delete(0, tk.END)

            if hr_24:
                self.hour_entry.insert(0, f"0{date.hour}" if date.hour < 10 else date.hour)
            else:
                self.am_pm_combo.set("AM" if date.hour < 12 else "PM")
                hr_12 = 12 if date.hour == 0 else date.hour if date.hour <= 12 else date.hour - 12
                self.hour_entry.insert(0, f"0{hr_12}" if hr_12 < 10 else hr_12)

            self.minute_entry.delete(0, tk.END)
            self.minute_entry.insert(0, f"0{date.minute}" if date.minute < 10 else date.minute)

        self._posts_entry_updated(None)


class GeneralScheduler(Scheduler):
    def _init_schedule_rows(self, schedule_data: list[dict[str, any]]):
        """Initialize the schedule display with the general schedule sorted from oldest to newest."""

        if len(schedule_data) == 0:
            return

        row_index = len(schedule_data)
        selected_timezone = pytz.timezone(self.timezone_combo.get())

        for row_data in schedule_data:
            row_index -= 1

            frame = tk.Frame(self.schedule_rows_frame, highlightbackground="gray", highlightthickness=1, pady=5)
            frame.grid(row=row_index, sticky="ew")

            content_label = tk.Label(frame, text=row_data["content"], width=20, wraplength=150)
            content_label.pack(side="left")

            id_label = tk.Label(frame, text=row_data["post_id"], width=5)
            id_label.pack(side="left", padx=5)

            # TODO move this in _changed_timezone
            row_data["scheduled_time"] = row_data["scheduled_time"].astimezone(selected_timezone)
            
            time_label = tk.Label(frame, width=18, text =
                row_data["scheduled_time"].strftime("%Y-%m-%d %I:%M %p") if self.am_pm_combo.get() != "24 hr" else row_data["scheduled_time"].strftime("%Y-%m-%d %H:%M")
            )
            time_label.pack(side="left", padx=5)
            
            remove_button = tk.Button(frame, text="Remove", command=lambda row=frame: self._remove_row(row))
            remove_button.pack(side="left", padx=5)

    def _schedule_general_post(self):
        scheduled_time: date = self._schedule_date_entry.get_date()

        hour = int(self.hour_entry.get())
        hour = (hour % 12) + 12 if self.am_pm_combo.get() == "PM" else hour % 12 if self.am_pm_combo.get() == "AM" else hour

        time_component = dt_time(hour, int(self.minute_entry.get()))
        scheduled_time = datetime.combine(date=scheduled_time, time=time_component)
        scheduled_time = pytz.timezone(self.timezone_combo.get()).localize(scheduled_time)

        content = self._content_entry.get("1.0", tk.END)
        post_id = self._schedule_mastodon_post(content, scheduled_time)

        scheduled_timestamp = scheduled_time.timestamp()
        i = next((i for i, entry_data in enumerate(data.schedules["General"]) if entry_data["scheduled_time"].timestamp() > scheduled_timestamp), len(data.schedules["General"]))

        self._add_schedule_row(content, post_id, scheduled_time)

        data.schedules["General"].insert(i, {
            "post_id": post_id,
            "content": content,
            "scheduled_time": scheduled_time
        })

    def _remove_row(self, row: tk.Frame):
        schedule_rows = self.schedule_rows_frame.winfo_children()
        row_count = len(schedule_rows)
        
        row_index = row_count - row.grid_info()["row"] - 1
        post_id = row.winfo_children()[SCH_I.ID].cget("text")

        self.mastodon.scheduled_status_delete(post_id)
        del data.schedules["General"][row_index]
        
        row.destroy()
        
        if row_count != 1:
            self._fix_row_nums(row_index)

    def set_active(self, ui_container: tk.Frame):
        self._insert_scheduler_components(ui_container)

        date_input_frame = tk.Frame(ui_container)
        date_input_frame.pack(pady=3)

        date_input_label = tk.Label(date_input_frame, text="Schedule Date:")
        date_input_label.grid(row=0, sticky="w")
        self._schedule_date_entry = tkcalendar.DateEntry(date_input_frame, state="readonly")
        self._schedule_date_entry.set_date(self._schedule_date_entry.get_date() + timedelta(days=1))
        self._schedule_date_entry.grid(row=1)

        content_frame = tk.Frame(ui_container)
        content_frame.pack()

        content_label = tk.Label(content_frame, text="Text Content:", font=Font(size=10))
        content_label.grid(row=0, sticky="w")

        self._content_entry = tk.Text(content_frame, width=55, height=7, font=("Helvetica", 12))
        self._content_entry.grid(row=1)

        schedule_button = tk.Button(ui_container, text="Schedule Post", command=self._schedule_general_post)
        schedule_button.pack(pady=10)

        self._init_schedule_rows_frame(ui_container)
        self._init_schedule_rows(data.schedules["General"])

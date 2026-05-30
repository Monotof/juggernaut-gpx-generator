# -*- coding: utf-8 -*-
"""
Juggernaut GPX Generator
"""

import datetime
import json
import locale
import os
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
import xml.etree.ElementTree as ET

from geographiclib.geodesic import Geodesic
from tkinter import filedialog, messagebox, simpledialog, ttk

import geohashing


locale.setlocale(locale.LC_ALL, "")


# %% BASIC FUNCTIONS
def indent(elem, level=0):
    """Pretty-print XML tree indentation."""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def parse_coordinates(text):
    """Parse decimal coordinates or geohashing graticule input."""
    text = text.strip()

    norm = text.replace(",", ".")
    nums = re.findall(r"-?\d+\.\d+", norm)

    # decimal coordinate input
    if len(nums) >= 2:
        return (float(nums[0]), float(nums[1])), False

    parts = text.split()

    try:
        # date + graticule
        if len(parts) == 3:
            date_str, lat_str, lon_str = parts

            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            lat = int(lat_str)
            lon = int(lon_str)

        # graticule only
        elif len(parts) == 2:
            lat = int(parts[0])
            lon = int(parts[1])
            date = datetime.date.today()

        else:
            return None, None

        gh_lat, gh_lon = geohashing.geohash(lat, lon, date=date)
        return (gh_lat, gh_lon), True

    except Exception:
        return None, None


def center_window(parent, child):
    """Center child window over parent."""
    parent.update_idletasks()
    child.update_idletasks()

    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()

    cw = child.winfo_width()
    ch = child.winfo_height()

    x = px + (pw // 2) - (cw // 2)
    y = py + (ph // 2) - (ch // 2)

    child.geometry(f"+{x}+{y}")

# %% POINT STORAGE
def get_appdata_dir():
    """Return application data directory."""
    if sys.platform.startswith("win"):
        base = os.getenv("APPDATA")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.path.expanduser("~/.config")

    app_dir = os.path.join(base, "juggernaut_gpx")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


POINTS_FILE = os.path.join(get_appdata_dir(), "saved_points.json")


def load_saved_points():
    """Load saved points from disk."""
    if not os.path.exists(POINTS_FILE):
        return {}

    try:
        with open(POINTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}


def save_points_dict(data):
    with open(POINTS_FILE, "w", encoding="utf-8") as f:
    """Save points dictionary to disk."""
        json.dump(data, f, indent=2)


# %% APPLICATION STATE
track_rows = []

app_state = {
    "start_coords": None,
    "end_coords": None,
    "start_valid": False,
    "end_valid": False,
    "factor": None,
    "factor_valid": False,
    "has_tracks": False,
    "can_generate_boundary": False,
    "can_generate_stack_only": False,
}


# %% GEODESIC
def compute_closed_offset_track(lat1, lon1, lat2, lon2, limit, circle_detail = 15):
    """Generate juggernaut boundary polygon."""
    geod = Geodesic.WGS84

    inv = geod.Inverse(lat1, lon1, lat2, lon2)
    total_dist = inv["s12"]
    azi1 = inv["azi1"]
    azi2 = inv["azi2"]

    max_segments = 500
    base_step = 2000

    n_segments = int(total_dist / base_step)
    if n_segments > max_segments:
        n_segments = max_segments

    step = total_dist / max(n_segments, 1)

    line = geod.Line(lat1, lon1, azi1)

    left_points = []
    right_points = []

    for i in range(n_segments + 1):
        d = min(i * step, total_dist)
        pos = line.Position(d)

        lat = pos["lat2"]
        lon = pos["lon2"]
        azi = pos["azi2"]

        left = geod.Direct(lat, lon, azi - 90, limit)
        right = geod.Direct(lat, lon, azi + 90, limit)

        left_points.append((left["lat2"], left["lon2"]))
        right_points.append((right["lat2"], right["lon2"]))

    def arc(center_lat, center_lon, start_azi, sweep, radius, segments):
        pts = []
        step = sweep / segments
        for i in range(segments + 1):
            azi = start_azi + i * step
            p = geod.Direct(center_lat, center_lon, azi, radius)
            pts.append((p["lat2"], p["lon2"]))
        return pts

    start_q1 = arc(lat1, lon1, azi1 + 180,  90, limit, circle_detail)
    start_q2 = arc(lat1, lon1, azi1 +  90,  90, limit, circle_detail)
    end_half = arc(lat2, lon2, azi2 -  90, 180, limit, (circle_detail * 2) - 1)

    track = []
    track.extend(start_q1)
    track.extend(left_points[1:])
    track.extend(end_half[1:])
    track.extend(reversed(right_points[:-1]))
    track.extend(start_q2[1:])

    return track


def compute_center_line(lat1, lon1, lat2, lon2):
    """Generate straight center line."""
    geod = Geodesic.WGS84
    inv = geod.Inverse(lat1, lon1, lat2, lon2)
    total_dist = inv["s12"]
    azi1 = inv["azi1"]

    line = geod.Line(lat1, lon1, azi1)

    points = []
    for i in range(21):
        d = i * total_dist / 20
        pos = line.Position(d)
        points.append((pos["lat2"], pos["lon2"]))

    return points


def compute_point_deviation(geod, line, lat1, lon1, lat, lon):
    """Compute perpendicular deviation from center line."""
    inv_pt = geod.Inverse(lat1, lon1, lat, lon)

    s = inv_pt["s12"]
    azi = inv_pt["azi1"]

    pos = line.Position(s)

    # perpendicular distance
    deviation = geod.Inverse(pos["lat2"], pos["lon2"], lat, lon)["s12"]

    # determine side
    left = ((azi - pos["azi2"] + 360) % 360) > 180

    return deviation, left


# %% GPX
def create_track(name, points, color):
    """Create GPX track element."""
    trk = ET.Element("trk")
    ET.SubElement(trk, "name").text = name

    ext = ET.SubElement(trk, "extensions")
    style = ET.SubElement(ext, "gpx_style:line")
    ET.SubElement(style, "gpx_style:color").text = color
    line = ET.SubElement(style, "line", xmlns="http://www.topografix.com/GPX/gpx_style/0/2")
    ET.SubElement(line, "color").text = color

    seg = ET.SubElement(trk, "trkseg")

    for lat, lon in points:
        ET.SubElement(seg, "trkpt", lat=str(lat), lon=str(lon))

    return trk


def create_waypoint(lat, lon, name):
    """Create GPX waypoint element."""
    wpt = ET.Element(
        "wpt",
        lat=str(lat),
        lon=str(lon)
    )

    ET.SubElement(wpt, "name").text = name

    return wpt


def load_gpx_segments(filepath):
    """Load all GPX track segments."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
    segments = root.findall(".//gpx:trkseg", ns)

    all_points = []
    for seg in segments:
        points = []
        for pt in seg.findall("gpx:trkpt", ns):
            points.append((float(pt.get("lat")), float(pt.get("lon"))))
        if points:
            all_points.append(points)

    return all_points


# %% STATE / UI
def get_valid_factor():
    """Return valid deviation factor or None."""
    try:
        factor = float(factor_entry.get())

        return factor if factor > 0 else None

    except ValueError:
        return None


def refresh_app_state():
    """Refresh parsed input state."""
    start_coords, _ = parse_coordinates(
        entry1.get()
    )

    end_coords, _ = parse_coordinates(
        entry2.get()
    )

    factor = get_valid_factor()

    app_state["start_coords"] = start_coords
    app_state["end_coords"] = end_coords

    app_state["start_valid"] = (
        start_coords is not None
    )

    app_state["end_valid"] = (
        end_coords is not None
    )

    app_state["factor"] = factor

    app_state["factor_valid"] = (
        factor is not None
    )

    app_state["has_tracks"] = any(
        r["file"] for r in track_rows
    )

    app_state["can_generate_boundary"] = all([
        app_state["start_valid"],
        app_state["end_valid"],
        app_state["factor_valid"],
    ])

    app_state["can_generate_stack_only"] = (
        app_state["has_tracks"]
    )

    refresh_ui_state()


def update_info_label():
    """Update distance/deviation info label."""
    if not app_state["can_generate_boundary"]:

        if app_state["can_generate_stack_only"]:
            info_label.config(
                text="Stack-only GPX generation mode"
            )

        else:
            info_label.config(
                text=(
                    "Total distance: --- km     "
                    "Deviation Limit: --- m"
                )
            )

        return

    geod = Geodesic.WGS84

    inv = geod.Inverse(
        app_state["start_coords"][0],
        app_state["start_coords"][1],
        app_state["end_coords"][0],
        app_state["end_coords"][1],
    )

    distance = inv["s12"]

    limit = distance / app_state["factor"]

    distance_km = locale.format_string(
        "%.2f",
        distance / 1000,
        grouping=True
    )

    limit_m = locale.format_string(
        "%.0f",
        limit,
        grouping=True
    )

    info_label.config(
        text=(
            f"Total distance: {distance_km} km     "
            f"Deviation Limit: {limit_m} m"
        )
    )


def refresh_ui_state():
    """Refresh button and widget states."""
    points_exist = bool(load_saved_points())

    start_save_btn.config(
        state=(
            "normal"
            if app_state["start_valid"]
            else "disabled"
        )
    )

    end_save_btn.config(
        state=(
            "normal"
            if app_state["end_valid"]
            else "disabled"
        )
    )

    start_load_btn.config(
        state=(
            "normal"
            if points_exist
            else "disabled"
        )
    )

    end_load_btn.config(
        state=(
            "normal"
            if points_exist
            else "disabled"
        )
    )

    can_generate = (
        app_state["can_generate_boundary"]
        or app_state["can_generate_stack_only"]
    )

    generate_btn.config(
        state=(
            "normal"
            if can_generate
            else "disabled"
        )
    )

    calc_state = (
        "normal"
        if app_state["can_generate_boundary"]
        else "disabled"
    )

    for row in track_rows:
        if "calc_btn" in row and row["file"]:
            row["calc_btn"].config(
                state=calc_state
            )

    update_info_label()


def update_preview(entry, label):
    """Update coordinate parsing preview."""
    coords, _ = parse_coordinates(
        entry.get()
    )

    if coords:
        label.config(
            text=(
                f"Parsed: "
                f"{coords[0]:.6f}, "
                f"{coords[1]:.6f}"
            )
        )

    else:
        label.config(text="Invalid input")

    refresh_app_state()


# %% GUI TRACK ROW
def add_track_row():
    """Add tracklog row."""
    row = {}

    frame = tk.Frame(tracks_container)
    frame.pack(fill="x", anchor="w", padx=20, pady=4)
    
    controls_frame = tk.Frame(frame)

    controls_frame.pack(fill="x")

    btn = tk.Button(controls_frame, text="Add Tracklog", width=16)
    btn.pack(side="left")

    color_entry = tk.Entry(controls_frame, width=8)
    color_entry.insert(0, "0000ff")

    use_btn = tk.Button(controls_frame, text="Use start/end from this")
    calc_btn = tk.Button(controls_frame, text="Calculate juggernaut", state="disabled")

    filename_var = tk.StringVar()
    filename_label = tk.Label(frame, textvariable=filename_var, anchor="w")


    row["file"] = None
    row["color"] = color_entry
    row["filename"] = filename_var
    row["frame"] = frame
    row["calc_btn"] = calc_btn

    def remove_row():
        frame.destroy()

        track_rows.remove(row)

        if not any(r["file"] is None for r in track_rows):
            add_track_row()

        refresh_app_state()

    def choose_file():
        file = filedialog.askopenfilename(filetypes=[("GPX files", "*.gpx")])
        if not file:
            return

        row["file"] = file
        filename_var.set(os.path.basename(file))

        color_entry.pack(side="left", padx=5)
        use_btn.pack(side="left", padx=5)
        calc_btn.pack(side="left", padx=5)
        filename_label.pack(side="left", fill="x", expand=True, padx=5)

        btn.config(text="Remove Tracklog", command=remove_row)

        if track_rows[-1] is row:
            add_track_row()

        refresh_app_state()

    def use_points():
        """Use track endpoints as start/end."""
        if not row["file"]:
            return

        tracks = load_gpx_segments(row["file"])
        if not tracks:
            return

        pts = tracks[0]

        entry1.delete(0, tk.END)
        entry1.insert(0, f"{pts[0][0]}, {pts[0][1]}")
        entry2.delete(0, tk.END)
        entry2.insert(0, f"{pts[-1][0]}, {pts[-1][1]}")

        update_preview(entry1, label1)
        update_preview(entry2, label2)

    def calculate_juggernaut():
        tracks = load_gpx_segments(row["file"])
        """Calculate track deviation statistics."""
        if not tracks:
            return

        pts = tracks[0]

        lat1, lon1 = app_state["start_coords"]
        lat2, lon2 = app_state["end_coords"]

        factor = app_state["factor"]

        geod = Geodesic.WGS84
    
        inv = geod.Inverse(lat1, lon1, lat2, lon2)
        total_dist = inv["s12"]
        limit = total_dist / factor
        line = geod.Line(lat1, lon1, inv["azi1"])
    
        max_left = 0
        max_right = 0
        pos_left = 0
        pos_right = 0

        current_dist = 0

        for i, (lat, lon) in enumerate(pts):

            if i > 0:
                prev_lat, prev_lon = pts[i-1]
                seg = geod.Inverse(prev_lat, prev_lon, lat, lon)
                current_dist += seg["s12"]

            deviation, left = compute_point_deviation(geod, line, lat1, lon1, lat, lon)
    
            if left:
                if deviation > max_left:
                    max_left = deviation
                    pos_left = current_dist
            else:
                if deviation > max_right:
                    max_right = deviation
                    pos_right = current_dist
    
            progress.set((i + 1) / len(pts) * 100)
            root.update_idletasks()

        if max_left > max_right:
            max_dev = max_left
            pos_max = pos_left
        else:
            max_dev = max_right
            pos_max = pos_right
    
        dev_factor = total_dist / max_dev if max_dev else 0
    
        show_results(
            total_dist,
            limit,
            max_dev,
            pos_max,
            dev_factor,
            max_left,
            pos_left,
            max_right,
            pos_right,
            current_dist,
            row
        )

    btn.config(command=choose_file)
    use_btn.config(command=use_points)
    calc_btn.config(command=calculate_juggernaut)

    track_rows.append(row)


def show_results(total_dist, limit, max_dev, pos_max, dev_factor, max_left, pos_left, max_right, pos_right, track_len, row):
# %% RESULTS
    """Show juggernaut analysis dialog."""
    result_text = (
        f"Straight line Distance: {total_dist/1000:.2f} km\n"
        f"Deviation Limit: {limit:.0f} m\n\n"
    
        f"Max Deviation: {max_dev:.0f} m at {pos_max/1000:.2f} km\n"
        f"Deviation Factor: {dev_factor:.2f}\n"
        f"Remaining Threshold: {limit - max_dev:.0f} m\n\n"
    
        f"Max Left Deviation: {max_left:.0f} m at {pos_left/1000:.2f} km\n"
        f"Max Right Deviation: {max_right:.0f} m at {pos_right/1000:.2f} km\n"
        f"Total Track lenght: {track_len/1000:.2f} km\n"
    )
    
    # --- build wiki text ---  
    wiki_text = "== Tracklog ==\n{{tracklog | ...juggernaut.gpx}}\n"
    main_color = row["color"].get()
    wiki_text += f"{{{{square|{main_color}}}}} Juggernaut run &emsp;&emsp;\n"

    
    for r in track_rows:
        if not r["file"] or r is row:
            continue
    
        fname = os.path.basename(r["file"])
        name = os.path.splitext(fname)[0]
        color = r["color"].get()
    
        wiki_text += f"{{{{square|{color}}}}} {name} &emsp;&emsp;\n"
    
    wiki_text += "{{square|000000}} Juggernaut boundary"
    
    dialog = tk.Toplevel(root)
    dialog.title("Juggernaut Results")

    txt = tk.Text(dialog, width=100, height=11)
    txt.insert("1.0", result_text)
    txt.pack(padx=10, pady=10)


    tk.Button(
        dialog,
        text="Copy Results",
        command=lambda: (
            root.clipboard_clear(),
            root.clipboard_append(result_text)
        )
    ).pack(pady=5)
    
    # --- wiki export block ---
    tk.Label(dialog, text="Wiki Color Legend:").pack(anchor="w", padx=10)
    
    wiki_txt = tk.Text(dialog, width=100, height=8)
    wiki_txt.insert("1.0", wiki_text)
    wiki_txt.pack(padx=10, pady=5)
    
    tk.Button(
        dialog,
        text="Copy Wiki Text",
        command=lambda: (
            root.clipboard_clear(),
            root.clipboard_append(wiki_text)
        )
    ).pack(pady=(0, 10))


# %% FILE GENERATION
def build_default_filename():
    """Build default GPX filename."""
    c2 = app_state["end_coords"]

    text = entry2.get()

    match = re.search(
        r"\d{4}-\d{2}-\d{2}",
        text
    )

    if match:
        date_str = match.group(0)
    else:
        date_str = datetime.date.today().strftime(
            "%Y-%m-%d"
        )

    lat_grat = int(c2[0])
    lon_grat = int(c2[1])

    return (
        f"{date_str} "
        f"{lat_grat} {lon_grat} "
        f"juggernaut.gpx"
    )


def save_file():
    """Generate combined GPX file."""
    boundary_mode = (
        app_state["can_generate_boundary"]
    )

    stack_only_mode = (
        app_state["can_generate_stack_only"]
    )

    if not (
        boundary_mode
        or stack_only_mode
    ):
        messagebox.showerror(
            "Error",
            "Nothing to generate."
        )

        return

    default_filename = (
        build_default_filename()
        if boundary_mode
        else "combined_tracklog.gpx"
    )

    filepath = filedialog.asksaveasfilename(
        defaultextension=".gpx",
        filetypes=[("GPX files", "*.gpx")],
        initialfile=default_filename
    )
    if not filepath:
        return

    gpx = ET.Element(
        "gpx",
        version="1.1",
        xmlns="http://www.topografix.com/GPX/1/1",
        **{
            "xmlns:gpx_style":
            "http://www.topografix.com/GPX/gpx_style/0/2"
        }
    )

    metadata = ET.SubElement(gpx, "metadata")

    ET.SubElement(
        metadata,
        "name"
    ).text = "generated combined tracklog"

    author = ET.SubElement(
        metadata,
        "author"
    )

    ET.SubElement(
        author,
        "name"
    ).text = (
        "Juggernaut-GPX-Generator by Monotof"
    )

    ET.SubElement(
        author,
        "link",
        href=(
            "https://geohashing.site/geohashing/"
            "Implementations#Juggernaut-GPX-Generator"
        )
    )

    # boundary mode
    if boundary_mode:
        lat1, lon1 = (
            app_state["start_coords"]
        )

        lat2, lon2 = (
            app_state["end_coords"]
        )

        if start_poi_var.get():
            gpx.append(
                create_waypoint(
                    lat1,
                    lon1,
                    "Startpoint"
                )
            )

        if end_poi_var.get():
            gpx.append(
                create_waypoint(
                    lat2,
                    lon2,
                    "Endpoint"
                )
            )

        geod = Geodesic.WGS84

        inv = geod.Inverse(
            lat1,
            lon1,
            lat2,
            lon2
        )

        limit = (
            inv["s12"]
            / app_state["factor"]
        )

        boundary = (
            compute_closed_offset_track(
                lat1,
                lon1,
                lat2,
                lon2,
                limit
            )
        )

        gpx.append(
            create_track(
                "boundary",
                boundary,
                "000000"
            )
        )

    # tracklogs
    user_tracks = [
        r for r in track_rows
        if r["file"]
    ]

    for row in reversed(user_tracks):
        segments = load_gpx_segments(
            row["file"]
        )

        for pts in segments:
            gpx.append(
                create_track(
                    os.path.basename(
                        row["file"]
                    ),
                    pts,
                    row["color"].get()
                )
            )

    # fallback center line
    if boundary_mode and not user_tracks:
        center = compute_center_line(
            lat1,
            lon1,
            lat2,
            lon2
        )

        gpx.append(
            create_track(
                "exact line",
                center,
                "0000ff"
            )
        )

    indent(gpx)
    ET.ElementTree(gpx).write(filepath, encoding="utf-8", xml_declaration=True)

def save_point(entry):
    coords, is_hashpoint = parse_coordinates(entry.get())
    if not coords:
        return
    
    init_str = entry.get() if is_hashpoint else ''
    
    name = simpledialog.askstring("Save Point", "Enter name:", initialvalue=init_str)
    if not name:
        return

    data = load_saved_points()
    if is_hashpoint:
        data[name] = {"hashpoint": entry.get()}
    else:
        data[name] = {"lat": coords[0], "lon": coords[1]}
    save_points_dict(data)

    refresh_ui_state()


def load_point(entry, label):
    """Load saved coordinate preset."""
    data = load_saved_points()
    if not data:
        return

    names = list(data.keys())

    dialog = tk.Toplevel(root)
    dialog.title("Load Point")

    dialog.transient(root)
    dialog.grab_set()

    tk.Label(dialog, text="Select saved point:").pack(padx=10, pady=10)

    listbox = tk.Listbox(dialog, width=40)
    listbox.pack(padx=10, pady=10)

    def refresh_list():
        listbox.delete(0, tk.END)
        for n in names:
            listbox.insert(tk.END, n)
        if names:
            listbox.select_set(0)
            listbox.activate(0)

    refresh_list()
    listbox.focus_set()

    def do_load():
        selection = listbox.curselection()
        if not selection:
            return

        name = names[selection[0]]
        pt = data[name]

        entry.delete(0, tk.END)
        if 'hashpoint' in pt:
            entry.insert(0, f"{pt['hashpoint']}")
        else:
            entry.insert(0, f"{pt['lat']}, {pt['lon']}")
        update_preview(entry, label)

        dialog.destroy()

    def do_remove():
        selection = listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        name = names[idx]

        if not messagebox.askyesno("Confirm Delete", f"Delete '{name}'?"):
            return

        del data[name]
        save_points_dict(data)

        names.pop(idx)

        refresh_list()

        refresh_ui_state()

        if not names:
            dialog.destroy()


    listbox.bind("<Double-Button-1>", lambda e: do_load())
    listbox.bind("<Return>", lambda e: do_load())

    btn_frame = tk.Frame(dialog)

    btn_frame.pack(pady=10)

    tk.Button(
        btn_frame,
        text="Remove",
        command=do_remove
    ).pack(
        side="left",
        padx=5
    )

    tk.Button(
        btn_frame,
        text="Load",
        command=do_load
    ).pack(
        side="left",
        padx=5
    )

    center_window(root, dialog)


# %% MAIN
if __name__ == "__main__":

    # %%% UI
    root = tk.Tk()
    root.title("Juggernaut GPX Generator")
    root.geometry("500x600")

    PAD_X = 20
    PAD_Y = 4

    main_frame = tk.Frame(root)
    main_frame.pack(fill="both", expand=True)
    
    input_frame = tk.Frame(main_frame)
    input_frame.pack(fill="x", anchor="w")
    
    
    # %%% STARTPOINT
    row1 = tk.Frame(input_frame)
    row1.pack(fill="x", padx=PAD_X, pady=PAD_Y)
    
    tk.Label(row1, text="Startpoint").pack(side="left")
    
    start_save_btn = tk.Button(row1, text="Save", state="disabled")
    start_save_btn.pack(side="right", padx=2)
    
    start_load_btn = tk.Button(row1, text="Load", state="disabled")
    start_load_btn.pack(side="right", padx=2)
    
    entry1 = tk.Entry(input_frame, width=80)
    entry1.pack(anchor="w", padx=PAD_X)
    
    label1 = tk.Label(input_frame, text="Parsed:")
    label1.pack(anchor="w", padx=PAD_X)
    
    entry1.bind("<KeyRelease>", lambda e: update_preview(entry1, label1))
    
    start_save_btn.config(command=lambda: save_point(entry1))
    start_load_btn.config(command=lambda: load_point(entry1, label1))
    
    
    # %%% ENDPOINT
    row2 = tk.Frame(input_frame)
    row2.pack(fill="x", padx=PAD_X, pady=PAD_Y)
    
    tk.Label(row2, text="Endpoint (Hashpoint)").pack(side="left")
    
    end_save_btn = tk.Button(row2, text="Save", state="disabled")
    end_save_btn.pack(side="right", padx=2)
    
    end_load_btn = tk.Button(row2, text="Load", state="disabled")
    end_load_btn.pack(side="right", padx=2)
    
    entry2 = tk.Entry(input_frame, width=80)
    entry2.pack(anchor="w", padx=PAD_X)
    
    label2 = tk.Label(input_frame, text="Parsed:")
    label2.pack(anchor="w", padx=PAD_X)
    
    entry2.bind("<KeyRelease>", lambda e: update_preview(entry2, label2))
    
    end_save_btn.config(command=lambda: save_point(entry2))
    end_load_btn.config(command=lambda: load_point(entry2, label2))
    
    
    # %%% FACTOR + INFO + BUTTON
    top_action_frame = tk.Frame(main_frame)
    top_action_frame.pack(fill="x", padx=PAD_X, pady=PAD_Y)
    
    # LEFT SIDE
    left_frame = tk.Frame(top_action_frame)
    left_frame.pack(side="left", fill="x", expand=True)
    
    # deviation ratio
    factor_frame = tk.Frame(left_frame)
    factor_frame.pack(anchor="w")
    
    tk.Label(factor_frame, text="Deviation Ratio 1:").pack(side="left")
    
    factor_entry = tk.Entry(factor_frame, width=5)
    factor_entry.insert(0, "20")
    factor_entry.pack(side="left")

    factor_entry.bind(
        "<KeyRelease>",
        lambda e: refresh_app_state()
    )

    info_label = tk.Label(
        left_frame,
        text="Total distance: --- km     Deviation Limit: --- m"
    )
    info_label.pack(anchor="w")

    right_frame = tk.Frame(top_action_frame)
    right_frame.pack(side="right", anchor="n")
    
    big_font = tkfont.Font(size=10, weight="bold")
    

    generate_btn = tk.Button(
        right_frame,
        text="Generate GPX",
        command=save_file,
        font=big_font,
        padx=10,
        pady=10,
        state="disabled"
    )
    generate_btn.pack()

    # %%% TRACKS
    tk.Label(main_frame, text="Tracklogs to include:").pack(
        anchor="w", padx=PAD_X, pady=(10, 2)
    )

    tracks_container = tk.Frame(main_frame)
    tracks_container.pack(fill="x", anchor="w")
    
    # %%% STATUS BAR (BOTTOM)
    progress = tk.DoubleVar()

    status_frame = tk.Frame(root)
    status_frame.pack(side="bottom", fill="x")
    
    progressbar = ttk.Progressbar(status_frame, variable=progress, maximum=100)
    progressbar.pack(fill="x", padx=5, pady=3)
    
    
    # %%% INIT
    update_save_load_buttons()
    add_track_row()

    refresh_app_state()

    root.mainloop()

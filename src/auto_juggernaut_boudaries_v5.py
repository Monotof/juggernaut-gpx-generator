# -*- coding: utf-8 -*-
"""
Juggernaut GPX Generator
"""

import re
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
from geographiclib.geodesic import Geodesic
import tkinter.font as tkfont
import locale
locale.setlocale(locale.LC_ALL, '')


# -----------------------------
# BASIC FUNCTIONS
# -----------------------------
def indent(elem, level=0):
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
    text = text.replace(",", ".")
    nums = re.findall(r"-?\d+\.\d+", text)
    if len(nums) < 2:
        return None
    return float(nums[0]), float(nums[1])


# -----------------------------
# GEODESIC
# -----------------------------
def compute_offset_lines(lat1, lon1, lat2, lon2, limit):
    geod = Geodesic.WGS84

    inv = geod.Inverse(lat1, lon1, lat2, lon2)
    total_dist = inv["s12"]
    azi1 = inv["azi1"]

    max_segments = 500
    base_step = 2000

    n_segments = int(total_dist / base_step)
    if n_segments > max_segments:
        n_segments = max_segments

    step = total_dist / max(n_segments, 1)

    line = geod.Line(lat1, lon1, azi1)

    left_points, right_points = [], []

    for i in range(n_segments + 1):
        d = min(i * step, total_dist)
        pos = line.Position(d)

        lat, lon, azi = pos["lat2"], pos["lon2"], pos["azi2"]

        left = geod.Direct(lat, lon, azi - 90, limit)
        right = geod.Direct(lat, lon, azi + 90, limit)

        left_points.append((left["lat2"], left["lon2"]))
        right_points.append((right["lat2"], right["lon2"]))

    return left_points, right_points


def compute_center_line(lat1, lon1, lat2, lon2):
    geod = Geodesic.WGS84
    inv = geod.Inverse(lat1, lon1, lat2, lon2)
    total_dist = inv["s12"]
    azi1 = inv["azi1"]

    line = geod.Line(lat1, lon1, azi1)

    points = []
    for i in range(11):
        d = i * total_dist / 10
        pos = line.Position(d)
        points.append((pos["lat2"], pos["lon2"]))

    return points


# -----------------------------
# GPX
# -----------------------------
def create_track(name, points, color):
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


def load_gpx_segments(filepath):
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


# -----------------------------
# GUI TRACK ROW
# -----------------------------
track_rows = []


def add_track_row():
    row = {}

    frame = tk.Frame(tracks_container)
    frame.pack(fill="x", anchor="w", padx=20, pady=4)

    btn = tk.Button(frame, text="Add Tracklog", width=16)
    btn.pack(side="left")

    # create but DO NOT pack yet
    color_entry = tk.Entry(frame, width=8)
    color_entry.insert(0, "0000ff")

    use_btn = tk.Button(frame, text="Use start/end from this")

    filename_var = tk.StringVar()
    filename_label = tk.Label(frame, textvariable=filename_var, anchor="w")


    row["file"] = None
    row["color"] = color_entry
    row["filename"] = filename_var
    row["frame"] = frame

    def remove_row():
        frame.destroy()
        track_rows.remove(row)

        if not any(r["file"] is None for r in track_rows):
            add_track_row()

    def choose_file():
        file = filedialog.askopenfilename(filetypes=[("GPX files", "*.gpx")])
        if not file:
            return

        row["file"] = file
        filename_var.set(os.path.basename(file))

        # SHOW controls now
        color_entry.pack(side="left", padx=5)
        use_btn.pack(side="left", padx=5)
        filename_label.pack(side="left", fill="x", expand=True, padx=5)

        btn.config(text="Remove Tracklog", command=remove_row)

        if track_rows[-1] is row:
            add_track_row()

    def use_points():
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

    btn.config(command=choose_file)
    use_btn.config(command=use_points)

    track_rows.append(row)


# -----------------------------
# GUI LOGIC
# -----------------------------
def update_info():
    c1 = parse_coordinates(entry1.get())
    c2 = parse_coordinates(entry2.get())

    try:
        factor = float(factor_entry.get())
    except:
        info_label.config(text="Invalid factor")
        return

    if not c1 or not c2:
        info_label.config(text="Total distance: --- km     Deviation Limit: --- m")
        return

    geod = Geodesic.WGS84
    inv = geod.Inverse(c1[0], c1[1], c2[0], c2[1])

    distance = inv["s12"]
    limit = distance / factor

    distance_km = locale.format_string("%.2f", distance / 1000, grouping=True)
    limit_m = locale.format_string("%.0f", limit, grouping=True)
    
    info_label.config(
        text=f"Total distance: {distance_km} km     Deviation Limit: {limit_m} m"
    )



def update_preview(entry, label):
    coords = parse_coordinates(entry.get())
    if coords:
        label.config(text=f"Parsed: {coords[0]:.6f}, {coords[1]:.6f}")
    else:
        label.config(text="Invalid input")

    update_info()


def save_file():
    c1 = parse_coordinates(entry1.get())
    c2 = parse_coordinates(entry2.get())

    if not c1 or not c2:
        messagebox.showerror("Error", "Invalid coordinates")
        return

    factor = float(factor_entry.get())

    filepath = filedialog.asksaveasfilename(defaultextension=".gpx")
    if not filepath:
        return

    lat1, lon1 = c1
    lat2, lon2 = c2

    geod = Geodesic.WGS84
    inv = geod.Inverse(lat1, lon1, lat2, lon2)
    distance = inv["s12"]
    limit = distance / factor

    left, right = compute_offset_lines(lat1, lon1, lat2, lon2, limit)

    gpx = ET.Element("gpx", version="1.1",
                     xmlns="http://www.topografix.com/GPX/1/1",
                     **{"xmlns:gpx_style": "http://www.topografix.com/GPX/gpx_style/0/2"})

    metadata = ET.SubElement(gpx, "metadata")
    ET.SubElement(metadata, "name").text = "auto juggernaut boundaries"

    author = ET.SubElement(metadata, "author")
    ET.SubElement(author, "name").text = "Monotof's juggernaut script"
    ET.SubElement(author, "link", href="https://geohashing.site/geohashing/User:Monotof")

    gpx.append(create_track("boundary 1", left, "000000"))
    gpx.append(create_track("boundary 2", right, "000000"))

    user_tracks = [r for r in track_rows if r["file"]]

    if user_tracks:
        for row in reversed(user_tracks):
            segments = load_gpx_segments(row["file"])
            for pts in segments:
                gpx.append(create_track(
                    os.path.basename(row["file"]),
                    pts,
                    row["color"].get()
                ))
    else:
        center = compute_center_line(lat1, lon1, lat2, lon2)
        gpx.append(create_track("exact line", center, "0000ff"))

    indent(gpx)
    ET.ElementTree(gpx).write(filepath, encoding="utf-8", xml_declaration=True)


# -----------------------------
# UI
# -----------------------------
root = tk.Tk()
root.title("Juggernaut GPX Generator")
root.geometry("500x450")

PAD_X = 20
PAD_Y = 4

main_frame = tk.Frame(root)
main_frame.pack(fill="both", expand=True)

input_frame = tk.Frame(main_frame)
input_frame.pack(fill="x", anchor="w")

tk.Label(input_frame, text="Startpoint").pack(anchor="w", padx=PAD_X, pady=PAD_Y)
entry1 = tk.Entry(input_frame, width=80)
entry1.pack(anchor="w", padx=PAD_X)
label1 = tk.Label(input_frame, text="Parsed:")
label1.pack(anchor="w", padx=PAD_X)
entry1.bind("<KeyRelease>", lambda e: update_preview(entry1, label1))

tk.Label(input_frame, text="Endpoint (Hashpoint)").pack(anchor="w", padx=PAD_X, pady=PAD_Y)
entry2 = tk.Entry(input_frame, width=80)
entry2.pack(anchor="w", padx=PAD_X)
label2 = tk.Label(input_frame, text="Parsed:")
label2.pack(anchor="w", padx=PAD_X)
entry2.bind("<KeyRelease>", lambda e: update_preview(entry2, label2))

factor_frame = tk.Frame(input_frame)
factor_frame.pack(anchor="w", padx=PAD_X, pady=PAD_Y)

tk.Label(factor_frame, text="Deviation Ratio 1:").pack(side="left")
factor_entry = tk.Entry(factor_frame, width=5)
factor_entry.insert(0, "20")
factor_entry.pack(side="left")
factor_entry.bind("<KeyRelease>", lambda e: update_info())

info_label = tk.Label(input_frame, text="Total distance: --- km     Deviation Limit: --- m")
info_label.pack(anchor="w", padx=PAD_X)


tk.Label(main_frame, text="Tracklogs to include:").pack(anchor="w", padx=PAD_X, pady=(10, 2))

tracks_container = tk.Frame(main_frame)
tracks_container.pack(fill="x", anchor="w")

button_frame = tk.Frame(main_frame)
button_frame.pack(fill="x", pady=10)

big_font = tkfont.Font(size=10, weight="bold")

tk.Button(
    button_frame,
    text="Generate combined GPX",
    command=save_file,
    font=big_font,
    padx=8,
    pady=5
).pack(padx=PAD_X, pady=10)

add_track_row()

root.mainloop()

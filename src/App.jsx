import React, { useState, useEffect } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Geodesic } from "geographiclib";


const geod = Geodesic.WGS84;


function parseCoordinates(text) {
  const nums = text.replace(/,/g, ".").match(/-?\d+\.?\d*/g);
  if (!nums || nums.length < 2) return null;
  return [parseFloat(nums[0]), parseFloat(nums[1])];
}

function computeOffsetLines(lat1, lon1, lat2, lon2, limit) {
  const inv = geod.Inverse(lat1, lon1, lat2, lon2);
  const total_dist = inv.s12;
  const azi1 = inv.azi1;
  const n_segments = 40;
  const step = total_dist / n_segments;
  const line = geod.Line(lat1, lon1, azi1);
  let left = [], right = [];
  for (let i = 0; i <= n_segments; i++) {
    let d = Math.min(i * step, total_dist);
    let pos = line.Position(d);
    let lat = pos.lat2;
    let lon = pos.lon2;
    let azi = pos.azi2;
    let leftPt = geod.Direct(lat, lon, azi - 90, limit);
    let rightPt = geod.Direct(lat, lon, azi + 90, limit);
    left.push([leftPt.lat2, leftPt.lon2]);
    right.push([rightPt.lat2, rightPt.lon2]);
  }


  return [left, right];
}

function computeCenterLine(lat1, lon1, lat2, lon2) {
  const inv = geod.Inverse(lat1, lon1, lat2, lon2);
  const total_dist = inv.s12;
  const azi1 = inv.azi1;
  const line = geod.Line(lat1, lon1, azi1);
  let pts = [];
  for (let i = 0; i <= 10; i++) {
    let d = i * total_dist / 10;
    let pos = line.Position(d);
    pts.push([pos.lat2, pos.lon2]);
  }
  return pts;
}

function parseGPX(text) {
  const parser = new DOMParser();
  const xml = parser.parseFromString(text, "application/xml");
  const segments = [...xml.getElementsByTagName("trkseg")];

  return segments.map(seg =>
    [...seg.getElementsByTagName("trkpt")].map(pt => ([
      parseFloat(pt.getAttribute("lat")),
      parseFloat(pt.getAttribute("lon"))
    ]))
  );
}

function createGPX(tracks) {
  let gpx = `<?xml version="1.0" encoding="UTF-8"?>
`;
  gpx += `<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpx_style="http://www.topografix.com/GPX/gpx_style/0/2">
`;

  tracks.forEach(t => {
    gpx += `<trk><name>${t.name}</name>`;
    gpx += `<extensions><gpx_style:line><color>${t.color}</color></gpx_style:line></extensions>`;
    gpx += `<trkseg>`;

    t.points.forEach(p => {
      gpx += `<trkpt lat="${p[0]}" lon="${p[1]}"></trkpt>`;
    });

    gpx += `</trkseg></trk>
`;
  });

  gpx += `</gpx>`;
  return gpx;
}

export default function App() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [factor, setFactor] = useState(20);
  const [tracks, setTracks] = useState([{ file: null, name: "", data: null, color: "0000ff" }]);
  const [map, setMap] = useState(null);
  const [layerGroup, setLayerGroup] = useState(null);

  useEffect(() => {
    const m = L.map("map").setView([51, 10], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(m);
    const group = L.layerGroup().addTo(m);
    setMap(m);
    setLayerGroup(group);
  }, []);

  const updateTrack = (index, update) => {
    const copy = [...tracks];
    copy[index] = { ...copy[index], ...update };
    setTracks(copy);
  };

  const handleFile = (file, index) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => {
      const data = parseGPX(e.target.result);
      updateTrack(index, { file, name: file.name, data });

      if (index === tracks.length - 1) {
        setTracks(t => [...t, { file: null, name: "", data: null, color: "0000ff" }]);
      }
    };
    reader.readAsText(file);
  };

  const removeTrack = index => {
    const copy = tracks.filter((_, i) => i !== index);
    setTracks(copy.length ? copy : [{ file: null, name: "", data: null, color: "0000ff" }]);
  };

  const useTrackPoints = index => {
    const t = tracks[index];
    if (!t.data || !t.data.length) return;
    const pts = t.data[0];
    setStart(`${pts[0][0]}, ${pts[0][1]}`);
    setEnd(`${pts[pts.length-1][0]}, ${pts[pts.length-1][1]}`);
  };

  const drawMap = (tracksToDraw) => {
    if (!layerGroup || !map) return;
    layerGroup.clearLayers();


    let allLatLngs = [];


    tracksToDraw.forEach((t, idx) => {
      const latlngs = t.points.map(p => [p[0], p[1]]);
      allLatLngs = allLatLngs.concat(latlngs);


      L.polyline(latlngs, { color: `#${t.color}`, weight: 3 }).addTo(layerGroup);


      if (idx === 0) {
        L.marker(latlngs[0]).addTo(layerGroup).bindPopup("Start");
      }
      if (idx === 1) {
        L.marker(latlngs[latlngs.length - 1]).addTo(layerGroup).bindPopup("End");
      }
    });


    if (allLatLngs.length) {
      const bounds = L.latLngBounds(allLatLngs);
      map.fitBounds(bounds);
    }
  };

  const generate = () => {
    const c1 = parseCoordinates(start);
    const c2 = parseCoordinates(end);

    if (!c1 || !c2) {
      alert("Invalid coordinates");
      return;
    }

    const inv = geod.Inverse(c1[0], c1[1], c2[0], c2[1]);
    const limit = inv.s12 / factor;
    const [left, right] = computeOffsetLines(c1[0], c1[1], c2[0], c2[1], limit);

    let allTracks = [
      { name: "boundary 1", points: left, color: "000000" },
      { name: "boundary 2", points: right, color: "000000" }
    ];

    const userTracks = tracks.filter(t => t.data);

    if (userTracks.length) {
      userTracks.reverse().forEach(t => {
        t.data.forEach(seg => {
          allTracks.push({ name: t.name, points: seg, color: t.color });
        });
      });
    } else {
      allTracks.push({ name: "center", points: computeCenterLine(c1[0], c1[1], c2[0], c2[1]), color: "0000ff" });
    }

    drawMap(allTracks);


    const gpx = createGPX(allTracks);

    const blob = new Blob([gpx], { type: "application/gpx+xml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "juggernaut.gpx";
    a.click();
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold mb-4">Juggernaut GPX Generator</h1>

      <input className="border p-2 w-full mb-1" placeholder="Startpoint" value={start} onChange={e=>setStart(e.target.value)} />
      <div className="text-sm mb-2">{JSON.stringify(parseCoordinates(start) || "Invalid")}</div>

      <input className="border p-2 w-full mb-1" placeholder="Endpoint" value={end} onChange={e=>setEnd(e.target.value)} />
      <div className="text-sm mb-2">{JSON.stringify(parseCoordinates(end) || "Invalid")}</div>

      <div className="flex gap-2 mb-4">
        <span>Deviation 1:</span>
        <input type="number" value={factor} onChange={e=>setFactor(Number(e.target.value))} className="border w-20" />
      </div>

      <h2 className="font-semibold mt-4 mb-2">Tracklogs</h2>

      {tracks.map((t, i) => (
        <div key={i} className="flex items-center gap-2 mb-2">
          {!t.file ? (
            <input type="file" accept=".gpx" onChange={e=>handleFile(e.target.files[0], i)} />
          ) : (
            <button onClick={()=>removeTrack(i)} className="bg-red-500 text-white px-2">Remove</button>
          )}

          <input value={t.color} onChange={e=>updateTrack(i,{color:e.target.value})} className="border w-16" />

          <button onClick={()=>useTrackPoints(i)}>Use start/end</button>

          <span className="text-sm">{t.name}</span>
        </div>
      ))}

      <button onClick={generate} className="bg-blue-600 text-white px-4 py-2 mt-4">Generate GPX + Preview</button>
      <div id="map" style={{ height: "400px", marginTop: "20px" }}></div>
    </div>
  );
}

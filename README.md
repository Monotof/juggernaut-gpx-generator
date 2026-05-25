# juggernaut-gpx-generator
Tool for generating .gpx files to visualize Tracklogs for the [Juggernaut Achievement](https://geohashing.site/geohashing/Juggernaut_achievement) for use on the [geohashing wiki](https://geohashing.site/geohashing/Main_Page).

[Python Code](https://github.com/Monotof/juggernaut-gpx-generator/blob/main/src/juggernaut-gpx-generator.py)

[Download compiled Executable of latest Release](https://github.com/Monotof/juggernaut-gpx-generator/releases/latest/download/juggernaut-gpx-generator.exe) (Windows)

## How to Use

<table border="0" cellspacing="0" cellpadding="0">
  <tr>
  <td width="310" valign="top" style="border:none;">
  <img height="266" alt="Screenshot 2026-05-24 191817" src="https://github.com/user-attachments/assets/f7c399b2-9272-432e-b0e6-2b5ec5bf6011" />
  </td>
  <td valign="top" style="border:none; padding-left:20px;">
  
  Paste coordinates for the start and endpoint in any lat/long format. You can also use a Geohash date and graticule, or just a graticule for the current day. Save and load frequently used points (e.g. Home and Office).

  Use **"Generate GPX"** without adding any tracklogs to create a .gpx file containing the straight line and juggernaut boundary for the selected deviation ratio. This is useful for loading into your route-planning tool of choice.
  
  After completing your mission, add your tracklog(s), choose the color you want them to appear as on the wiki, and export the combined .gpx file.
  </td>
  </tr>
  <tr>
  <td  valign="top" style="border:none;">
  <img width="310" height="289" alt="Screenshot 2026-05-25 124138" src="https://github.com/user-attachments/assets/d7715a19-956d-4da2-a240-08941ec3fd2e" />

  </td>
  <td valign="top" style="border:none; padding-left:20px;">
    
  Use **"Calculate Juggernaut"** on a tracklog (the one to the hashpoint) to generate detailed metrics for your mission report, along with a prepared tracklog section including the color legend.
  </td>
  </tr>
</table>

## Calculation method

This tool uses the WGS 1984 model for maximum accuracy. Some other route-planning software may use different models, so slight inconsistencies can occur.

## Third-Party Code

This project uses code from:

- geohashing.py | 
  Source: https://github.com/makew0rld/geohashing | 
  License: CC0-1.0 license

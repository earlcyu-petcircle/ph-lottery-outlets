#!/usr/bin/env python3
"""
Interactive web map (Folium/Leaflet): granular wealth base + lottery outlets.

Wealth base = Relative Wealth Index painted as a ~2.4 km image overlay
(each pixel takes the RWI of the zoom-14 tile it sits in).
Points = lotto outlets from OpenStreetMap.

Run after analysis.py:  python src/map.py  ->  maps/lottery_map.html
"""
import base64
import io
import re

import folium
import matplotlib.cm as cm
import numpy as np
import pandas as pd
from folium import Element
from matplotlib.colors import Normalize
from PIL import Image

from common import (CANVAS, DERIVED, INK, MAPS, OUTLET_EDGE, OUTLET_FILL, WEALTH, WEALTH_STOPS,
                    ncr_boundary, rwi_canvas)

odf = pd.read_csv(DERIVED / "outlets_clean.csv", keep_default_na=False)

# ---- wealth base as a PNG overlay ----
grid, vmin, vmax = rwi_canvas(res=0.018)
rgba = cm.ScalarMappable(norm=Normalize(vmin, vmax), cmap=WEALTH).to_rgba(grid, bytes=True)
rgba[..., 3] = np.where(np.isnan(grid), 0, 205).astype(np.uint8)   # transparent where no data
buf = io.BytesIO()
Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
png_b64 = base64.b64encode(buf.getvalue()).decode()

# Keyless base tiles: OpenStreetMap standard is free; CartoDB/Stamen now need keys.
m = folium.Map(location=[12.6, 122.5], zoom_start=6, tiles="OpenStreetMap",
               control_scale=True, prefer_canvas=True)

folium.raster_layers.ImageOverlay(
    image=f"data:image/png;base64,{png_b64}",
    bounds=[[CANVAS["lat_min"], CANVAS["lon_min"]], [CANVAS["lat_max"], CANVAS["lon_max"]]],
    opacity=0.85, name="Neighbourhood wealth (RWI, ~2.4 km)", interactive=False, zindex=1,
).add_to(m)

# ---- NCR outline for context ----
folium.GeoJson(ncr_boundary().__geo_interface__, name="Metro Manila (NCR) outline",
               style_function=lambda f: {"color": INK, "weight": 1.5, "fill": False,
                                         "dashArray": "4,3"}).add_to(m)

# ---- outlets ----
fg = folium.FeatureGroup(name=f"Lotto outlets (OSM, n={len(odf)})", show=True)
for r in odf.itertuples():
    name = r.name or "Lotto outlet"
    folium.CircleMarker(
        [r.lat, r.lon], radius=3, weight=0.8, color=OUTLET_EDGE,
        fill=True, fill_color=OUTLET_FILL, fill_opacity=0.9,
        popup=folium.Popup(f"<b>{name}</b><br><span style='color:#665B45'>{r.operator}</span>"
                           f"<br><span style='font-size:11px;color:#8B8069'>shop={r.shop}</span>",
                           max_width=240),
    ).add_to(fg)
fg.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

# ---- title + legend ----
ramp = ",".join(WEALTH_STOPS)
m.get_root().html.add_child(Element("""
<div style="position:fixed;top:12px;left:50px;z-index:9999;background:#F8F3E8;
 border:1px solid #C2B597;border-left:3px solid #96700F;padding:10px 14px;max-width:340px;
 font-family:Georgia,serif;color:#292216;box-shadow:0 1px 6px rgba(0,0,0,.12)">
 <div style="font-size:15px;font-weight:600;line-height:1.2">Lotto outlets over neighbourhood wealth</div>
 <div style="font-size:11.5px;color:#665B45;margin-top:4px;font-family:system-ui,sans-serif">
   Philippines &middot; wealth base = Meta Relative Wealth Index (~2.4&nbsp;km grid);
   points = lotto outlets mapped in OpenStreetMap.</div>
</div>"""))
m.get_root().html.add_child(Element(f"""
<div style="position:fixed;bottom:22px;left:12px;z-index:9999;background:#F8F3E8;
 border:1px solid #C2B597;padding:9px 12px;font-family:system-ui,sans-serif;color:#292216;
 font-size:11.5px;box-shadow:0 1px 6px rgba(0,0,0,.12)">
 <div style="font-weight:700;margin-bottom:4px">Relative Wealth Index</div>
 <div style="height:11px;width:190px;background:linear-gradient(to right,{ramp});
   border:1px solid #C2B597"></div>
 <div style="display:flex;justify-content:space-between;width:190px;color:#665B45;margin-top:2px">
   <span>poorer</span><span>richer</span></div>
 <div style="margin-top:7px;display:flex;align-items:center;gap:6px">
   <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{OUTLET_FILL};
     border:1px solid {OUTLET_EDGE}"></span> lotto outlet</div>
</div>"""))

# Folium names every element with a random 32-hex id; renumber them in order of
# first appearance so a re-run on the same data writes a byte-identical file.
html = m.get_root().render()
ids = {}
html = re.sub(r"(?<![0-9A-Za-z+/])[0-9a-f]{32}(?![0-9A-Za-z+/])",
              lambda mt: ids.setdefault(mt.group(0), f"{len(ids):032x}"), html)
(MAPS / "lottery_map.html").write_text(html)
print(f"wrote maps/lottery_map.html  |  outlets plotted: {len(odf)}")

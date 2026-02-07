// ==== EDIT THESE PER LISTING ====
const LISTING = {
  center: [106.7305, 10.7872], // [lng, lat]
  label: "Luxury 2BR Apartment",       // callout badge text
  location: "DISTRICT 2, HCMC",          // callout subtitle
  title: "Luxury 2BR Apartment • District 2",
  subline: "3 mins to Metro • River View • From $220,000",
  cta: "Book a tour: +84 900 000 000",
  poi: [
    { name: "Property", coords: [106.7305, 10.7872] },
    { name: "Metro", coords: [106.7357, 10.7848] },
    { name: "Mall", coords: [106.7222, 10.7910] }
  ]
};

// update overlays
document.getElementById("headline").textContent = LISTING.title;
document.getElementById("subline").textContent = LISTING.subline;
document.getElementById("cta").textContent = LISTING.cta;

// const map = new maplibregl.Map({
//   container: "map",
//   style: "https://demotiles.maplibre.org/style.json", // replace with your style URL
//   center: [106.70, 10.77],
//   zoom: 10,
//   pitch: 50,
//   bearing: -20,
//   antialias: true
// });

const map = new maplibregl.Map({
  container: "map",
  style: {
    version: 8,
    glyphs: "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
    sources: {
      // Satellite imagery (Esri World Imagery)
      satellite: {
        type: "raster",
        tiles: [
          "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ],
        tileSize: 256,
        attribution: "Tiles © Esri"
      },
      // Optional labels overlay (Carto light labels)
      labels: {
        type: "raster",
        tiles: [
          "https://a.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}.png",
          "https://b.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}.png",
          "https://c.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}.png",
          "https://d.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}.png"
        ],
        tileSize: 256,
        attribution: "© OpenStreetMap contributors © CARTO"
      }
    },
    layers: [
      {
        id: "satellite",
        type: "raster",
        source: "satellite",
        minzoom: 0,
        maxzoom: 22
      },
      {
        id: "labels",
        type: "raster",
        source: "labels",
        minzoom: 0,
        maxzoom: 22
      }
    ]
  },
  center: [106.70, 10.77],
  zoom: 10,
  pitch: 50,
  bearing: -20,
  antialias: true
});

let roadLabelMarkers = [];
let roadLabelsEnabled = false;
let roadLabelMinLimit = 0;
let roadLabelsAllowMinor = false;
let storyboardStarted = false;

function safeRunStoryboard() {
  if (storyboardStarted) return;
  storyboardStarted = true;
  window.__storyboardStarted = true;
  window.dispatchEvent(new CustomEvent("storyboard-started"));
  console.log("Storyboard started");
  runStoryboard().then(() => {
    window.__storyboardFinished = true;
    console.log("Storyboard finished");
  });
}

function isValidLngLat(coords) {
  return Array.isArray(coords) && coords.length === 2 &&
    Number.isFinite(coords[0]) && Number.isFinite(coords[1]);
}

function getRoadLabelLimit(zoom) {
  if (zoom < 12.8) return 0;
  if (zoom < 13.4) return 10;
//   if (zoom < 14.2) return 30;
  if (zoom < 15.0) return 30;
  return 40;
}

function updateRoadLabels() {
  if (!roadLabelsEnabled) return;
  const zoom = map.getZoom();
  const limit = getRoadLabelLimit(zoom);
  const allowMinorNow = zoom >= 14.5;
  roadLabelsAllowMinor = roadLabelsAllowMinor || allowMinorNow;
  roadLabelMinLimit = Math.max(roadLabelMinLimit, limit);
  const allowMinor = roadLabelsAllowMinor;
  const effectiveLimit = Math.max(limit, roadLabelMinLimit);
  const maxMinor = 10;
  const maxDistanceKm = 2.8;
  const minDistanceKm = 0.12;
  const padPx = zoom >= 15 ? 10 : 8;

  roadLabelMarkers.forEach(item => {
    item.el.style.display = "none";
  });

  const candidates = roadLabelMarkers
    .filter(item => isValidLngLat(item.coords))
    .filter(item => item.distanceKm <= maxDistanceKm && item.distanceKm >= minDistanceKm)
    .filter(item => allowMinor || !item.isMinor)
    .sort((a, b) => b.score - a.score);

  const byClass = {
    motorway: [],
    trunk: [],
    primary: [],
    secondary: [],
    minor: []
  };

  for (const item of candidates) {
    if (item.isMinor) {
      byClass.minor.push(item);
    } else if (item.highway === "motorway") {
      byClass.motorway.push(item);
    } else if (item.highway === "trunk") {
      byClass.trunk.push(item);
    } else if (item.highway === "primary") {
      byClass.primary.push(item);
    } else {
      byClass.secondary.push(item);
    }
  }

  const minPerClass = {
    motorway: zoom >= 14.2 ? 1 : 0,
    trunk: zoom >= 13.4 ? 1 : 0,
    primary: zoom >= 13.4 ? 2 : 1,
    secondary: zoom >= 14.2 ? 3 : 1,
    minor: allowMinor ? 2 : 0
  };

  const selected = [];
  const selectedSet = new Set();
  const placedRects = [];

  function estimateRect(item) {
    if (!isValidLngLat(item.coords)) return null;
    const pt = map.project(item.coords);
    const w = Math.min(220, 18 + item.name.length * 7.2);
    const h = item.isMinor ? 22 : 24;
    return {
      x1: pt.x - w / 2 - padPx,
      y1: pt.y - h / 2 - padPx,
      x2: pt.x + w / 2 + padPx,
      y2: pt.y + h / 2 + padPx
    };
  }

  function overlaps(rect) {
    if (!rect) return true;
    return placedRects.some(r =>
      rect.x1 < r.x2 && rect.x2 > r.x1 && rect.y1 < r.y2 && rect.y2 > r.y1
    );
  }

  function takeFrom(list, count) {
    let taken = 0;
    for (const item of list) {
      if (taken >= count) break;
      if (selectedSet.has(item.name)) continue;
      if (item.isMinor && selected.filter(i => i.isMinor).length >= maxMinor) break;
      const rect = estimateRect(item);
      if (overlaps(rect)) continue;
      selected.push(item);
      selectedSet.add(item.name);
      if (rect) placedRects.push(rect);
      taken += 1;
    }
  }

  takeFrom(byClass.motorway, minPerClass.motorway);
  takeFrom(byClass.trunk, minPerClass.trunk);
  takeFrom(byClass.primary, minPerClass.primary);
  takeFrom(byClass.secondary, minPerClass.secondary);
  takeFrom(byClass.minor, minPerClass.minor);

  for (const item of candidates) {
    if (selected.length >= effectiveLimit) break;
    if (selectedSet.has(item.name)) continue;
    if (item.isMinor && selected.filter(i => i.isMinor).length >= maxMinor) continue;
    const rect = estimateRect(item);
    if (overlaps(rect)) continue;
    selected.push(item);
    selectedSet.add(item.name);
    if (rect) placedRects.push(rect);
  }

  for (const item of selected.slice(0, effectiveLimit)) {
    item.el.style.display = "block";
    if (!item.el.dataset.animated) {
      const badge = item.el.querySelector(".road-callout-badge");
      if (badge) {
        // Force reflow to ensure animation triggers
        void badge.offsetWidth;
        badge.classList.add("animate-in");
        item.el.dataset.animated = "true";
        badge.addEventListener("animationend", () => {
          badge.classList.remove("animate-in");
        }, { once: true });
      }
    }
  }

  window.__roadLabelVisibleCount = selected.slice(0, effectiveLimit).length;
  window.__roadLabelsEnabled = true;
}

map.on("load", () => {
  // ── Major roads from Overpass API (GeoJSON) ──
  const bbox = (() => {
    const R = 0.015; // ~1.5 km buffer around center
    return [
      LISTING.center[1] - R, LISTING.center[0] - R,
      LISTING.center[1] + R, LISTING.center[0] + R
    ];
  })();

  function buildOverpassQuery(bounds) {
    return `
      [out:json][timeout:25];
      (
        way["highway"]["name"](${bounds.join(",")});
      );
      out body; >; out skel qt;
    `.trim();
  }

  const overpassQuery = buildOverpassQuery(bbox);

  const overpassMirrors = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
  ];

  const OVERPASS_CACHE_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours
  const OVERPASS_FETCH_TIMEOUT_MS = 15000;

  function getOverpassCacheKey() {
    const bboxKey = bbox.map(v => v.toFixed(5)).join(",");
    return `overpass:${bboxKey}`;
  }

  function readOverpassCache() {
    try {
      const raw = localStorage.getItem(getOverpassCacheKey());
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || !parsed.data || !parsed.timestamp) return null;
      const age = Date.now() - parsed.timestamp;
      return {
        data: parsed.data,
        fresh: age <= OVERPASS_CACHE_TTL_MS
      };
    } catch (e) {
      console.warn("Overpass cache read failed:", e.message);
      return null;
    }
  }

  function writeOverpassCache(data) {
    try {
      localStorage.setItem(
        getOverpassCacheKey(),
        JSON.stringify({ timestamp: Date.now(), data })
      );
    } catch (e) {
      console.warn("Overpass cache write failed:", e.message);
    }
  }

  async function fetchWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  }

  async function fetchOverpass() {
    const cached = readOverpassCache();
    if (cached?.fresh) return cached.data;

    async function tryQuery(query) {
      let lastError = null;
      for (const base of overpassMirrors) {
        try {
          const resp = await fetchWithTimeout(
            base + "?data=" + encodeURIComponent(query),
            OVERPASS_FETCH_TIMEOUT_MS
          );
          if (resp.ok) {
            const data = await resp.json();
            writeOverpassCache(data);
            return data;
          }
          console.warn(`Overpass mirror ${base} returned ${resp.status}, trying next…`);
        } catch (e) {
          lastError = e;
          console.warn(`Overpass mirror ${base} failed: ${e.message}, trying next…`);
        }
      }
      return { error: lastError };
    }

    const primary = await tryQuery(overpassQuery);
    if (primary && !primary.error) return primary;

    // Fallback: smaller bbox to improve response time
    const rSmall = 0.01;
    const bboxSmall = [
      LISTING.center[1] - rSmall, LISTING.center[0] - rSmall,
      LISTING.center[1] + rSmall, LISTING.center[0] + rSmall
    ];
    window.__overpassBbox = bboxSmall;
    const smallQuery = buildOverpassQuery(bboxSmall);
    const small = await tryQuery(smallQuery);
    if (small && !small.error) return small;

    if (cached?.data) return cached.data;
    throw new Error(primary.error?.message || small.error?.message || "All Overpass mirrors failed");
  }

  fetchOverpass()
    .then(data => {
      // Convert Overpass JSON to GeoJSON
      const nodes = {};
      data.elements.filter(e => e.type === "node").forEach(n => {
        nodes[n.id] = [n.lon, n.lat];
      });

      const features = data.elements
        .filter(e => e.type === "way" && e.nodes)
        .map(w => ({
          type: "Feature",
          properties: {
            name: w.tags?.name || w.tags?.["name:en"] || "",
            highway: w.tags?.highway || ""
          },
          geometry: {
            type: "LineString",
            coordinates: w.nodes.map(id => nodes[id]).filter(Boolean)
          }
        }))
        .filter(f => f.geometry.coordinates.length >= 2);

      console.log(`Roads loaded: ${features.length} segments`);
      window.__roadsLoaded = features.length;

      const geojson = { type: "FeatureCollection", features };

      map.addSource("roads", { type: "geojson", data: geojson });

      // Road outer glow
      map.addLayer({
        id: "roads-glow",
        type: "line",
        source: "roads",
        paint: {
          "line-color": "#000000",
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 4, 14, 12, 16, 18],
          "line-opacity": 0.5,
          "line-blur": 3
        },
        layout: { "line-cap": "round", "line-join": "round" }
      }, "poi-circles");

      // Road casing
      map.addLayer({
        id: "roads-casing",
        type: "line",
        source: "roads",
        paint: {
          "line-color": "#1a1a2e",
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 3, 14, 8, 16, 14],
          "line-opacity": 0.7
        },
        layout: { "line-cap": "round", "line-join": "round" }
      }, "poi-circles");

      // Road fill (color-coded)
      map.addLayer({
        id: "roads-fill",
        type: "line",
        source: "roads",
        paint: {
          "line-color": [
            "match", ["get", "highway"],
            "motorway", "#ffa94d",
            "trunk",    "#ffd43b",
            "primary",  "#ffffff",
            "secondary","#dee2e6",
            "#ced4da"
          ],
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1.5, 14, 4, 16, 8],
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 10, 0.5, 13, 0.8, 16, 0.95]
        },
        layout: { "line-cap": "round", "line-join": "round" }
      }, "poi-circles");

      // Road name callout labels (HTML markers)
      const seen = new Set();

      // Sort: major roads first so they win placement priority
      const rankOrder = { motorway: 0, trunk: 1, primary: 2, secondary: 3 };

      const MAX_LABELS = 120;

      const byName = new Map();
      features.forEach(f => {
        const name = f.properties.name;
        if (!name) return;
        if (!byName.has(name)) byName.set(name, []);
        byName.get(name).push(f);
      });

      const classWeights = {
        motorway: 6,
        trunk: 5,
        primary: 4,
        secondary: 3,
        tertiary: 2,
        residential: 1
      };

      const mergedRoads = Array.from(byName.entries()).map(([name, segs]) => {
        const allCoords = segs.flatMap(s => s.geometry.coordinates).filter(c => Array.isArray(c) && c.length === 2);
        if (allCoords.length < 2) return null;
        const line = turf.lineString(allCoords);
        const lengthKm = turf.length(line, { units: "kilometers" });
        const midIdx = Math.floor(allCoords.length / 2);
        const coords = allCoords[midIdx];
        if (!coords || !Number.isFinite(coords[0]) || !Number.isFinite(coords[1])) return null;
        const hw = segs[0].properties.highway;
        const distanceKm = turf.distance(turf.point(coords), turf.point(LISTING.center), { units: "kilometers" });
        const classWeight = classWeights[hw] ?? 0.5;
        const score = classWeight * 1000 + (2 / (distanceKm + 0.1)) + lengthKm;
        return { name, coords, lengthKm, distanceKm, highway: hw, score };
      }).filter(Boolean);

      const sortedRoads = mergedRoads
        .sort((a, b) => b.score - a.score)
        .slice(0, MAX_LABELS);

      roadLabelMarkers = [];

      for (const r of sortedRoads) {
        if (roadLabelMarkers.length >= MAX_LABELS) break;
        const name = r.name;
        if (!name || seen.has(name)) continue;
        seen.add(name);

        if (!isValidLngLat(r.coords)) continue;

        const isMinor = !(r.highway === "motorway" || r.highway === "trunk" || r.highway === "primary" || r.highway === "secondary");
        const colorClass = r.highway === "motorway" || r.highway === "trunk" ? "road-callout--major" : "road-callout--minor";

        const el = document.createElement("div");
        el.className = `road-callout ${colorClass}`;
        el.innerHTML = `<div class="road-callout-badge">${name}</div>`;
        el.style.display = "none";
        el.style.zIndex = "20";

        const marker = new maplibregl.Marker({ element: el, anchor: "center" })
          .setLngLat(r.coords)
          .addTo(map);

        roadLabelMarkers.push({
          marker,
          el,
          highway: r.highway,
          name,
          score: r.score,
          distanceKm: r.distanceKm,
          isMinor
          ,coords: r.coords
        });
      }

      window.__roadLabelCount = roadLabelMarkers.length;

      updateRoadLabels();
    })
    .catch(err => {
      window.__roadsLoaded = 0;
      window.__roadLabelCount = 0;
      console.warn("Road highlight fetch failed:", err);
    });

  // Property point + POIs
  const poiFC = {
    type: "FeatureCollection",
    features: LISTING.poi.map(p => ({
      type: "Feature",
      properties: { name: p.name },
      geometry: { type: "Point", coordinates: p.coords }
    }))
  };

  map.addSource("poi", { type: "geojson", data: poiFC });

  // POI circles (non-property)
  map.addLayer({
    id: "poi-circles",
    type: "circle",
    source: "poi",
    filter: ["!=", ["get", "name"], "Property"],
    paint: {
      "circle-radius": 6,
      "circle-color": "#4dabf7",
      "circle-stroke-width": 2,
      "circle-stroke-color": "#ffffff"
    }
  });

  // POI labels (non-property)
  map.addLayer({
    id: "poi-labels",
    type: "symbol",
    source: "poi",
    filter: ["!=", ["get", "name"], "Property"],
    layout: {
      "text-field": ["get", "name"],
      "text-offset": [0, 1.2],
      "text-size": 14,
      "text-font": ["Klokantech Noto Sans Regular"]
    },
    paint: {
      "text-color": "#ffffff",
      "text-halo-color": "#000000",
      "text-halo-width": 1
    }
  });

  // ── Property callout label (HTML marker) ──
  const calloutEl = document.createElement("div");
  calloutEl.className = "property-callout";
  calloutEl.style.zIndex = "30";
  calloutEl.innerHTML = `
    <div class="callout-badge">${LISTING.label}</div>
    <div class="callout-location">${LISTING.location}</div>
    <div class="callout-stem"></div>
    <div class="callout-dot"></div>
  `;

  new maplibregl.Marker({ element: calloutEl, anchor: "bottom" })
    .setLngLat(LISTING.center)
    .addTo(map);

  // Route: Property -> Metro
  const routeLine = turf.lineString([
    LISTING.poi.find(x => x.name === "Property").coords,
    LISTING.poi.find(x => x.name === "Metro").coords
  ]);

  map.addSource("route", {
    type: "geojson",
    data: routeLine
  });

  map.addLayer({
    id: "route-line",
    type: "line",
    source: "route",
    paint: {
      "line-color": "#ffd43b",
      "line-width": 5,
      "line-opacity": 0.9
    }
  });

  // Property radius (approx catchment)
  const circle = turf.circle(LISTING.center, 0.6, { units: "kilometers", steps: 64 });
  map.addSource("catchment", { type: "geojson", data: circle });

  map.addLayer({
    id: "catchment-fill",
    type: "fill",
    source: "catchment",
    paint: {
      "fill-color": "#51cf66",
      "fill-opacity": 0.15
    }
  });

  map.addLayer({
    id: "catchment-line",
    type: "line",
    source: "catchment",
    paint: {
      "line-color": "#51cf66",
      "line-width": 2
    }
  });

  // Radar-style sweeping scan (rotating sector)
  const radarSourceId = "radar-sweep";
  const radarLayerId = "radar-sweep-fill";
  const radarRadiusKm = 0.6;
  const sweepWidthDeg = 60;

  const initialSector = turf.sector(
    LISTING.center,
    radarRadiusKm,
    0,
    sweepWidthDeg,
    { steps: 64, units: "kilometers" }
  );

  map.addSource(radarSourceId, { type: "geojson", data: initialSector });

  map.addLayer({
    id: radarLayerId,
    type: "fill",
    source: radarSourceId,
    paint: {
      "fill-color": "#7CFF8A",
      "fill-opacity": 0.35
    }
  }, "catchment-line");

  map.addLayer({
    id: "radar-sweep-edge",
    type: "line",
    source: radarSourceId,
    paint: {
      "line-color": "rgba(124, 255, 138, 0.75)",
      "line-width": 6,
      "line-blur": 6,
      "line-opacity": 0.7
    }
  }, "catchment-line");

  const radarStart = performance.now();
  function drawRadarSweep(now) {
    const t = ((now - radarStart) % 2600) / 2600; // 0..1
    const angle = t * 360;
    const start = angle - sweepWidthDeg / 2;
    const end = angle + sweepWidthDeg / 2;
    window.__radarFrames = (window.__radarFrames || 0) + 1;

    const sector = turf.sector(
      LISTING.center,
      radarRadiusKm,
      start,
      end,
      { steps: 64, units: "kilometers" }
    );

    const src = map.getSource(radarSourceId);
    if (src && src.setData) {
      src.setData(sector);
    }
    requestAnimationFrame(drawRadarSweep);
  }

  requestAnimationFrame(drawRadarSweep);

  safeRunStoryboard();
});

// Fallbacks in case load sequence is interrupted by errors
map.once("idle", safeRunStoryboard);
setTimeout(() => {
  if (!storyboardStarted) safeRunStoryboard();
}, 2500);

// --- Shot timeline ---
function wait(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function flyToAsync(options, settle = 1200) {
  return new Promise(resolve => {
    map.flyTo(options);
    map.once("moveend", async () => {
      await wait(settle);
      resolve();
    });
  });
}

async function runStoryboard() {
  // Shot 1: City wide
  await flyToAsync({
    center: [106.70, 10.77],
    zoom: 10.2,
    pitch: 45,
    bearing: -20,
    duration: 5000
  });

  // Shot 2: District approach
  await flyToAsync({
    center: [106.725, 10.785],
    zoom: 13,
    pitch: 55,
    bearing: 15,
    duration: 5000
  });

  // Enable road labels from shot 2 onward
  roadLabelsEnabled = true;
  updateRoadLabels();

  // Shot 3: Property hero
  await flyToAsync({
    center: LISTING.center,
    zoom: 15.8,
    pitch: 60,
    bearing: 35,
    duration: 5500
  });

  // Lock in higher label counts and minor roads once we reach hero zoom
  roadLabelMinLimit = Math.max(roadLabelMinLimit, getRoadLabelLimit(map.getZoom()));
  roadLabelsAllowMinor = true;
  updateRoadLabels();

  // Shot 4: Route emphasis
  await flyToAsync({
    center: [106.7330, 10.7860],
    zoom: 14.8,
    pitch: 58,
    bearing: 70,
    duration: 5000
  });

  // Shot 5: CTA hold
  updateRoadLabels();
  await wait(3000);

  // tell capture script we are done (if running recording)
  window.dispatchEvent(new CustomEvent("storyboard-finished"));
}

map.on("zoomend", updateRoadLabels);
map.on("moveend", updateRoadLabels);



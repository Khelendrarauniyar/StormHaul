import "maplibre-gl/dist/maplibre-gl.css";

export const MAP_STYLE =
  import.meta.env.VITE_MAP_STYLE_URL ??
  "https://tiles.openfreemap.org/styles/liberty";

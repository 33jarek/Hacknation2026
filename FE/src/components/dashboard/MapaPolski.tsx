import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Geometry } from "geojson";
import { useEffect, useRef } from "react";

type Props = {
  lat: number;
  lon: number;
  parcelGeometry?: Geometry | null;
  /** zmiana tej wartości = przybliż mapę do wybranej lokalizacji */
  focusKey?: string | number;
  onPick: (lat: number, lon: number) => void;
};

const POLSKA_BOUNDS = L.latLngBounds([48.8, 13.8], [55.1, 24.3]);

export function MapaPolski({ lat, lon, parcelGeometry, focusKey, onPick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.CircleMarker | null>(null);
  const parcelRef = useRef<L.GeoJSON | null>(null);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  // Inicjalizacja mapy (raz)
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [lat, lon],
      zoom: 6,
      minZoom: 5,
      maxBounds: POLSKA_BOUNDS.pad(0.3),
      maxBoundsViscosity: 0.8,
      zoomControl: true,
    });

    const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    const orto = L.tileLayer.wms(
      "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution",
      {
        layers: "Raster",
        format: "image/jpeg",
        maxZoom: 19,
        attribution: "Ortofotomapa &copy; GUGiK",
      },
    );

    const dzialki = L.tileLayer.wms(
      "https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow",
      {
        layers: "dzialki,numery_dzialek",
        format: "image/png",
        transparent: true,
        minZoom: 15,
        maxZoom: 19,
        attribution: "Działki &copy; GUGiK",
      },
    );

    L.control
      .layers(
        { Mapa: osm, Ortofotomapa: orto },
        { "Granice działek (od zoom 15)": dzialki },
        { position: "topright" },
      )
      .addTo(map);
    L.control.scale({ imperial: false }).addTo(map);

    markerRef.current = L.circleMarker([lat, lon], {
      radius: 8,
      color: "#ffffff",
      weight: 2.5,
      fillColor: "#1f5b46",
      fillOpacity: 1,
      interactive: false,
    }).addTo(map);

    map.on("click", (e: L.LeafletMouseEvent) => {
      onPickRef.current(
        Number(e.latlng.lat.toFixed(6)),
        Number(e.latlng.lng.toFixed(6)),
      );
    });

    mapRef.current = map;

    // kontener mógł mieć zerowy rozmiar przy montowaniu
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
      parcelRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Marker
  useEffect(() => {
    markerRef.current?.setLatLng([lat, lon]);
  }, [lat, lon]);

  // Obrys działki
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    parcelRef.current?.remove();
    parcelRef.current = null;
    if (parcelGeometry) {
      parcelRef.current = L.geoJSON(parcelGeometry, {
        style: {
          color: "#dadc5a",
          weight: 3,
          fillColor: "#6cad46",
          fillOpacity: 0.25,
        },
        interactive: false,
      }).addTo(map);
      markerRef.current?.bringToFront();
    }
  }, [parcelGeometry]);

  // Przybliżenie po wyszukaniu
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focusKey) return;
    if (parcelRef.current) {
      map.flyToBounds(parcelRef.current.getBounds(), { maxZoom: 17, padding: [40, 40], duration: 0.8 });
    } else {
      map.flyTo([lat, lon], Math.max(map.getZoom(), 14), { duration: 0.8 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusKey]);

  return <div ref={containerRef} className="mapa-wybor isolate h-full w-full" />;
}

'use client';
import maplibregl, { type GeoJSONSource, type Map as MLMap } from 'maplibre-gl';
import { useEffect, useMemo, useRef } from 'react';
import type { LayerCollection } from '@sih/types';

import { colorFor } from '@/lib/mapColors';

interface Props { layer: LayerCollection | null; stateOutlines: unknown; selectedId: string | null; onSelect: (regionId: string) => void; focusState: string | null }

export default function MapView({ layer, stateOutlines, selectedId, onSelect, focusState }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const colored = useMemo(() => {
    if (!layer) return null;
    const ind = layer.meta.indicator;
    return { ...layer, features: layer.features.map((f) => ({ ...f, properties: { ...f.properties, _c: colorFor(f.properties.value, ind.legend, ind.higher_is_better) } })) };
  }, [layer]);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = new maplibregl.Map({
      container: el.current, center: [78.5, 16.5], zoom: 4.2, attributionControl: false,
      style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#eef2f1' } }] },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    m.on('load', () => {
      m.addSource('states', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      m.addSource('districts', { type: 'geojson', data: { type: 'FeatureCollection', features: [] }, promoteId: 'region_id' });
      m.addLayer({ id: 'state-fill', type: 'fill', source: 'states', paint: { 'fill-color': '#dfe6e4', 'fill-opacity': 0.6 } });
      m.addLayer({ id: 'state-line', type: 'line', source: 'states', paint: { 'line-color': '#6b7c89', 'line-width': 1.2, 'line-dasharray': [3, 2] } });
      m.addLayer({ id: 'd-fill', type: 'fill', source: 'districts', paint: { 'fill-color': ['get', '_c'], 'fill-opacity': 0.92 } });
      m.addLayer({ id: 'd-line', type: 'line', source: 'districts', paint: { 'line-color': '#ffffff', 'line-width': 1 } });
      m.addLayer({ id: 'd-sel', type: 'line', source: 'districts', paint: { 'line-color': '#14232f', 'line-width': 3 }, filter: ['==', ['get', 'region_id'], ''] });
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
      m.on('mousemove', 'd-fill', (e) => {
        m.getCanvas().style.cursor = 'pointer';
        const f = e.features?.[0]; if (!f) return;
        const v = f.properties?.value;
        popup.setLngLat(e.lngLat).setHTML(`<strong>${f.properties?.name}</strong><br/>${v == null || v === 'null' ? 'no data' : Number(v).toFixed(1)}`).addTo(m);
      });
      m.on('mouseleave', 'd-fill', () => { m.getCanvas().style.cursor = ''; popup.remove(); });
      m.on('click', 'd-fill', (e) => { const id = e.features?.[0]?.properties?.region_id; if (id) onSelectRef.current(id); });
      m.on('click', 'state-fill', (e) => { if (m.queryRenderedFeatures(e.point, { layers: ['d-fill'] }).length) return; const id = e.features?.[0]?.properties?.region_id; if (id) onSelectRef.current(id); });
      ready.current = true;
      m.fire('sih-ready');
    });
    map.current = m;
    return () => { m.remove(); map.current = null; ready.current = false; };
  }, []);

  useEffect(() => {
    const m = map.current; if (!m) return;
    const apply = () => {
      (m.getSource('states') as GeoJSONSource | undefined)?.setData((stateOutlines ?? { type: 'FeatureCollection', features: [] }) as GeoJSON.FeatureCollection);
      (m.getSource('districts') as GeoJSONSource | undefined)?.setData((colored ?? { type: 'FeatureCollection', features: [] }) as unknown as GeoJSON.FeatureCollection);
      const feats = ((colored?.features ?? []) as { geometry: { coordinates: number[][][] }; properties: { state_code: string } }[])
        .filter((f) => !focusState || f.properties.state_code === focusState);
      const pts = feats.flatMap((f) => f.geometry.coordinates[0]);
      if (pts.length) {
        const b = pts.reduce((bb, p) => bb.extend(p as [number, number]), new maplibregl.LngLatBounds(pts[0] as [number, number], pts[0] as [number, number]));
        m.fitBounds(b, { padding: 60, duration: 600, maxZoom: 8 });
      }
    };
    if (ready.current) apply(); else m.once('sih-ready' as never, apply);
  }, [colored, stateOutlines, focusState]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    const apply = () => m.getLayer('d-sel') && m.setFilter('d-sel', ['==', ['get', 'region_id'], selectedId ?? '']);
    if (ready.current) apply(); else m.once('sih-ready' as never, apply);
  }, [selectedId]);

  return <div ref={el} className="h-full min-h-[420px] w-full rounded-lg" role="application" aria-label="Interactive map of schematic district tiles" />;
}

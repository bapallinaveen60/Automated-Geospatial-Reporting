import { useEffect } from 'react'
import { GeoJSON, MapContainer, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

function FitBounds({ geometry }: { geometry: GeoJSON.Geometry }) {
  const map = useMap()
  useEffect(() => {
    const bounds = L.geoJSON(geometry).getBounds()
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 })
  }, [geometry, map])
  return null
}

/** Site boundary on an OpenStreetMap basemap, zoomed to fit. */
export function SiteMap({ geometry }: { geometry: GeoJSON.Geometry }) {
  return (
    <div className="map">
      <MapContainer center={[20.5, 78.9]} zoom={5} style={{ height: '100%' }} scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSON
          key={JSON.stringify(geometry)}
          data={geometry}
          style={{ color: '#d92d20', weight: 3, fillOpacity: 0.08 }}
        />
        <FitBounds geometry={geometry} />
      </MapContainer>
    </div>
  )
}

import React, { useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import { createHospitalIcon } from './leafletConfig'
import { Badge, Button } from '../ui'

// Helper component to center, fit bounds, and invalidate size on dimensions/container change
function MapController({ selectedHospital, hospitals }) {
  const map = useMap()

  useEffect(() => {
    // Invalidate map size after DOM layout settles (e.g. mobile drawer/tab switch)
    const timer = setTimeout(() => {
      map.invalidateSize()
    }, 150)

    if (selectedHospital && selectedHospital.latitude && selectedHospital.longitude) {
      map.flyTo([selectedHospital.latitude, selectedHospital.longitude], 14, {
        duration: 1.2,
      })
    } else if (hospitals && hospitals.length > 0) {
      const validCoords = hospitals
        .filter((h) => h.latitude !== null && h.longitude !== null)
        .map((h) => [h.latitude, h.longitude])

      if (validCoords.length > 0) {
        map.fitBounds(validCoords, { padding: [40, 40], maxZoom: 13 })
      }
    }

    return () => clearTimeout(timer)
  }, [selectedHospital, hospitals, map])

  return null
}

export default function HospitalMap({
  hospitals = [],
  selectedHospital = null,
  onSelectHospital = () => {},
  onOpenDetails = () => {},
}) {
  // Filter only hospitals that have valid geographic coordinates
  const mappedHospitals = hospitals.filter(
    (h) => h.latitude !== null && h.longitude !== null
  )

  // Default center: India central coordinates or first hospital
  const defaultCenter =
    mappedHospitals.length > 0
      ? [mappedHospitals[0].latitude, mappedHospitals[0].longitude]
      : [22.3511, 78.6677]

  return (
    <div className="relative w-full h-full min-h-[380px] sm:min-h-[460px] md:min-h-[580px] rounded-2xl overflow-hidden border border-brand-border shadow-clinical-xs bg-brand-ground z-10 flex flex-col">
      <MapContainer
        center={defaultCenter}
        zoom={mappedHospitals.length > 0 ? 5 : 4}
        scrollWheelZoom={false}
        className="w-full flex-1"
        style={{ width: '100%', height: '100%', minHeight: '380px' }}
      >
        {/* OpenStreetMap Tile Layer with Mandatory Copyright Attribution */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />

        <MapController selectedHospital={selectedHospital} hospitals={mappedHospitals} />

        {mappedHospitals.map((hospital) => {
          const isSelected = selectedHospital?.id === hospital.id

          return (
            <Marker
              key={hospital.id}
              position={[hospital.latitude, hospital.longitude]}
              icon={createHospitalIcon(isSelected, hospital.data_source)}
              eventHandlers={{
                click: () => onSelectHospital(hospital),
              }}
            >
              <Popup className="hospital-popup">
                <div className="p-1 space-y-2 max-w-[260px] font-sans">
                  <div className="space-y-1">
                    <Badge
                      variant={hospital.data_source === 'verified' ? 'teal' : 'neutral'}
                      size="sm"
                    >
                      {hospital.data_source === 'verified' ? 'Verified Facility' : 'Sample Record'}
                    </Badge>
                    <h4 className="text-sm font-bold text-brand-text leading-tight pt-1">
                      {hospital.name}
                    </h4>
                    <p className="text-xs text-brand-muted line-clamp-2">
                      {hospital.address}, {hospital.city}
                    </p>
                  </div>

                  {/* Specialty chips */}
                  {hospital.specialties && hospital.specialties.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-0.5">
                      {hospital.specialties.slice(0, 3).map((spec, i) => (
                        <span
                          key={i}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-brand-mint text-brand-deep font-semibold"
                        >
                          {spec}
                        </span>
                      ))}
                      {hospital.specialties.length > 3 && (
                        <span className="text-[10px] text-brand-muted">
                          +{hospital.specialties.length - 3} more
                        </span>
                      )}
                    </div>
                  )}

                  <div className="pt-2 flex items-center justify-between border-t border-brand-border/70">
                    {hospital.phone ? (
                      <span className="text-[11px] text-brand-muted font-medium truncate max-w-[120px]">
                        {hospital.phone}
                      </span>
                    ) : (
                      <span className="text-[10px] text-brand-muted/70">
                        {hospital.city}, {hospital.state}
                      </span>
                    )}

                    <Button
                      variant="link"
                      size="sm"
                      onClick={() => onOpenDetails(hospital)}
                      className="text-xs font-bold text-brand-accent hover:text-brand-deep p-0"
                    >
                      View Details &rarr;
                    </Button>
                  </div>
                </div>
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>

      {/* Floating Map Legend */}
      <div className="absolute bottom-3 left-3 z-[1000] bg-brand-surface/95 backdrop-blur-xs px-3 py-2 rounded-xl border border-brand-border shadow-clinical-sm text-[11px] flex items-center gap-3 select-none">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-brand-primary" aria-hidden="true"></span>
          <span className="text-brand-text font-medium">Verified Partner</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-600" aria-hidden="true"></span>
          <span className="text-brand-muted font-medium">Sample / Demo</span>
        </div>
      </div>
    </div>
  )
}

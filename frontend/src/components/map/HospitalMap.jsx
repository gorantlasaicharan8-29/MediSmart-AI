import React, { useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import { createHospitalIcon } from './leafletConfig'

// Helper component to center and fit bounds on hospital changes
function MapController({ selectedHospital, hospitals }) {
  const map = useMap()

  useEffect(() => {
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
    <div className="relative w-full h-full min-h-[420px] rounded-2xl overflow-hidden border border-slate-200 shadow-xs bg-slate-100 z-10">
      <MapContainer
        center={defaultCenter}
        zoom={mappedHospitals.length > 0 ? 5 : 4}
        scrollWheelZoom={true}
        className="w-full h-full min-h-[420px]"
        style={{ width: '100%', height: '100%' }}
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
                <div className="p-1 space-y-2 max-w-xs">
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-900 leading-tight">
                      {hospital.name}
                    </h4>
                  </div>
                  <p className="text-xs text-slate-600 line-clamp-2">{hospital.address}, {hospital.city}</p>

                  {/* Specialty chips */}
                  {hospital.specialties && hospital.specialties.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-1">
                      {hospital.specialties.slice(0, 3).map((spec, i) => (
                        <span
                          key={i}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-teal-50 text-teal-700 font-medium"
                        >
                          {spec}
                        </span>
                      ))}
                      {hospital.specialties.length > 3 && (
                        <span className="text-[10px] text-slate-400">
                          +{hospital.specialties.length - 3} more
                        </span>
                      )}
                    </div>
                  )}

                  <div className="pt-2 flex items-center justify-between border-t border-slate-100">
                    <span
                      className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${
                        hospital.data_source === 'verified'
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-amber-50 text-amber-700'
                      }`}
                    >
                      {hospital.data_source}
                    </span>
                    <button
                      type="button"
                      onClick={() => onOpenDetails(hospital)}
                      className="text-xs font-semibold text-teal-700 hover:text-teal-800 hover:underline"
                    >
                      View Details →
                    </button>
                  </div>
                </div>
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>

      {/* Floating Map Legend */}
      <div className="absolute bottom-3 left-3 z-[1000] bg-white/95 backdrop-blur-xs px-3 py-2 rounded-xl border border-slate-200/90 shadow-sm text-[11px] flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-teal-600"></span>
          <span className="text-slate-600 font-medium">Verified Facility</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
          <span className="text-slate-600 font-medium">Sample / Unverified</span>
        </div>
      </div>
    </div>
  )
}

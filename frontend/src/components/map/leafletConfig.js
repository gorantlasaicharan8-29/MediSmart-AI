import L from 'leaflet'

/**
 * Creates custom high-resolution SVG medical marker icons for Leaflet.
 * Distinguishes between selected, verified, and sample facilities.
 */
export function createHospitalIcon(isSelected = false, dataSource = 'verified') {
  const isVerified = dataSource === 'verified'
  const primaryColor = isSelected ? '#0f766e' : isVerified ? '#0d9488' : '#d97706'
  const size = isSelected ? 40 : 32

  const svgHtml = `
    <div style="display: flex; align-items: center; justify-content: center; transform: ${
      isSelected ? 'scale(1.15)' : 'scale(1)'
    }; transition: transform 0.2s ease;">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" fill="${primaryColor}" style="filter: drop-shadow(0 4px 6px rgba(15, 23, 42, 0.35));">
        <path d="M12 2C7.589 2 4 5.589 4 10c0 5.25 8 12 8 12s8-6.75 8-12c0-4.411-3.589-8-8-8zm0 13c-2.757 0-5-2.243-5-5s2.243-5 5-5 5 2.243 5 5-2.243 5-5 5z"/>
        <path fill="#ffffff" d="M11 7h2v2h2v2h-2v2h-2v-2H9V9h2z"/>
      </svg>
    </div>
  `

  return L.divIcon({
    html: svgHtml,
    className: 'custom-medical-pin',
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size + 2],
  })
}

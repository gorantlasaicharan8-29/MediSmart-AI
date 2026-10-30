import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getDoctors } from '../../services/api'
import {
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Badge,
  Button,
  ClinicalIcon,
  Skeleton,
} from '../ui'

export default function HospitalDetailModal({
  hospital,
  isOpen = false,
  onClose = () => {},
}) {
  const navigate = useNavigate()
  const [doctors, setDoctors] = useState([])
  const [isLoadingDoctors, setIsLoadingDoctors] = useState(false)
  const [doctorsError, setDoctorsError] = useState(null)

  useEffect(() => {
    if (!isOpen || !hospital?.id) return

    let ignore = false

    async function fetchAffiliated() {
      try {
        setIsLoadingDoctors(true)
        setDoctorsError(null)
        const res = await getDoctors({ hospital_id: hospital.id, page_size: 10 })
        if (!ignore) {
          setDoctors(res?.items || [])
        }
      } catch (err) {
        if (!ignore) {
          setDoctorsError(err.message || 'Unable to load affiliated doctors')
        }
      } finally {
        if (!ignore) {
          setIsLoadingDoctors(false)
        }
      }
    }

    fetchAffiliated()

    return () => {
      ignore = true
    }
  }, [isOpen, hospital?.id])



  if (!isOpen || !hospital) return null

  const hasCoords = hospital.latitude !== null && hospital.longitude !== null

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="lg"
      showCloseButton={false}
      className="max-h-[90vh]"
    >
      {/* Header */}
      <ModalHeader onClose={onClose} showCloseButton={true}>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant={hospital.data_source === 'verified' ? 'teal' : 'neutral'}
              size="sm"
            >
              {hospital.data_source === 'verified' ? 'Verified Facility' : 'Demonstration Record'}
            </Badge>
            <Badge
              variant={hasCoords ? 'mint' : 'neutral'}
              size="sm"
              icon={
                <ClinicalIcon
                  name={hasCoords ? 'map-pin' : 'alert-circle'}
                  size={12}
                  ariaHidden="true"
                />
              }
            >
              {hasCoords ? 'Geocoded Coordinates' : 'Location Pending'}
            </Badge>
          </div>
          <h2 className="text-xl font-bold text-brand-text leading-tight">
            {hospital.name}
          </h2>
          <p className="text-xs text-brand-muted">
            {hospital.address}, {hospital.city}, {hospital.state}
          </p>
        </div>
      </ModalHeader>

      {/* Body */}
      <ModalBody className="space-y-5">
        {/* Contact Information */}
        <div className="p-4 rounded-2xl bg-brand-ground border border-brand-border/80 grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
          <div>
            <span className="text-brand-muted block font-medium mb-0.5">Telephone Inquiries</span>
            <span className="font-bold text-brand-text flex items-center gap-1.5">
              <ClinicalIcon name="heart-pulse" size={14} className="text-brand-accent" ariaHidden="true" />
              {hospital.phone ? (
                <a
                  href={`tel:${hospital.phone}`}
                  className="hover:text-brand-deep hover:underline text-brand-text font-semibold"
                >
                  {hospital.phone}
                </a>
              ) : (
                <span className="text-brand-muted/70 font-normal">Contact number not specified</span>
              )}
            </span>
          </div>
          <div>
            <span className="text-brand-muted block font-medium mb-0.5">Clinical Email Desk</span>
            <span className="font-bold text-brand-text flex items-center gap-1.5">
              <ClinicalIcon name="shield-check" size={14} className="text-brand-accent" ariaHidden="true" />
              {hospital.email ? (
                <a
                  href={`mailto:${hospital.email}`}
                  className="hover:text-brand-deep hover:underline text-brand-text font-semibold"
                >
                  {hospital.email}
                </a>
              ) : (
                <span className="text-brand-muted/70 font-normal">Email desk not specified</span>
              )}
            </span>
          </div>
        </div>

        {/* Clinical Specialties */}
        <div>
          <h3 className="text-xs font-bold text-brand-text uppercase tracking-wider mb-2.5">
            Clinical Specialties
          </h3>
          {hospital.specialties && hospital.specialties.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {hospital.specialties.map((spec, i) => (
                <span
                  key={i}
                  className="text-xs font-semibold px-3 py-1 rounded-xl bg-brand-mint/70 text-brand-deep border border-teal-200/70"
                >
                  {spec}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-brand-muted">No specific departments cataloged.</p>
          )}
        </div>

        {/* Infrastructure & Facilities */}
        <div>
          <h3 className="text-xs font-bold text-brand-text uppercase tracking-wider mb-2.5">
            Facility Infrastructure &amp; Capabilities
          </h3>
          {hospital.facilities && hospital.facilities.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {hospital.facilities.map((fac, i) => (
                <span
                  key={i}
                  className="text-xs font-medium px-3 py-1 rounded-xl bg-brand-ground text-brand-text border border-brand-border/80 flex items-center gap-1"
                >
                  <ClinicalIcon name="check" size={13} className="text-brand-accent" ariaHidden="true" />
                  <span>{fac}</span>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-brand-muted">Standard outpatient facilities available.</p>
          )}
        </div>

        {/* Associated Specialists Section */}
        <div className="pt-2 border-t border-brand-border/70">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-xs font-bold text-brand-text uppercase tracking-wider">
                Practicing Specialists
              </h3>
              <p className="text-[11px] text-brand-muted">
                Doctors affiliated with {hospital.name}
              </p>
            </div>
            {doctors.length > 0 && (
              <Button
                variant="link"
                size="sm"
                onClick={() => {
                  onClose()
                  navigate(`/doctors?hospital_id=${hospital.id}`)
                }}
                className="text-xs font-bold text-brand-accent"
              >
                View all in Directory &rarr;
              </Button>
            )}
          </div>

          {isLoadingDoctors ? (
            <div className="space-y-2 py-1">
              <Skeleton.Line width="w-full" height="h-10" />
              <Skeleton.Line width="w-full" height="h-10" />
            </div>
          ) : doctorsError ? (
            <div className="p-3 rounded-xl bg-brand-ground border border-brand-border text-xs text-brand-muted">
              {doctorsError}
            </div>
          ) : doctors.length === 0 ? (
            <div className="p-4 rounded-xl bg-brand-ground border border-brand-border text-center text-xs text-brand-muted space-y-1">
              <p className="font-semibold text-brand-text">No Specialists Currently Listed</p>
              <p>Appointments for this facility can be requested at the hospital reception desk.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {doctors.map((doc) => (
                <div
                  key={doc.id}
                  className="p-3 rounded-xl bg-brand-ground border border-brand-border flex items-center justify-between gap-3 text-xs"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-full bg-brand-mint text-brand-deep font-bold flex items-center justify-center shrink-0">
                      {doc.user?.full_name?.replace('Dr. ', '')?.charAt(0) || 'D'}
                    </div>
                    <div className="min-w-0">
                      <h4 className="font-bold text-brand-text truncate">
                        {doc.user?.full_name || 'Medical Specialist'}
                      </h4>
                      <p className="text-[11px] text-brand-muted truncate">
                        {doc.specialty} &bull; {doc.experience_years}y Exp.
                      </p>
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      onClose()
                      navigate(`/doctors?search=${encodeURIComponent(doc.user?.full_name || '')}`)
                    }}
                    className="shrink-0 text-xs font-semibold"
                  >
                    View Schedule
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Coordinates & Provenance Box */}
        <div className="p-3.5 rounded-xl bg-brand-ground/60 border border-brand-border text-xs space-y-1.5">
          <div className="flex items-center justify-between text-brand-muted">
            <span>Geographic Position</span>
            <span className="font-mono font-semibold text-brand-text">
              {hasCoords
                ? `${hospital.latitude.toFixed(4)}° N, ${hospital.longitude.toFixed(4)}° E`
                : 'Pending GPS Coordinate Survey'}
            </span>
          </div>
          <div className="flex items-center justify-between text-brand-muted pt-1 border-t border-brand-border/60 text-[11px]">
            <span>Data Attribution</span>
            <span className="font-medium text-brand-text">
              {hospital.source_attribution || 'MediSmart Verified Records'}
            </span>
          </div>
        </div>
      </ModalBody>

      {/* Footer */}
      <ModalFooter>
        <Button
          variant="outline"
          size="md"
          onClick={onClose}
          className="text-xs font-semibold"
        >
          Close Facility Details
        </Button>
        <Button
          variant="primary"
          size="md"
          onClick={() => {
            onClose()
            navigate(`/doctors?hospital_id=${hospital.id}`)
          }}
          className="text-xs font-semibold"
        >
          Explore Hospital Specialists
        </Button>
      </ModalFooter>
    </Modal>
  )
}

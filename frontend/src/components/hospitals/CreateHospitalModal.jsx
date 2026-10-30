import React, { useState } from 'react'
import { createHospital } from '../../services/api'
import {
  Modal,
  ModalBody,
  ModalFooter,
  Button,
  Input,
  Select,
  ClinicalIcon,
} from '../ui'

export default function CreateHospitalModal({
  isOpen = false,
  onClose = () => {},
  onCreated = () => {},
}) {
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [city, setCity] = useState('')
  const [state, setState] = useState('')
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [specialtiesText, setSpecialtiesText] = useState('')
  const [facilitiesText, setFacilitiesText] = useState('')
  const [dataSource, setDataSource] = useState('verified')
  const [sourceAttribution, setSourceAttribution] = useState('© OpenStreetMap contributors')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)

  if (!isOpen) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage(null)
    setIsSubmitting(true)

    try {
      const specialties = specialtiesText
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)

      const facilities = facilitiesText
        .split(',')
        .map((f) => f.trim())
        .filter(Boolean)

      const payload = {
        name: name.trim(),
        address: address.trim(),
        city: city.trim(),
        state: state.trim(),
        latitude: latitude ? parseFloat(latitude) : null,
        longitude: longitude ? parseFloat(longitude) : null,
        phone: phone.trim() || null,
        email: email.trim() || null,
        specialties,
        facilities,
        is_active: true,
        data_source: dataSource,
        source_attribution: sourceAttribution.trim() || null,
      }

      const created = await createHospital(payload)
      onCreated(created)
      onClose()
    } catch (err) {
      setErrorMessage(err.message || 'Failed to create hospital facility. Please check permissions.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="lg"
      title="Add Healthcare Facility"
      subtitle="Register new hospital or clinical center (Authorized Admin)"
      showCloseButton={true}
    >
      <form onSubmit={handleSubmit} noValidate>
        <ModalBody className="space-y-4">
          {errorMessage && (
            <div
              role="alert"
              className="p-3.5 rounded-xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center gap-2"
            >
              <ClinicalIcon name="alert-circle" size={16} ariaHidden="true" />
              <span>{errorMessage}</span>
            </div>
          )}

          <Input
            label="Hospital Facility Name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Apollo Super Speciality Hospital"
            disabled={isSubmitting}
          />

          <Input
            label="Street Address / Area"
            required
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="e.g. Ring Road, Sector 4"
            disabled={isSubmitting}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="City"
              required
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. New Delhi, Mumbai"
              disabled={isSubmitting}
            />
            <Input
              label="State / Region"
              required
              value={state}
              onChange={(e) => setState(e.target.value)}
              placeholder="e.g. Delhi, Maharashtra"
              disabled={isSubmitting}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="Latitude (optional)"
              type="number"
              step="any"
              value={latitude}
              onChange={(e) => setLatitude(e.target.value)}
              placeholder="e.g. 28.5672"
              disabled={isSubmitting}
            />
            <Input
              label="Longitude (optional)"
              type="number"
              step="any"
              value={longitude}
              onChange={(e) => setLongitude(e.target.value)}
              placeholder="e.g. 77.2100"
              disabled={isSubmitting}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="Phone Contact"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91 000 000 0000"
              disabled={isSubmitting}
            />
            <Input
              label="Email Desk"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="contact@hospital.com"
              disabled={isSubmitting}
            />
          </div>

          <Input
            label="Clinical Specialties"
            value={specialtiesText}
            onChange={(e) => setSpecialtiesText(e.target.value)}
            placeholder="Cardiology, Neurology, Pediatrics, Orthopedics (comma-separated)"
            helperText="Separate multiple departments with commas"
            disabled={isSubmitting}
          />

          <Input
            label="Infrastructure & Facilities"
            value={facilitiesText}
            onChange={(e) => setFacilitiesText(e.target.value)}
            placeholder="ICU, Emergency 24/7, Blood Bank, MRI (comma-separated)"
            helperText="Separate facility tags with commas"
            disabled={isSubmitting}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Select
              label="Data Provenance"
              value={dataSource}
              onChange={(e) => setDataSource(e.target.value)}
              disabled={isSubmitting}
            >
              <option value="verified">Verified Facility</option>
              <option value="imported">OpenStreetMap Import</option>
              <option value="sample">Sample / Test Facility</option>
            </Select>

            <Input
              label="Attribution Notice"
              value={sourceAttribution}
              onChange={(e) => setSourceAttribution(e.target.value)}
              placeholder="© OpenStreetMap contributors"
              disabled={isSubmitting}
            />
          </div>
        </ModalBody>

        <ModalFooter>
          <Button
            variant="outline"
            size="md"
            onClick={onClose}
            disabled={isSubmitting}
            className="text-xs font-semibold"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            size="md"
            isLoading={isSubmitting}
            className="text-xs font-semibold"
          >
            Save Facility
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  )
}

import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  uploadMedicalReport,
  getMedicalReports,
  getMedicalReportAnalysis,
  getMedicalReportSummary,
  compareMedicalReports,
  getMedicalParameterTrends,
  deleteMedicalReport,
} from '../../services/api'
import {
  Button,
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  EmptyState,
  SkeletonCard,
  ClinicalIcon,
} from '../../components/ui'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
} from 'recharts'

const DOCUMENT_CATEGORIES = [
  'Complete Blood Count (CBC)',
  'Blood Glucose',
  'HbA1c',
  'Lipid Profile',
  'Liver Function Test (LFT)',
  'Kidney Function Test (KFT)',
  'Thyroid Function Test',
  'Urine Analysis',
  'Other Medical Reports',
]

const TREND_PARAMETERS = [
  'Hemoglobin',
  'HbA1c',
  'Fasting Blood Glucose',
  'Postprandial Blood Glucose',
  'Total Cholesterol',
  'HDL Cholesterol',
  'LDL Cholesterol',
  'Triglycerides',
  'Serum Creatinine',
  'Blood Urea',
  'ALT (SGPT)',
  'AST (SGOT)',
  'TSH',
]

export default function PatientMedicalReports() {
  const [activeTab, setActiveTab] = useState('reports') // 'reports' | 'compare' | 'trends'
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Upload State
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploadCategory, setUploadCategory] = useState('Complete Blood Count (CBC)')
  const [uploadDate, setUploadDate] = useState(() => new Date().toISOString().split('T')[0])
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadSuccess, setUploadSuccess] = useState(null)
  const fileInputRef = useRef(null)

  // Document Details Modal
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [docAnalysis, setDocAnalysis] = useState(null)
  const [docSummary, setDocSummary] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [paramFilter, setParamFilter] = useState('ALL') // 'ALL' | 'ABNORMAL' | 'CRITICAL'

  // Comparison State
  const [selectedForCompare, setSelectedForCompare] = useState([])
  const [comparisonData, setComparisonData] = useState(null)
  const [comparisonLoading, setComparisonLoading] = useState(false)

  // Trends State
  const [trendParam, setTrendParam] = useState('Hemoglobin')
  const [trendData, setTrendData] = useState(null)
  const [trendLoading, setTrendLoading] = useState(false)

  // 1. Fetch Reports List
  const fetchReports = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getMedicalReports()
      setReports(data || [])
    } catch (err) {
      setError(err.message || 'Failed to load medical reports.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchReports()
  }, [fetchReports])

  // 2. Fetch Trend Data when active tab is trends
  const fetchTrends = useCallback(async (paramName) => {
    try {
      setTrendLoading(true)
      const res = await getMedicalParameterTrends(paramName)
      setTrendData(res)
    } catch (err) {
      console.error('Trend fetch error:', err)
    } finally {
      setTrendLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'trends' && trendParam) {
      fetchTrends(trendParam)
    }
  }, [activeTab, trendParam, fetchTrends])

  // 3. Handle File Upload
  const handleFileDrop = (e) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const f = e.dataTransfer.files[0]
      if (f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')) {
        setSelectedFile(f)
      } else {
        alert('Please select a valid PDF file.')
      }
    }
  }

  const handleUploadSubmit = async (e) => {
    e.preventDefault()
    if (!selectedFile) return

    setIsUploading(true)
    setUploadProgress(20)
    setUploadSuccess(null)
    setError(null)

    const formData = new FormData()
    formData.append('file', selectedFile)
    formData.append('document_category', uploadCategory)
    if (uploadDate) formData.append('report_date', uploadDate)

    try {
      setUploadProgress(60)
      const doc = await uploadMedicalReport(formData)
      setUploadProgress(100)
      setUploadSuccess(`Report "${doc.original_filename}" uploaded and analyzed successfully!`)
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await fetchReports()
    } catch (err) {
      setError(err.message || 'Upload failed.')
    } finally {
      setIsUploading(false)
      setUploadProgress(0)
    }
  }

  // 4. Open Document Analysis Modal
  const openDocumentDetails = async (doc) => {
    setSelectedDoc(doc)
    setAnalysisLoading(true)
    setDocAnalysis(null)
    setDocSummary(null)
    try {
      const [analysis, summary] = await Promise.all([
        getMedicalReportAnalysis(doc.id),
        getMedicalReportSummary(doc.id).catch(() => null),
      ])
      setDocAnalysis(analysis)
      setDocSummary(summary || analysis?.summary_json)
    } catch (err) {
      console.error('Failed to load analysis:', err)
    } finally {
      setAnalysisLoading(false)
    }
  }

  // 5. Compare Selected Reports
  const handleCompareClick = async () => {
    if (selectedForCompare.length < 2) return
    setActiveTab('compare')
    setComparisonLoading(true)
    try {
      const res = await compareMedicalReports(selectedForCompare)
      setComparisonData(res)
    } catch (err) {
      setError(err.message || 'Failed to compare reports.')
    } finally {
      setComparisonLoading(false)
    }
  }

  const toggleSelectForCompare = (docId) => {
    setSelectedForCompare((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    )
  }

  // 6. Delete Report
  const handleDeleteDoc = async (docId, e) => {
    e.stopPropagation()
    if (!window.confirm('Are you sure you want to remove this medical report?')) return
    try {
      await deleteMedicalReport(docId)
      setSelectedForCompare((prev) => prev.filter((id) => id !== docId))
      await fetchReports()
    } catch (err) {
      alert(err.message || 'Failed to delete report.')
    }
  }

  // Helper for Range Status Badges
  const renderRangeStatusBadge = (status, isCrit) => {
    if (isCrit || status === 'CRITICAL_REVIEW_REQUIRED') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-ping" />
          Critical Review
        </span>
      )
    }
    switch (status) {
      case 'WITHIN_RANGE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <ClinicalIcon name="check" size={12} className="text-emerald-700" />
            Within Range
          </span>
        )
      case 'BELOW_RANGE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            ↓ Below Range
          </span>
        )
      case 'ABOVE_RANGE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            ↑ Above Range
          </span>
        )
      case 'EXTRACTION_REQUIRES_VERIFICATION':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            Verify Value
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
            No Range
          </span>
        )
    }
  }

  // Filtered parameters for details modal
  const filteredParameters = (docAnalysis?.parameters || []).filter((p) => {
    if (paramFilter === 'ABNORMAL') return p.range_status !== 'WITHIN_RANGE'
    if (paramFilter === 'CRITICAL') return p.is_critical || p.range_status === 'CRITICAL_REVIEW_REQUIRED'
    return true
  })

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-brand-border/60 pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
              AI Medical Report Analysis
            </h1>
            <span className="px-2.5 py-0.5 rounded-md text-[11px] font-bold bg-teal-100 text-teal-800 border border-teal-200 uppercase tracking-wider">
              Phase 12.0
            </span>
          </div>
          <p className="text-sm text-brand-muted mt-1 max-w-3xl">
            Upload diagnostic blood tests, metabolic panels, and lab reports. MediSmart AI extracts structured parameters,
            compares measurements against laboratory reference ranges, and visualizes historical trends.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selectedForCompare.length >= 2 && (
            <Button
              variant="accent"
              size="sm"
              onClick={handleCompareClick}
              className="flex items-center gap-1.5 shadow-sm"
            >
              <ClinicalIcon name="activity" size={16} />
              Compare ({selectedForCompare.length}) Reports
            </Button>
          )}
        </div>
      </div>

      {/* Assistive Governance Disclaimer Banner */}
      <div className="p-3.5 rounded-xl bg-teal-50/80 border border-teal-200/80 flex items-start gap-3">
        <ClinicalIcon name="shield" size={18} className="text-teal-700 shrink-0 mt-0.5" />
        <p className="text-xs text-teal-900 leading-relaxed">
          <strong className="font-semibold">Assistive Medical Intelligence:</strong> This module organizes laboratory
          data and flags measurements relative to the reference ranges printed on your original report. It does not
          independently diagnose conditions or prescribe treatments. Always consult your attending doctor for medical advice.
        </p>
      </div>

      {/* Upload Card */}
      <div className="bg-brand-surface rounded-2xl border border-brand-border/80 shadow-clinical-sm p-6">
        <h2 className="text-base font-bold text-brand-text mb-4 flex items-center gap-2">
          <ClinicalIcon name="upload" size={18} className="text-brand-accent" />
          Upload New Medical Report (PDF)
        </h2>

        <form onSubmit={handleUploadSubmit} className="space-y-4">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleFileDrop}
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${
              selectedFile
                ? 'border-brand-accent bg-brand-mint/20'
                : 'border-brand-border hover:border-brand-accent/70 bg-brand-ground/40'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              id="report-file-input"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && setSelectedFile(e.target.files[0])}
            />
            {selectedFile ? (
              <div className="flex flex-col items-center justify-center space-y-2">
                <span className="w-10 h-10 rounded-full bg-brand-mint text-brand-deep flex items-center justify-center font-bold">
                  PDF
                </span>
                <span className="text-sm font-semibold text-brand-text">{selectedFile.name}</span>
                <span className="text-xs text-brand-muted">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready to analyze
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="text-xs text-rose-600 hover:underline pt-1"
                >
                  Choose a different file
                </button>
              </div>
            ) : (
              <label
                htmlFor="report-file-input"
                className="cursor-pointer flex flex-col items-center justify-center space-y-2"
              >
                <div className="w-12 h-12 rounded-full bg-brand-ground flex items-center justify-center text-brand-muted">
                  <ClinicalIcon name="document" size={24} />
                </div>
                <span className="text-sm font-semibold text-brand-text">
                  Click to select a PDF report or drag and drop here
                </span>
                <span className="text-xs text-brand-muted">
                  Supports digital lab reports and scanned PDFs (up to 15 MB)
                </span>
              </label>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-brand-muted uppercase tracking-wider mb-1">
                Report Category
              </label>
              <select
                value={uploadCategory}
                onChange={(e) => setUploadCategory(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-xl border border-brand-border bg-white text-brand-text focus:ring-2 focus:ring-brand-accent"
              >
                {DOCUMENT_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-brand-muted uppercase tracking-wider mb-1">
                Report Collection Date
              </label>
              <input
                type="date"
                value={uploadDate}
                onChange={(e) => setUploadDate(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-xl border border-brand-border bg-white text-brand-text focus:ring-2 focus:ring-brand-accent"
              />
            </div>
          </div>

          {isUploading && (
            <div className="space-y-1.5 pt-2">
              <div className="flex justify-between text-xs text-brand-muted">
                <span>Analyzing document with PyMuPDF & RapidOCR...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-brand-ground rounded-full h-2 overflow-hidden">
                <div
                  className="bg-brand-accent h-2 transition-all duration-300 rounded-full"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {uploadSuccess && (
            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium">
              {uploadSuccess}
            </div>
          )}

          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium">
              {error}
            </div>
          )}

          <div className="flex justify-end pt-2">
            <Button
              type="submit"
              variant="primary"
              disabled={!selectedFile || isUploading}
              loading={isUploading}
              className="px-6"
            >
              Upload & Extract Parameters
            </Button>
          </div>
        </form>
      </div>

      {/* Navigation Subtabs */}
      <div className="flex items-center gap-2 border-b border-brand-border">
        <button
          onClick={() => setActiveTab('reports')}
          className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'reports'
              ? 'border-brand-accent text-brand-accent'
              : 'border-transparent text-brand-muted hover:text-brand-text'
          }`}
        >
          My Medical Reports ({reports.length})
        </button>
        <button
          onClick={() => {
            if (selectedForCompare.length >= 2) handleCompareClick()
            else setActiveTab('compare')
          }}
          className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'compare'
              ? 'border-brand-accent text-brand-accent'
              : 'border-transparent text-brand-muted hover:text-brand-text'
          }`}
        >
          Historical Comparison {selectedForCompare.length > 0 && `(${selectedForCompare.length} selected)`}
        </button>
        <button
          onClick={() => setActiveTab('trends')}
          className={`pb-3 px-4 text-sm font-semibold border-b-2 transition-all ${
            activeTab === 'trends'
              ? 'border-brand-accent text-brand-accent'
              : 'border-transparent text-brand-muted hover:text-brand-text'
          }`}
        >
          Parameter Trends & Charts
        </button>
      </div>

      {/* Tab 1: Reports List */}
      {activeTab === 'reports' && (
        <div className="space-y-4">
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SkeletonCard />
              <SkeletonCard />
            </div>
          ) : reports.length === 0 ? (
            <EmptyState
              title="No medical reports uploaded yet"
              description="Upload your blood tests or laboratory reports above to view automated AI extraction and reference range analysis."
            />
          ) : (
            <div className="bg-brand-surface rounded-2xl border border-brand-border/80 shadow-clinical-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-brand-border/60 text-left text-sm">
                  <thead className="bg-brand-ground/60 text-brand-muted uppercase tracking-wider text-xs font-semibold">
                    <tr>
                      <th className="py-3.5 px-4 w-12 text-center">Compare</th>
                      <th className="py-3.5 px-4">Document / File</th>
                      <th className="py-3.5 px-4">Category</th>
                      <th className="py-3.5 px-4">Report Date</th>
                      <th className="py-3.5 px-4">Status</th>
                      <th className="py-3.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-brand-border/40 text-brand-text">
                    {reports.map((doc) => {
                      const isSelected = selectedForCompare.includes(doc.id)
                      return (
                        <tr
                          key={doc.id}
                          onClick={() => openDocumentDetails(doc)}
                          className={`hover:bg-brand-ground/40 cursor-pointer transition-colors ${
                            isSelected ? 'bg-teal-50/50' : ''
                          }`}
                        >
                          <td
                            className="py-3.5 px-4 text-center"
                            onClick={(e) => {
                              e.stopPropagation()
                              toggleSelectForCompare(doc.id)
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelectForCompare(doc.id)}
                              className="rounded border-brand-border text-brand-accent focus:ring-brand-accent cursor-pointer"
                            />
                          </td>
                          <td className="py-3.5 px-4 font-semibold text-brand-text">
                            <div className="flex items-center gap-2">
                              <span className="p-1.5 rounded-lg bg-brand-ground text-brand-muted">
                                <ClinicalIcon name="document" size={16} />
                              </span>
                              <span className="truncate max-w-xs">{doc.original_filename}</span>
                            </div>
                          </td>
                          <td className="py-3.5 px-4 text-xs">
                            <span className="px-2.5 py-1 rounded-md bg-teal-50 text-teal-800 border border-teal-200/60 font-medium">
                              {doc.document_category}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-xs text-brand-muted font-medium">
                            {doc.report_date || 'N/A'}
                          </td>
                          <td className="py-3.5 px-4">
                            {doc.processing_status === 'COMPLETED' ? (
                              <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                                <ClinicalIcon name="check" size={12} />
                                Analyzed
                              </span>
                            ) : doc.processing_status === 'FAILED' ? (
                              <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
                                Failed
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200 animate-pulse">
                                Processing...
                              </span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-right space-x-2" onClick={(e) => e.stopPropagation()}>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openDocumentDetails(doc)}
                              className="text-xs font-medium"
                            >
                              View Analysis
                            </Button>
                            <a
                              href={`/api/v1/medical-reports/${doc.id}/download`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center text-xs font-medium text-brand-muted hover:text-brand-text px-2 py-1"
                            >
                              PDF
                            </a>
                            <button
                              onClick={(e) => handleDeleteDoc(doc.id, e)}
                              className="text-xs text-rose-500 hover:text-rose-700 p-1"
                              title="Delete document"
                            >
                              <ClinicalIcon name="trash" size={14} />
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Historical Comparison */}
      {activeTab === 'compare' && (
        <div className="space-y-6">
          {selectedForCompare.length < 2 ? (
            <div className="p-8 text-center bg-brand-surface rounded-2xl border border-brand-border">
              <ClinicalIcon name="activity" size={32} className="mx-auto text-brand-muted mb-2" />
              <h3 className="text-base font-bold text-brand-text">Select at least 2 reports to compare</h3>
              <p className="text-xs text-brand-muted mt-1 max-w-md mx-auto">
                Go to the &quot;My Medical Reports&quot; tab and check the boxes next to the reports you wish to compare
                (e.g., previous vs current Lipid Profile or HbA1c).
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={() => setActiveTab('reports')}
              >
                Go to Reports List
              </Button>
            </div>
          ) : comparisonLoading ? (
            <div className="p-8 text-center">
              <div className="w-8 h-8 border-2 border-brand-accent border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <span className="text-xs text-brand-muted">Comparing parameters across reports...</span>
            </div>
          ) : comparisonData ? (
            <div className="space-y-6">
              {/* Reports Compared Header */}
              <div className="bg-brand-surface rounded-2xl border border-brand-border p-5">
                <h3 className="text-sm font-bold text-brand-text mb-3">Comparing {comparisonData.reports_compared.length} Medical Reports</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {comparisonData.reports_compared.map((r, idx) => (
                    <div key={r.document_id} className="p-3 rounded-xl bg-brand-ground/50 border border-brand-border text-xs">
                      <span className="text-brand-muted block font-semibold">Report {idx + 1} ({r.report_date})</span>
                      <span className="font-bold text-brand-text truncate block mt-0.5">{r.original_filename}</span>
                      <span className="text-[11px] text-teal-800">{r.document_category}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Comparison Table */}
              <div className="bg-brand-surface rounded-2xl border border-brand-border overflow-hidden">
                <table className="min-w-full divide-y divide-brand-border text-left text-sm">
                  <thead className="bg-brand-ground/60 text-brand-muted text-xs uppercase font-semibold">
                    <tr>
                      <th className="py-3 px-4">Parameter</th>
                      <th className="py-3 px-4">Previous Value</th>
                      <th className="py-3 px-4">Current Value</th>
                      <th className="py-3 px-4">Delta (Difference)</th>
                      <th className="py-3 px-4">% Change</th>
                      <th className="py-3 px-4">Trend</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-brand-border/40 text-brand-text">
                    {comparisonData.parameters.map((p) => {
                      if (!p.unit_compatible) {
                        return (
                          <tr key={p.canonical_name} className="bg-amber-50/40">
                            <td className="py-3 px-4 font-semibold text-brand-text">{p.canonical_name}</td>
                            <td colSpan={5} className="py-3 px-4 text-xs text-amber-800 italic">
                              ⚠ {p.note || 'Unit mismatch: measurements cannot be mathematically compared.'}
                            </td>
                          </tr>
                        )
                      }
                      const isUp = p.delta > 0
                      const isDown = p.delta < 0
                      return (
                        <tr key={p.canonical_name} className="hover:bg-brand-ground/30">
                          <td className="py-3 px-4 font-semibold text-brand-text">
                            {p.canonical_name}
                            <span className="text-xs text-brand-muted ml-1.5 font-normal">({p.unit})</span>
                          </td>
                          <td className="py-3 px-4 text-xs font-mono">{p.previous_value ?? '—'}</td>
                          <td className="py-3 px-4 text-xs font-mono font-bold">{p.current_value ?? '—'}</td>
                          <td className="py-3 px-4 text-xs font-mono">
                            {p.delta !== null ? (
                              <span className={isUp ? 'text-amber-800 font-semibold' : isDown ? 'text-blue-800 font-semibold' : 'text-slate-600'}>
                                {isUp ? `+${p.delta}` : p.delta}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="py-3 px-4 text-xs font-mono">
                            {p.percent_change !== null ? (
                              <span>{p.percent_change > 0 ? `+${p.percent_change}%` : `${p.percent_change}%`}</span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="py-3 px-4 text-xs">
                            {p.trend === 'INCREASING' && (
                              <span className="inline-flex items-center gap-1 font-bold text-amber-800">
                                ↑ Increasing
                              </span>
                            )}
                            {p.trend === 'DECREASING' && (
                              <span className="inline-flex items-center gap-1 font-bold text-blue-800">
                                ↓ Decreasing
                              </span>
                            )}
                            {p.trend === 'STABLE' && (
                              <span className="inline-flex items-center gap-1 text-slate-600">
                                → Stable
                              </span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <p className="text-xs text-brand-muted italic">{comparisonData.disclaimer}</p>
            </div>
          ) : null}
        </div>
      )}

      {/* Tab 3: Trends & Visualizations */}
      {activeTab === 'trends' && (
        <div className="space-y-6">
          <div className="bg-brand-surface rounded-2xl border border-brand-border p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-brand-text">Medical Parameter Trends</h2>
                <p className="text-xs text-brand-muted">
                  View chronological trajectory of your lab parameters across all uploaded reports.
                </p>
              </div>
              <div className="w-full sm:w-64">
                <select
                  value={trendParam}
                  onChange={(e) => setTrendParam(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-xl border border-brand-border bg-white text-brand-text focus:ring-2 focus:ring-brand-accent font-semibold"
                >
                  {TREND_PARAMETERS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {trendLoading ? (
              <div className="h-64 flex items-center justify-center">
                <div className="w-8 h-8 border-2 border-brand-accent border-t-transparent rounded-full animate-spin" />
              </div>
            ) : trendData?.data_points?.length ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs text-brand-muted bg-brand-ground/40 p-3 rounded-xl border border-brand-border">
                  <span>Parameter: <strong className="text-brand-text">{trendData.parameter_name}</strong></span>
                  <span>Unit: <strong className="text-brand-text">{trendData.unit}</strong></span>
                  {trendData.reference_range_low !== null && trendData.reference_range_high !== null && (
                    <span>
                      Normal Reference Range:{' '}
                      <strong className="text-emerald-700">
                        {trendData.reference_range_low} – {trendData.reference_range_high} {trendData.unit}
                      </strong>
                    </span>
                  )}
                </div>

                <div className="h-72 w-full pt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trendData.data_points} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            const data = payload[0].payload
                            return (
                              <div className="bg-white p-3 rounded-xl shadow-lg border border-brand-border text-xs space-y-1">
                                <p className="font-bold text-brand-text">{data.date}</p>
                                <p className="text-brand-accent font-semibold">
                                  {trendData.parameter_name}: {data.value} {data.unit}
                                </p>
                                <p className="text-[11px] text-brand-muted truncate max-w-xs">{data.filename}</p>
                                {renderRangeStatusBadge(data.range_status, data.is_critical)}
                              </div>
                            )
                          }
                          return null
                        }}
                      />
                      {/* Normal Reference Area Shading */}
                      {trendData.reference_range_low !== null && trendData.reference_range_high !== null && (
                        <ReferenceArea
                          y1={trendData.reference_range_low}
                          y2={trendData.reference_range_high}
                          fill="#10b981"
                          fillOpacity={0.12}
                        />
                      )}
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#0d9488"
                        strokeWidth={3}
                        dot={{ r: 5, fill: '#0d9488' }}
                        activeDot={{ r: 7 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-brand-muted">
                No historical records found for {trendParam}. Upload reports containing this parameter to see trends.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Document Details & Analysis Modal */}
      {selectedDoc && (
        <Modal isOpen={!!selectedDoc} onClose={() => setSelectedDoc(null)} size="2xl">
          <ModalHeader onClose={() => setSelectedDoc(null)}>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-teal-100 text-teal-800">
                <ClinicalIcon name="document" size={18} />
              </span>
              <div>
                <h3 className="text-base font-bold text-brand-text truncate max-w-md">
                  {selectedDoc.original_filename}
                </h3>
                <span className="text-xs text-brand-muted">
                  {selectedDoc.document_category} • {selectedDoc.report_date || 'Date unrecorded'}
                </span>
              </div>
            </div>
          </ModalHeader>
          <ModalBody>
            {analysisLoading ? (
              <div className="p-8 text-center">
                <div className="w-8 h-8 border-2 border-brand-accent border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                <span className="text-xs text-brand-muted">Loading structured parameter extraction...</span>
              </div>
            ) : (
              <div className="space-y-6">
                {/* 10-Section Report Summary Card */}
                {docSummary && (
                  <div className="p-4 rounded-xl bg-brand-ground/40 border border-brand-border space-y-3">
                    <h4 className="text-xs font-bold text-brand-muted uppercase tracking-wider">
                      AI Executive Summary
                    </h4>
                    <p className="text-sm text-brand-text leading-relaxed font-medium">
                      {docSummary.report_overview}
                    </p>

                    {/* Metric Pills */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                      <div className="p-2.5 rounded-lg bg-white border border-brand-border text-center">
                        <span className="text-xs text-brand-muted block">Extracted</span>
                        <span className="text-lg font-extrabold text-brand-text">
                          {docSummary.total_parameters_extracted}
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-center">
                        <span className="text-xs text-emerald-800 block">In Range</span>
                        <span className="text-lg font-extrabold text-emerald-800">
                          {docSummary.parameters_within_range_count}
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-center">
                        <span className="text-xs text-amber-800 block">Out of Range</span>
                        <span className="text-lg font-extrabold text-amber-800">
                          {docSummary.parameters_below_range_count + docSummary.parameters_above_range_count}
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-center">
                        <span className="text-xs text-rose-800 block">Critical</span>
                        <span className="text-lg font-extrabold text-rose-800">
                          {docSummary.critical_alerts_count}
                        </span>
                      </div>
                    </div>

                    {/* Observations */}
                    {docSummary.important_observations?.length > 0 && (
                      <div className="pt-2 space-y-1">
                        <span className="text-xs font-bold text-brand-text block">Important Observations:</span>
                        <ul className="list-disc list-inside space-y-1 text-xs text-brand-text">
                          {docSummary.important_observations.map((obs, i) => (
                            <li key={i} className="leading-relaxed">
                              {obs}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Parameters Filter & Table */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-brand-muted uppercase tracking-wider">
                      Extracted Parameters ({filteredParameters.length})
                    </h4>
                    <div className="flex items-center gap-1.5 text-xs">
                      <button
                        onClick={() => setParamFilter('ALL')}
                        className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                          paramFilter === 'ALL'
                            ? 'bg-brand-accent text-white'
                            : 'bg-brand-ground text-brand-muted hover:text-brand-text'
                        }`}
                      >
                        All
                      </button>
                      <button
                        onClick={() => setParamFilter('ABNORMAL')}
                        className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                          paramFilter === 'ABNORMAL'
                            ? 'bg-amber-600 text-white'
                            : 'bg-brand-ground text-brand-muted hover:text-brand-text'
                        }`}
                      >
                        Abnormal Only
                      </button>
                      <button
                        onClick={() => setParamFilter('CRITICAL')}
                        className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                          paramFilter === 'CRITICAL'
                            ? 'bg-rose-600 text-white'
                            : 'bg-brand-ground text-brand-muted hover:text-brand-text'
                        }`}
                      >
                        Critical Alerts
                      </button>
                    </div>
                  </div>

                  <div className="rounded-xl border border-brand-border overflow-hidden">
                    <table className="min-w-full divide-y divide-brand-border text-left text-xs">
                      <thead className="bg-brand-ground/60 text-brand-muted font-semibold">
                        <tr>
                          <th className="py-2.5 px-3">Parameter</th>
                          <th className="py-2.5 px-3">Result</th>
                          <th className="py-2.5 px-3">Unit</th>
                          <th className="py-2.5 px-3">Reference Range</th>
                          <th className="py-2.5 px-3">Status</th>
                          <th className="py-2.5 px-3 text-right">Verification</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-brand-border/40 text-brand-text">
                        {filteredParameters.map((p) => (
                          <tr key={p.id} className="hover:bg-brand-ground/30">
                            <td className="py-2.5 px-3 font-semibold text-brand-text">
                              {p.canonical_name}
                              <span className="block text-[10px] text-brand-muted font-normal">
                                Orig: {p.parameter_name}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 font-mono font-bold text-sm">
                              {p.extracted_value}
                            </td>
                            <td className="py-2.5 px-3 text-brand-muted">{p.original_unit || '—'}</td>
                            <td className="py-2.5 px-3 font-mono text-brand-muted">
                              {p.reference_range_text || 'None reported'}
                            </td>
                            <td className="py-2.5 px-3">
                              {renderRangeStatusBadge(p.range_status, p.is_critical)}
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              {p.verification_status === 'DOCTOR_VERIFIED' ? (
                                <span className="text-[10px] font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                                  Verified
                                </span>
                              ) : p.verification_status === 'DOCTOR_CORRECTED' ? (
                                <span className="text-[10px] font-bold text-indigo-800 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                                  Corrected
                                </span>
                              ) : (
                                <span className="text-[10px] text-slate-400">Unverified</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </ModalBody>
          <ModalFooter>
            <div className="flex justify-between w-full items-center">
              <a
                href={`/api/v1/medical-reports/${selectedDoc.id}/download`}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-brand-accent hover:underline font-semibold flex items-center gap-1"
              >
                <ClinicalIcon name="download" size={14} /> Download Original Laboratory PDF
              </a>
              <Button variant="outline" size="sm" onClick={() => setSelectedDoc(null)}>
                Close
              </Button>
            </div>
          </ModalFooter>
        </Modal>
      )}
    </div>
  )
}

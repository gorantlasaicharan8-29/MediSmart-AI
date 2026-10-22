import React, { useState, useEffect } from 'react'
import { getMLServiceStatus } from '../../services/api'

export default function MLStatusBadge({ compact = false }) {
  const [status, setStatus] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isUnavailable, setIsUnavailable] = useState(false)
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    let isMounted = true

    const checkStatus = async () => {
      try {
        const data = await getMLServiceStatus()
        if (isMounted) {
          setStatus(data)
          setIsUnavailable(false)
        }
      } catch {
        if (isMounted) {
          setIsUnavailable(true)
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    checkStatus()
    return () => {
      isMounted = false
    }
  }, [])

  if (isLoading) {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-500 border border-slate-200 animate-pulse">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
        <span>Checking AI Engine...</span>
      </div>
    )
  }

  if (isUnavailable || !status) {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
        <span>AI Engine: Offline (Standard Heuristics)</span>
      </div>
    )
  }

  const isModelsReady =
    status.waiting_time_model?.artifact_exists && status.noshow_model?.artifact_exists

  return (
    <>
      <button
        type="button"
        onClick={() => setShowModal(true)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-teal-50 hover:bg-teal-100/80 text-teal-800 border border-teal-200 transition-colors shadow-2xs cursor-pointer group"
        title="View ML Model Status & Synthetic Provenance"
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${isModelsReady ? 'bg-emerald-500' : 'bg-amber-500'}`}
        ></span>
        <span>
          {compact
            ? 'AI Active (Synthetic)'
            : 'AI Prediction Engine Active'}
        </span>
        <span className="text-[10px] text-teal-600 group-hover:text-teal-900 font-mono">ℹ</span>
      </button>

      {/* Provenance & Disclaimer Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 space-y-5 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <span className="text-xl">🤖</span>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    MediSmart ML Prediction Engine
                  </h3>
                  <p className="text-xs text-slate-500">Operational Machine Learning Services</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg text-lg leading-none"
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            {/* Model Architecture Details */}
            <div className="space-y-3 text-xs">
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1.5">
                <div className="flex items-center justify-between font-bold text-slate-800">
                  <span>⏱️ Waiting-Time Prediction</span>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800">
                    Online
                  </span>
                </div>
                <p className="text-slate-600">
                  Model: <span className="font-mono text-slate-800">{status.waiting_time_model?.model_name || 'XGBoost Regressor'}</span> (v1.0.0)
                </p>
                <p className="text-slate-500 text-[11px]">
                  Estimates clinic queue wait time from arrival timing, queue position, department, and doctor pacing. Enforces non-negative minutes.
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1.5">
                <div className="flex items-center justify-between font-bold text-slate-800">
                  <span>📅 Appointment No-Show Prediction</span>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800">
                    Online
                  </span>
                </div>
                <p className="text-slate-600">
                  Model: <span className="font-mono text-slate-800">{status.noshow_model?.model_name || 'Logistic Regression'}</span> (Decision Threshold: 0.50)
                </p>
                <p className="text-slate-500 text-[11px]">
                  Evaluates scheduling lead time, fee, day of week, and historical appointment ratios into an illustrative probability band.
                </p>
              </div>
            </div>

            {/* Strict Synthetic Disclaimer */}
            <div className="p-4 rounded-xl bg-amber-50/80 border border-amber-200 text-amber-900 text-xs space-y-1.5">
              <div className="flex items-center gap-1.5 font-bold text-amber-950">
                <span>⚠️</span>
                <span>Mandatory Synthetic Data Disclosure</span>
              </div>
              <p className="leading-relaxed text-[11px] text-amber-900/90">
                All underlying machine learning models are trained exclusively on reproducible synthetic queue simulation and appointment datasets.
              </p>
              <p className="text-[11px] font-semibold text-amber-950 pt-1 border-t border-amber-200/60">
                These estimates are illustrative demonstration aids only and are NOT clinically calibrated or diagnostic instruments.
              </p>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-slate-900 text-white hover:bg-slate-800 transition-colors"
              >
                Understood
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

"""
Core Processing Engine for Medical Document Analysis, Text/OCR Extraction,
Parameter Normalization, Range Evaluation, Summarization, and Historical Comparison.
Part of MediSmart AI Phase 12.0.
"""
import hashlib
import io
import logging
import os
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pymupdf  # PyMuPDF
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.doctor import Doctor
from app.models.medical_report import (
    ExtractedMedicalParameter,
    MedicalDocument,
    MedicalParameterCorrection,
    MedicalReportAnalysis,
    MedicalReportReview,
)
from app.models.user import User
from app.services.clinical_audit_service import clinical_audit_service
from app.services.medical_parameters_registry import (
    MEDICAL_PARAMETERS_REGISTRY,
    MedicalParameterSpec,
    convert_parameter_value,
    lookup_parameter_spec,
    normalize_unit,
)

logger = logging.getLogger("medismart.services.medical_report")

# Lazy-loaded RapidOCR instance to optimize process memory
_rapid_ocr_instance = None


def get_ocr_engine():
    global _rapid_ocr_instance
    if _rapid_ocr_instance is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapid_ocr_instance = RapidOCR()
            logger.info("RapidOCR engine initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize RapidOCR engine: {e}")
            _rapid_ocr_instance = None
    return _rapid_ocr_instance


class MedicalReportService:
    """Centralized service for medical document extraction, analysis, and clinical governance."""

    @classmethod
    def ensure_storage_dir(cls) -> Path:
        storage_path = settings.MEDICAL_REPORTS_STORAGE_DIR
        storage_path.mkdir(parents=True, exist_ok=True)
        return storage_path

    @classmethod
    def calculate_sha256(cls, file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()

    @classmethod
    def validate_pdf_content(cls, file_bytes: bytes, filename: str) -> None:
        """Validates file magic bytes, size constraints, and PDF structure integrity."""
        if len(file_bytes) > settings.MAX_REPORT_FILE_SIZE_BYTES:
            max_mb = settings.MAX_REPORT_FILE_SIZE_BYTES // (1024 * 1024)
            raise ValueError(f"File size exceeds maximum permitted limit of {max_mb} MB.")
        
        # Magic bytes check for PDF
        if not file_bytes.startswith(b"%PDF-"):
            raise ValueError("Invalid file format. Uploaded file is not a valid PDF document.")

        # PDF structure integrity check via PyMuPDF
        try:
            test_doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            if test_doc.page_count < 1:
                test_doc.close()
                raise ValueError("PDF document contains no valid pages.")
            test_doc.close()
        except Exception as pdf_err:
            raise ValueError(f"Invalid or corrupted PDF document: {pdf_err}")

    # ---------------------------------------------------------------------------
    # 1. Document Upload & Storage
    # ---------------------------------------------------------------------------
    @classmethod
    async def upload_and_save_document(
        cls,
        patient_id: uuid.UUID,
        uploader: User,
        original_filename: str,
        file_bytes: bytes,
        document_category: str = "Other Medical Reports",
        report_date: Optional[date] = None,
        db: Optional[AsyncSession] = None,
    ) -> MedicalDocument:
        """
        Validates, stores physical file, computes SHA-256, and records MedicalDocument row.
        Detects duplicates for the same patient.
        """
        cls.validate_pdf_content(file_bytes, original_filename)
        sha256_hash = cls.calculate_sha256(file_bytes)

        # Duplicate check if database session provided
        if db:
            dup_query = select(MedicalDocument).where(
                and_(
                    MedicalDocument.patient_id == patient_id,
                    MedicalDocument.sha256_hash == sha256_hash,
                    MedicalDocument.is_deleted == False,
                )
            )
            dup_res = await db.execute(dup_query)
            existing_doc = dup_res.scalar_one_or_none()
            if existing_doc:
                logger.info(f"Duplicate document uploaded for patient {patient_id}. Reusing existing doc {existing_doc.id}")
                return existing_doc

        # Generate secure unguessable stored filename
        stored_filename = f"{uuid.uuid4().hex}.pdf"
        storage_dir = cls.ensure_storage_dir()
        physical_path = storage_dir / stored_filename

        with open(physical_path, "wb") as f:
            f.write(file_bytes)

        # Sanitize filename against path traversal and dangerous characters
        sanitized_filename = Path(original_filename).name
        sanitized_filename = re.sub(r'[\\/:*?"<>|\x00]', '_', sanitized_filename)[:250]
        if not sanitized_filename:
            sanitized_filename = "medical_report.pdf"

        doc = MedicalDocument(
            id=uuid.uuid4(),
            patient_id=patient_id,
            uploaded_by=uploader.id,
            original_filename=sanitized_filename,
            stored_filename=stored_filename,
            mime_type="application/pdf",
            file_size_bytes=len(file_bytes),
            sha256_hash=sha256_hash,
            document_category=document_category or "Other Medical Reports",
            report_date=report_date or date.today(),
            processing_status="PENDING",
            is_deleted=False,
        )

        if db:
            db.add(doc)
            await db.flush()

        return doc

    # ---------------------------------------------------------------------------
    # 2. Text Extraction & OCR Fallback
    # ---------------------------------------------------------------------------
    @classmethod
    def extract_text_from_pdf(cls, file_path: Union[str, Path]) -> Tuple[List[Dict[str, Any]], int, int]:
        """
        Extracts text from PDF page by page using PyMuPDF.
        Applies RapidOCR fallback for scanned or low-text pages (< 40 chars).
        Returns (pages_data, total_pages, ocr_applied_count).
        """
        doc = pymupdf.open(str(file_path))
        total_pages = len(doc)
        ocr_applied_count = 0
        pages_data = []

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_text = page.get_text("text").strip()
            ocr_used = False

            # If digital text is missing or extremely short, fallback to OCR
            if len(page_text) < 40:
                ocr_engine = get_ocr_engine()
                if ocr_engine is not None:
                    try:
                        # Render page to image pixmap
                        pix = page.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("png")
                        
                        ocr_result, _ = ocr_engine(img_bytes)
                        if ocr_result:
                            # Combine OCR detected text lines
                            ocr_lines = [line[1] for line in ocr_result if line and len(line) >= 2]
                            ocr_text = "\n".join(ocr_lines).strip()
                            if len(ocr_text) > len(page_text):
                                page_text = ocr_text
                                ocr_used = True
                                ocr_applied_count += 1
                    except Exception as ocr_err:
                        logger.warning(f"OCR fallback failed on page {page_idx + 1}: {ocr_err}")

            pages_data.append({
                "page_num": page_idx + 1,
                "text": page_text,
                "ocr_used": ocr_used,
            })

        doc.close()
        return pages_data, total_pages, ocr_applied_count

    # ---------------------------------------------------------------------------
    # 3. Reference Range Parsing & Range Status Evaluation
    # ---------------------------------------------------------------------------
    @classmethod
    def parse_reference_range(cls, range_str: Optional[str]) -> Tuple[Optional[float], Optional[float], str]:
        """
        Parses common reference range expressions into (low, high, raw_text).
        Handles formats:
        - "12.0 - 16.0", "12.0-16.0", "12.0 to 16.0"
        - "< 200", "<= 200", "Less than 200"
        - "> 60", ">= 60", "Greater than 60"
        - "Up to 40"
        """
        if not range_str or not range_str.strip():
            return None, None, ""

        raw = range_str.strip()
        # Clean enclosing parens or brackets
        cleaned = re.sub(r"^[(\[]|[)\]]$", "", raw).strip()

        # Format 1: Lower - Upper (e.g., "13.0 - 17.0" or "0.6 - 1.2" or "150,000 - 450,000")
        range_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:,\d{3})*(?:\.\d+)?)", cleaned, re.IGNORECASE)
        if range_match:
            try:
                low = float(range_match.group(1).replace(",", ""))
                high = float(range_match.group(2).replace(",", ""))
                return low, high, raw
            except ValueError:
                pass

        # Format 2: Less than / upper bound (e.g., "< 200", "<= 5.7", "Up to 40")
        less_match = re.search(r"(?:<|<=|less than|up to)\s*(\d+(?:,\d{3})*(?:\.\d+)?)", cleaned, re.IGNORECASE)
        if less_match:
            try:
                high = float(less_match.group(1).replace(",", ""))
                return None, high, raw
            except ValueError:
                pass

        # Format 3: Greater than / lower bound (e.g., "> 60", ">= 50")
        greater_match = re.search(r"(?:>|>=|greater than)\s*(\d+(?:,\d{3})*(?:\.\d+)?)", cleaned, re.IGNORECASE)
        if greater_match:
            try:
                low = float(greater_match.group(1).replace(",", ""))
                return low, None, raw
            except ValueError:
                pass

        return None, None, raw

    @classmethod
    def evaluate_range_status(
        cls,
        val: Optional[float],
        low: Optional[float],
        high: Optional[float],
        spec: Optional[MedicalParameterSpec] = None,
    ) -> Tuple[str, bool]:
        """
        Evaluates extracted value against report reference range and critical thresholds.
        Returns (range_status, is_critical).
        """
        if val is None:
            return "EXTRACTION_REQUIRES_VERIFICATION", False

        is_critical = False
        # Check critical thresholds first if specified in registry
        if spec:
            if spec.critical_low is not None and val <= spec.critical_low:
                is_critical = True
            elif spec.critical_high is not None and val >= spec.critical_high:
                is_critical = True

        if is_critical:
            return "CRITICAL_REVIEW_REQUIRED", True

        # Check for inverted or invalid reference range (e.g. low > high)
        if low is not None and high is not None and low > high:
            return "EXTRACTION_REQUIRES_VERIFICATION", False

        # If report provided no valid range bounds
        if low is None and high is None:
            return "REFERENCE_RANGE_NOT_AVAILABLE", False

        # Upper bound only (e.g. < 200, <= 5.7)
        if low is None and high is not None:
            if val > high:
                return "ABOVE_RANGE", False
            return "WITHIN_RANGE", False

        # Lower bound only (e.g. > 60, >= 50)
        if low is not None and high is None:
            if val < low:
                return "BELOW_RANGE", False
            return "WITHIN_RANGE", False

        # Both bounds present
        if low is not None and high is not None:
            if val < low:
                return "BELOW_RANGE", False
            elif val > high:
                return "ABOVE_RANGE", False
            else:
                return "WITHIN_RANGE", False

        return "REFERENCE_RANGE_NOT_AVAILABLE", False

    # ---------------------------------------------------------------------------
    # 4. Structured Parameter Extraction Engine
    # ---------------------------------------------------------------------------
    @classmethod
    def extract_parameters_from_text(
        cls,
        pages_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Extracts structured parameters across all pages using regular expressions and registry matching.
        Supports multi-parameter lines, multi-column layouts, thousands separators, negative numbers,
        and decimal values. Calibrates confidence scores based on text source and unit matches.
        """
        extracted_parameters = []
        seen_canonical = set()

        num_pattern = re.compile(r"([<>]?=?\s*[-+]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+))")

        for page in pages_data:
            page_num = page["page_num"]
            lines = page["text"].split("\n")

            for line in lines:
                clean_line = line.strip()
                if not clean_line or len(clean_line) < 3:
                    continue

                # 1. Discover all matching parameter aliases in this line
                alias_matches = []
                for key, spec in MEDICAL_PARAMETERS_REGISTRY.items():
                    for alias in spec.aliases:
                        for m in re.finditer(rf"\b{re.escape(alias)}\b", clean_line, re.IGNORECASE):
                            alias_matches.append({
                                "start": m.start(),
                                "end": m.end(),
                                "alias": alias,
                                "spec": spec,
                                "key": key,
                            })

                if not alias_matches:
                    continue

                # 2. Deduplicate overlapping matches: prefer longer alias match span
                # e.g., 'rbc count' over 'rbc', 'total wbc' over 'wbc'
                sorted_by_pos = sorted(alias_matches, key=lambda x: (x["start"], -(x["end"] - x["start"])))
                non_overlapping = []
                last_end = -1
                for match in sorted_by_pos:
                    if match["start"] >= last_end:
                        non_overlapping.append(match)
                        last_end = match["end"]

                # 3. Extract parameter values from each non-overlapping segment
                for i, match in enumerate(non_overlapping):
                    spec = match["spec"]
                    canonical_name = spec.canonical_name

                    # Don't duplicate exact canonical parameter from same document
                    if canonical_name in seen_canonical:
                        continue

                    # Segment bounds: from this alias end up to the start of the next alias match on this line
                    seg_start = match["end"]
                    seg_end = non_overlapping[i + 1]["start"] if (i + 1 < len(non_overlapping)) else len(clean_line)
                    search_text = clean_line[seg_start:seg_end].strip()

                    # Find numbers in search_text
                    num_matches = [m for m in num_pattern.finditer(search_text) if m.group(1).strip()]
                    if not num_matches:
                        continue

                    # The first number candidate represents the test result value
                    raw_val_str = num_matches[0].group(1).replace(",", "").strip()
                    clean_num_str = re.sub(r"[<>=]", "", raw_val_str).strip()
                    try:
                        num_val = float(clean_num_str)
                    except ValueError:
                        num_val = None

                    # Check for explicit unit match in segment
                    found_unit = None
                    for u in spec.accepted_units + [spec.canonical_unit]:
                        if re.search(rf"\b{re.escape(u)}\b", search_text, re.IGNORECASE):
                            found_unit = u
                            break

                    # Search for reference range in remainder of segment after the result value
                    range_low = None
                    range_high = None
                    range_text = ""
                    rest_of_text = search_text[num_matches[0].end():]
                    low_cand, high_cand, r_raw = cls.parse_reference_range(rest_of_text)
                    if low_cand is not None or high_cand is not None or r_raw:
                        range_low = low_cand
                        range_high = high_cand
                        range_text = r_raw

                    # Evaluate range status and critical status
                    range_status, is_critical = cls.evaluate_range_status(
                        num_val,
                        range_low,
                        range_high,
                        spec,
                    )

                    # Calibrate confidence score
                    is_ocr = page.get("ocr_used", False)
                    if num_val is None or range_status == "EXTRACTION_REQUIRES_VERIFICATION":
                        confidence = 0.50
                    elif is_ocr:
                        confidence = 0.78 if found_unit else 0.65
                    else:
                        confidence = 0.95 if found_unit else 0.85

                    extracted_parameters.append({
                        "parameter_name": spec.aliases[0].title(),
                        "canonical_name": canonical_name,
                        "category": spec.category,
                        "extracted_value": raw_val_str,
                        "numeric_value": num_val,
                        "original_unit": found_unit or spec.canonical_unit,
                        "canonical_unit": spec.canonical_unit,
                        "reference_range_text": range_text or None,
                        "reference_range_low": range_low,
                        "reference_range_high": range_high,
                        "range_status": range_status,
                        "is_critical": is_critical,
                        "extraction_confidence": confidence,
                        "source_page": page_num,
                        "source_text_snippet": clean_line[:400],
                        "verification_status": "UNVERIFIED",
                    })
                    seen_canonical.add(canonical_name)

        return extracted_parameters

    # ---------------------------------------------------------------------------
    # 5. Report Category Identification & Date Detection
    # ---------------------------------------------------------------------------
    @classmethod
    def detect_category_and_date(
        cls,
        pages_data: List[Dict[str, Any]],
        extracted_parameters: List[Dict[str, Any]],
    ) -> Tuple[str, Optional[date]]:
        """
        Infers likely medical document category from extracted parameters and header text,
        and extracts report date if printed on the document.
        """
        # Count parameter categories
        cat_counts: Dict[str, int] = {}
        for p in extracted_parameters:
            c = p.get("category", "General")
            cat_counts[c] = cat_counts.get(c, 0) + 1

        inferred_category = "Other Medical Reports"
        if cat_counts:
            # Most prevalent category
            inferred_category = max(cat_counts.items(), key=lambda x: x[1])[0]

        # Date extraction: search for patterns like DD/MM/YYYY, YYYY-MM-DD, or DD-Mon-YYYY
        full_text = " ".join(p["text"] for p in pages_data)
        date_patterns = [
            r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b",       # 2026-11-20
            r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b",       # 20/11/2026
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b", # 20 Nov 2026
        ]

        found_date = None
        for dp in date_patterns:
            m = re.search(dp, full_text, re.IGNORECASE)
            if m:
                d_str = m.group(1)
                for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
                    try:
                        found_date = datetime.strptime(d_str, fmt).date()
                        break
                    except ValueError:
                        continue
            if found_date:
                break

        return inferred_category, found_date

    # ---------------------------------------------------------------------------
    # 6. Structured Plain-Language Report Summary (10 Sections)
    # ---------------------------------------------------------------------------
    @classmethod
    def generate_report_summary(
        cls,
        doc: MedicalDocument,
        parameters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Produces a structured, 10-section plain-language summary traceable to actual data.
        Non-diagnostic: never generates unsupported clinical conclusions.
        """
        total = len(parameters)
        within_range = [p for p in parameters if p.get("range_status") == "WITHIN_RANGE"]
        below_range = [p for p in parameters if p.get("range_status") == "BELOW_RANGE"]
        above_range = [p for p in parameters if p.get("range_status") == "ABOVE_RANGE"]
        critical_alerts = [p for p in parameters if p.get("range_status") == "CRITICAL_REVIEW_REQUIRED" or p.get("is_critical")]
        requires_verification = [p for p in parameters if p.get("range_status") == "EXTRACTION_REQUIRES_VERIFICATION"]

        # Formulate non-diagnostic observations
        observations = []
        if critical_alerts:
            names = ", ".join(p["canonical_name"] for p in critical_alerts)
            observations.append(
                f"CRITICAL SAFETY WARNING: High-priority review required for {names}. "
                "These values meet or exceed critical clinical thresholds. Consult attending physician promptly."
            )

        if above_range:
            names = ", ".join(p["canonical_name"] for p in above_range[:4])
            observations.append(
                f"Elevated parameters noted: {names} {'are' if len(above_range) > 1 else 'is'} above the laboratory-printed reference range."
            )

        if below_range:
            names = ", ".join(p["canonical_name"] for p in below_range[:4])
            observations.append(
                f"Low parameters noted: {names} {'are' if len(below_range) > 1 else 'is'} below the laboratory-printed reference range."
            )

        if not above_range and not below_range and not critical_alerts and total > 0:
            observations.append(
                "All successfully extracted parameters are within their laboratory-provided reference ranges."
            )

        if not observations:
            observations.append("Laboratory report parameters extracted. Clinician review recommended.")

        overview_text = (
            f"Your uploaded report ({doc.document_category}) contains {total} extracted parameters. "
            f"{len(within_range)} values are within report reference ranges. "
            f"{len(below_range) + len(above_range) + len(critical_alerts)} values require clinical review by your healthcare professional."
        )

        return {
            "report_overview": overview_text,
            "report_category": doc.document_category,
            "report_date": doc.report_date.isoformat() if doc.report_date else date.today().isoformat(),
            "total_parameters_extracted": total,
            "parameters_within_range_count": len(within_range),
            "parameters_below_range_count": len(below_range),
            "parameters_above_range_count": len(above_range),
            "parameters_requiring_verification_count": len(requires_verification),
            "critical_alerts_count": len(critical_alerts),
            "below_range_parameters": [p["canonical_name"] for p in below_range],
            "above_range_parameters": [p["canonical_name"] for p in above_range],
            "critical_parameters": [p["canonical_name"] for p in critical_alerts],
            "important_observations": observations,
            "doctor_review_status": "PENDING_DOCTOR_REVIEW",
            "disclaimer": (
                "MediSmart AI Report Analysis is assistive and educational. It does NOT diagnose illnesses, "
                "prescribe treatments, or replace professional laboratory consultation."
            ),
        }

    # ---------------------------------------------------------------------------
    # 7. Complete End-to-End Document Analysis Pipeline
    # ---------------------------------------------------------------------------
    @classmethod
    async def process_document(
        cls,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> MedicalReportAnalysis:
        """
        Executes complete extraction and analysis pipeline:
        1. Retrieves MedicalDocument.
        2. Extracts text with PyMuPDF & RapidOCR fallback.
        3. Identifies parameters and evaluates reference ranges.
        4. Synthesizes plain-language summary.
        5. Saves MedicalReportAnalysis and ExtractedMedicalParameter records in PostgreSQL.
        """
        doc_query = select(MedicalDocument).where(MedicalDocument.id == document_id)
        doc_res = await db.execute(doc_query)
        document = doc_res.scalar_one_or_none()
        if not document:
            raise ValueError(f"Document {document_id} not found.")

        document.processing_status = "PROCESSING"
        await db.flush()

        storage_dir = cls.ensure_storage_dir()
        file_path = storage_dir / document.stored_filename
        if not file_path.exists():
            document.processing_status = "FAILED"
            document.error_message = "Stored physical file is missing from private storage."
            await db.commit()
            raise FileNotFoundError("Stored document physical file not found.")

        try:
            # 1. Text & OCR Extraction
            pages_data, total_pages, ocr_applied = cls.extract_text_from_pdf(file_path)

            # 2. Parameter Extraction
            raw_parameters = cls.extract_parameters_from_text(pages_data)

            # 3. Detect Category & Date if not specified
            inferred_cat, detected_date = cls.detect_category_and_date(pages_data, raw_parameters)
            if document.document_category == "Other Medical Reports" and inferred_cat != "Other Medical Reports":
                document.document_category = inferred_cat
            if detected_date and not document.report_date:
                document.report_date = detected_date

            # 4. Generate Summary
            summary_dict = cls.generate_report_summary(document, raw_parameters)

            # 5. Create Analysis Row
            raw_text_combined = "\n--- Page Break ---\n".join(p["text"] for p in pages_data)
            analysis = MedicalReportAnalysis(
                id=uuid.uuid4(),
                document_id=document.id,
                extraction_engine_version="12.0.0-pymupdf-rapidocr",
                analysis_status="SUCCESS" if raw_parameters else "PARTIAL",
                total_pages=total_pages,
                ocr_applied_pages=ocr_applied,
                raw_text_preview=raw_text_combined[:4000],
                summary_json=summary_dict,
                extraction_metadata={
                    "total_parameters": len(raw_parameters),
                    "ocr_used": ocr_applied > 0,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            db.add(analysis)
            await db.flush()

            # 6. Save Extracted Parameters
            for p in raw_parameters:
                param_row = ExtractedMedicalParameter(
                    id=uuid.uuid4(),
                    analysis_id=analysis.id,
                    parameter_name=p["parameter_name"],
                    canonical_name=p["canonical_name"],
                    category=p["category"],
                    extracted_value=p["extracted_value"],
                    numeric_value=p["numeric_value"],
                    original_unit=p["original_unit"],
                    canonical_unit=p["canonical_unit"],
                    reference_range_text=p["reference_range_text"],
                    reference_range_low=p["reference_range_low"],
                    reference_range_high=p["reference_range_high"],
                    range_status=p["range_status"],
                    is_critical=p["is_critical"],
                    extraction_confidence=p["extraction_confidence"],
                    source_page=p["source_page"],
                    source_text_snippet=p["source_text_snippet"],
                    verification_status="UNVERIFIED",
                )
                db.add(param_row)

            document.processing_status = "COMPLETED"
            await db.commit()
            return analysis

        except Exception as e:
            logger.error(f"Error processing medical document {document_id}: {e}", exc_info=True)
            document.processing_status = "FAILED"
            document.error_message = str(e)[:500]
            await db.commit()
            raise

    # ---------------------------------------------------------------------------
    # 8. Historical Medical Report Comparison
    # ---------------------------------------------------------------------------
    @classmethod
    async def compare_reports(
        cls,
        document_ids: List[uuid.UUID],
        patient_id: uuid.UUID,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Compares two or more reports belonging to the same patient.
        Matches equivalent parameters, checks unit compatibility, computes numerical differences,
        and identifies increasing / decreasing trends without assuming clinical significance.
        """
        if len(document_ids) < 2:
            raise ValueError("Comparison requires at least two distinct report documents.")

        # Query documents with eager loading of analyses and parameters
        query = (
            select(MedicalDocument)
            .where(
                and_(
                    MedicalDocument.id.in_(document_ids),
                    MedicalDocument.patient_id == patient_id,
                    MedicalDocument.is_deleted == False,
                )
            )
            .options(
                selectinload(MedicalDocument.analyses).selectinload(MedicalReportAnalysis.parameters)
            )
            .order_by(MedicalDocument.report_date.asc(), MedicalDocument.created_at.asc())
        )
        res = await db.execute(query)
        docs = res.scalars().all()

        if len(docs) < 2:
            raise ValueError("One or more specified reports were not found or do not belong to this patient.")

        # Map parameters across reports
        reports_meta = []
        param_history: Dict[str, List[Dict[str, Any]]] = {}

        for doc in docs:
            reports_meta.append({
                "document_id": str(doc.id),
                "original_filename": doc.original_filename,
                "document_category": doc.document_category,
                "report_date": doc.report_date.isoformat() if doc.report_date else "Unknown",
            })
            latest_analysis = doc.analyses[0] if doc.analyses else None
            if not latest_analysis:
                continue

            for p in latest_analysis.parameters:
                canonical = p.canonical_name
                if canonical not in param_history:
                    param_history[canonical] = []
                param_history[canonical].append({
                    "document_id": str(doc.id),
                    "report_date": doc.report_date.isoformat() if doc.report_date else "Unknown",
                    "value_str": p.extracted_value,
                    "numeric_value": p.numeric_value,
                    "unit": p.original_unit,
                    "range_status": p.range_status,
                })

        # Calculate comparisons
        compared_parameters = []
        for canonical, entries in param_history.items():
            if len(entries) < 2:
                # Parameter only present in one report
                compared_parameters.append({
                    "canonical_name": canonical,
                    "status": "ONLY_IN_ONE_REPORT",
                    "history": entries,
                    "delta": None,
                    "percent_change": None,
                    "trend": "INSUFFICIENT_DATA",
                    "unit_compatible": True,
                })
                continue

            prev = entries[-2]
            curr = entries[-1]

            prev_num = prev["numeric_value"]
            curr_num = curr["numeric_value"]
            prev_u = prev["unit"]
            curr_u = curr["unit"]

            # Check unit compatibility & perform clinical conversion if necessary
            unit_conversion_note = None
            effective_prev_val = prev_num
            unit_compatible = False

            if normalize_unit(prev_u) == normalize_unit(curr_u):
                unit_compatible = True
            elif prev_num is not None:
                # Attempt validated unit conversion
                conv_result = convert_parameter_value(canonical, prev_num, prev_u, curr_u)
                if conv_result is not None:
                    effective_prev_val = conv_result[0]
                    unit_conversion_note = conv_result[2]
                    unit_compatible = True

            if not unit_compatible:
                compared_parameters.append({
                    "canonical_name": canonical,
                    "status": "UNIT_MISMATCH",
                    "history": entries,
                    "delta": None,
                    "percent_change": None,
                    "trend": "UNIT_INCOMPATIBLE",
                    "unit_compatible": False,
                    "note": f"Incompatible units cannot be clinically compared: {prev_u} vs {curr_u}",
                })
                continue

            if effective_prev_val is not None and curr_num is not None:
                delta = round(curr_num - effective_prev_val, 3)
                pct = None
                if abs(effective_prev_val) > 1e-6:
                    pct = round((delta / effective_prev_val) * 100, 1)

                trend = "STABLE"
                if delta > 0.001:
                    trend = "INCREASING"
                elif delta < -0.001:
                    trend = "DECREASING"

                comp_entry = {
                    "canonical_name": canonical,
                    "status": "COMPARABLE",
                    "history": entries,
                    "previous_value": prev_num,
                    "current_value": curr_num,
                    "unit": curr_u,
                    "delta": delta,
                    "percent_change": pct,
                    "trend": trend,
                    "unit_compatible": True,
                }
                if unit_conversion_note:
                    comp_entry["conversion_note"] = unit_conversion_note
                compared_parameters.append(comp_entry)
            else:
                compared_parameters.append({
                    "canonical_name": canonical,
                    "status": "NON_NUMERICAL",
                    "history": entries,
                    "delta": None,
                    "percent_change": None,
                    "trend": "NON_NUMERICAL",
                    "unit_compatible": True,
                })

        return {
            "patient_id": str(patient_id),
            "reports_compared": reports_meta,
            "total_compared_parameters": len(compared_parameters),
            "parameters": compared_parameters,
            "disclaimer": (
                "Numerical differences are factual observations. A higher or lower value must NOT be assumed "
                "to represent clinical improvement without professional physician assessment."
            ),
        }

    # ---------------------------------------------------------------------------
    # 9. Medical Parameter Trend Aggregation (for Recharts)
    # ---------------------------------------------------------------------------
    @classmethod
    async def get_parameter_trends(
        cls,
        patient_id: uuid.UUID,
        canonical_name: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Retrieves chronological time-series points for a specific parameter for Recharts.
        """
        query = (
            select(ExtractedMedicalParameter, MedicalDocument)
            .join(MedicalReportAnalysis, ExtractedMedicalParameter.analysis_id == MedicalReportAnalysis.id)
            .join(MedicalDocument, MedicalReportAnalysis.document_id == MedicalDocument.id)
            .where(
                and_(
                    MedicalDocument.patient_id == patient_id,
                    MedicalDocument.is_deleted == False,
                    ExtractedMedicalParameter.canonical_name == canonical_name,
                )
            )
            .order_by(MedicalDocument.report_date.asc(), MedicalDocument.created_at.asc())
        )
        res = await db.execute(query)
        rows = res.all()

        points = []
        unit = None
        range_low = None
        range_high = None

        for param, doc in rows:
            if unit is None and param.original_unit:
                unit = param.canonical_unit or param.original_unit
            if range_low is None and param.reference_range_low is not None:
                range_low = param.reference_range_low
            if range_high is None and param.reference_range_high is not None:
                range_high = param.reference_range_high

            val = param.numeric_value
            # If param was recorded in a different compatible unit, convert to canonical unit
            if val is not None and param.original_unit and unit and normalize_unit(param.original_unit) != normalize_unit(unit):
                conv = convert_parameter_value(canonical_name, val, param.original_unit, unit)
                if conv:
                    val = conv[0]

            points.append({
                "date": doc.report_date.isoformat() if doc.report_date else "Unknown",
                "value": val,
                "value_str": param.extracted_value,
                "unit": unit or param.original_unit or "",
                "range_status": param.range_status,
                "is_critical": param.is_critical,
                "document_id": str(doc.id),
                "filename": doc.original_filename,
            })

        return {
            "patient_id": str(patient_id),
            "parameter_name": canonical_name,
            "unit": unit or "",
            "reference_range_low": range_low,
            "reference_range_high": range_high,
            "data_points": points,
            "total_records": len(points),
        }

    # ---------------------------------------------------------------------------
    # 10. Doctor Review & Parameter Correction Audit
    # ---------------------------------------------------------------------------
    @classmethod
    async def submit_doctor_review(
        cls,
        document_id: uuid.UUID,
        doctor_user: User,
        review_status: str,
        clinical_notes: Optional[str],
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> MedicalReportReview:
        """
        Records an official physician review for a medical document.
        Audits action to clinical audit log.
        """
        # Resolve doctor profile
        doc_res = await db.execute(select(Doctor).where(Doctor.user_id == doctor_user.id))
        doctor = doc_res.scalar_one_or_none()
        doctor_id = doctor.id if doctor else None

        # Verify document exists
        d_res = await db.execute(select(MedicalDocument).where(MedicalDocument.id == document_id))
        doc = d_res.scalar_one_or_none()
        if not doc:
            raise ValueError("Document not found.")

        review = MedicalReportReview(
            id=uuid.uuid4(),
            document_id=doc.id,
            doctor_id=doctor_id,
            doctor_user_id=doctor_user.id,
            review_status=review_status,
            clinical_notes=clinical_notes,
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(review)

        # Audit log entry
        await clinical_audit_service.log(
            db=db,
            action="MEDICAL_REPORT_REVIEW",
            target_type="medical_document",
            actor=doctor_user,
            target_id=doc.id,
            patient_id=doc.patient_id,
            doctor_id=doctor_id,
            hospital_id=doctor.hospital_id if doctor else None,
            metadata={
                "review_status": review_status,
                "document_category": doc.document_category,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await db.commit()
        return review

    @classmethod
    async def correct_extracted_parameter(
        cls,
        parameter_id: uuid.UUID,
        doctor_user: User,
        corrected_value: str,
        correction_reason: str,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ExtractedMedicalParameter:
        """
        Records a physician correction to an extracted parameter.
        Never overwrites without recording prior value in MedicalParameterCorrection and ClinicalAuditLog.
        """
        # Resolve doctor
        doc_res = await db.execute(select(Doctor).where(Doctor.user_id == doctor_user.id))
        doctor = doc_res.scalar_one_or_none()
        doctor_id = doctor.id if doctor else None

        p_query = (
            select(ExtractedMedicalParameter)
            .where(ExtractedMedicalParameter.id == parameter_id)
            .options(
                selectinload(ExtractedMedicalParameter.analysis).selectinload(MedicalReportAnalysis.document)
            )
        )
        p_res = await db.execute(p_query)
        param = p_res.scalar_one_or_none()
        if not param:
            raise ValueError("Extracted parameter not found.")

        prior_val = param.extracted_value
        prior_status = param.range_status

        # Evaluate corrected value
        try:
            new_num = float(re.sub(r"[<>]", "", corrected_value.strip()))
        except ValueError:
            new_num = None

        new_status, is_crit = cls.evaluate_range_status(
            new_num,
            param.reference_range_low,
            param.reference_range_high,
        )

        # Record immutable correction history
        correction = MedicalParameterCorrection(
            id=uuid.uuid4(),
            parameter_id=param.id,
            doctor_id=doctor_id,
            doctor_user_id=doctor_user.id,
            prior_value=prior_val,
            corrected_value=corrected_value.strip(),
            prior_range_status=prior_status,
            corrected_range_status=new_status,
            correction_reason=correction_reason.strip(),
            created_at=datetime.now(timezone.utc),
        )
        db.add(correction)

        # Update parameter
        param.extracted_value = corrected_value.strip()
        param.numeric_value = new_num
        param.range_status = new_status
        param.is_critical = is_crit
        param.verification_status = "DOCTOR_CORRECTED"

        # Audit log
        doc = param.analysis.document if param.analysis else None
        await clinical_audit_service.log(
            db=db,
            action="PARAMETER_CORRECTION",
            target_type="extracted_medical_parameter",
            actor=doctor_user,
            target_id=param.id,
            patient_id=doc.patient_id if doc else None,
            doctor_id=doctor_id,
            hospital_id=doctor.hospital_id if doctor else None,
            metadata={
                "canonical_name": param.canonical_name,
                "prior_value": prior_val,
                "corrected_value": corrected_value.strip(),
                "reason": correction_reason,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await db.commit()
        return param


medical_report_service = MedicalReportService()

"""
Configurable Registry of Supported Medical Parameters, Aliases, Units, and Critical Thresholds.
Part of MediSmart AI Phase 12.0.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class MedicalParameterSpec:
    canonical_name: str
    category: str
    aliases: List[str]
    canonical_unit: str
    accepted_units: List[str] = field(default_factory=list)
    critical_low: Optional[float] = None
    critical_high: Optional[float] = None
    typical_range_low: Optional[float] = None
    typical_range_high: Optional[float] = None
    description: str = ""


# Comprehensive registry covering CBC, Glucose, Lipids, KFT, LFT, TFT, and Urine
MEDICAL_PARAMETERS_REGISTRY: Dict[str, MedicalParameterSpec] = {
    # ---------------------------------------------------------------------------
    # A. Complete Blood Count (CBC)
    # ---------------------------------------------------------------------------
    "hemoglobin": MedicalParameterSpec(
        canonical_name="Hemoglobin",
        category="Complete Blood Count (CBC)",
        aliases=["hemoglobin", "haemoglobin", "hgb", "hb"],
        canonical_unit="g/dL",
        accepted_units=["g/dl", "gm/dl", "g/l", "g%", "gm%"],
        critical_low=7.0,
        critical_high=20.0,
        typical_range_low=12.0,
        typical_range_high=17.5,
        description="Oxygen-carrying protein in red blood cells.",
    ),
    "rbc_count": MedicalParameterSpec(
        canonical_name="RBC Count",
        category="Complete Blood Count (CBC)",
        aliases=["rbc count", "rbc", "red blood cell count", "total rbc", "erythrocyte count"],
        canonical_unit="million/uL",
        accepted_units=["million/ul", "mil/ul", "10^6/ul", "10^12/l", "mill/cumm", "x10^6/ul"],
        critical_low=2.0,
        critical_high=7.5,
        typical_range_low=3.8,
        typical_range_high=5.9,
        description="Total red blood cell concentration.",
    ),
    "wbc_count": MedicalParameterSpec(
        canonical_name="WBC Count",
        category="Complete Blood Count (CBC)",
        aliases=["wbc count", "wbc", "white blood cell count", "total wbc", "leukocyte count", "tlc"],
        canonical_unit="/uL",
        accepted_units=["/ul", "/cumm", "cells/cumm", "cells/ul", "10^3/ul", "10^9/l", "thou/ul"],
        critical_low=2000.0,
        critical_high=30000.0,
        typical_range_low=4000.0,
        typical_range_high=11000.0,
        description="Total white blood cell count.",
    ),
    "platelet_count": MedicalParameterSpec(
        canonical_name="Platelet Count",
        category="Complete Blood Count (CBC)",
        aliases=["platelet count", "platelets", "total platelets", "plt", "thrombocyte count"],
        canonical_unit="/uL",
        accepted_units=["/ul", "/cumm", "cells/cumm", "cells/ul", "10^3/ul", "lakh/cumm", "10^5/cumm", "thou/ul"],
        critical_low=50000.0,
        critical_high=1000000.0,
        typical_range_low=150000.0,
        typical_range_high=450000.0,
        description="Platelets responsible for blood clotting.",
    ),
    "hematocrit": MedicalParameterSpec(
        canonical_name="Hematocrit",
        category="Complete Blood Count (CBC)",
        aliases=["hematocrit", "haematocrit", "hct", "packed cell volume", "pcv"],
        canonical_unit="%",
        accepted_units=["%", "percent", "vol%"],
        critical_low=20.0,
        critical_high=60.0,
        typical_range_low=36.0,
        typical_range_high=52.0,
        description="Proportion of blood made up of red blood cells.",
    ),
    "mcv": MedicalParameterSpec(
        canonical_name="MCV",
        category="Complete Blood Count (CBC)",
        aliases=["mcv", "mean corpuscular volume", "mean cell volume"],
        canonical_unit="fL",
        accepted_units=["fl", "femtoliter", "um^3"],
        critical_low=60.0,
        critical_high=120.0,
        typical_range_low=80.0,
        typical_range_high=100.0,
        description="Average volume of a single red blood cell.",
    ),
    "mch": MedicalParameterSpec(
        canonical_name="MCH",
        category="Complete Blood Count (CBC)",
        aliases=["mch", "mean corpuscular hemoglobin", "mean cell hemoglobin"],
        canonical_unit="pg",
        accepted_units=["pg", "picogram"],
        critical_low=15.0,
        critical_high=45.0,
        typical_range_low=27.0,
        typical_range_high=33.0,
        description="Average mass of hemoglobin per red blood cell.",
    ),
    "mchc": MedicalParameterSpec(
        canonical_name="MCHC",
        category="Complete Blood Count (CBC)",
        aliases=["mchc", "mean corpuscular hemoglobin concentration", "mean cell hb conc"],
        canonical_unit="g/dL",
        accepted_units=["g/dl", "gm/dl", "%"],
        critical_low=25.0,
        critical_high=40.0,
        typical_range_low=32.0,
        typical_range_high=36.0,
        description="Average concentration of hemoglobin in packed red cells.",
    ),
    "neutrophils": MedicalParameterSpec(
        canonical_name="Neutrophils",
        category="Complete Blood Count (CBC)",
        aliases=["neutrophils", "neutrophil", "segs", "polymorphs", "neutrophils %", "absolute neutrophil count"],
        canonical_unit="%",
        accepted_units=["%", "/ul", "cells/ul"],
        critical_low=10.0,
        critical_high=90.0,
        typical_range_low=40.0,
        typical_range_high=75.0,
        description="Most abundant type of granulocyte white blood cell.",
    ),
    "lymphocytes": MedicalParameterSpec(
        canonical_name="Lymphocytes",
        category="Complete Blood Count (CBC)",
        aliases=["lymphocytes", "lymphocyte", "lymphs", "lymphocytes %", "absolute lymphocyte count"],
        canonical_unit="%",
        accepted_units=["%", "/ul", "cells/ul"],
        critical_low=5.0,
        critical_high=80.0,
        typical_range_low=20.0,
        typical_range_high=45.0,
        description="Key immune white blood cells (T cells, B cells, NK cells).",
    ),
    "eosinophils": MedicalParameterSpec(
        canonical_name="Eosinophils",
        category="Complete Blood Count (CBC)",
        aliases=["eosinophils", "eosinophil", "eos", "eosinophils %"],
        canonical_unit="%",
        accepted_units=["%", "/ul"],
        critical_low=0.0,
        critical_high=30.0,
        typical_range_low=1.0,
        typical_range_high=6.0,
        description="White blood cells involved in allergic responses and combating parasites.",
    ),

    # ---------------------------------------------------------------------------
    # B. Blood Glucose & Diabetic Panel
    # ---------------------------------------------------------------------------
    "fasting_blood_glucose": MedicalParameterSpec(
        canonical_name="Fasting Blood Glucose",
        category="Blood Glucose",
        aliases=["fasting blood glucose", "fasting blood sugar", "fbs", "fasting glucose", "glucose fasting", "plasma glucose fasting"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mg%", "mmol/l"],
        critical_low=50.0,
        critical_high=400.0,
        typical_range_low=70.0,
        typical_range_high=99.0,
        description="Blood glucose measured after an overnight fast.",
    ),
    "postprandial_blood_glucose": MedicalParameterSpec(
        canonical_name="Postprandial Blood Glucose",
        category="Blood Glucose",
        aliases=["postprandial blood glucose", "postprandial blood sugar", "ppbs", "pp glucose", "glucose pp", "post prandial glucose", "2 hr postprandial glucose"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mg%", "mmol/l"],
        critical_low=50.0,
        critical_high=450.0,
        typical_range_low=70.0,
        typical_range_high=140.0,
        description="Blood glucose measured 2 hours after a meal.",
    ),
    "random_blood_glucose": MedicalParameterSpec(
        canonical_name="Random Blood Glucose",
        category="Blood Glucose",
        aliases=["random blood glucose", "random blood sugar", "rbs", "glucose random", "random plasma glucose"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mg%", "mmol/l"],
        critical_low=50.0,
        critical_high=400.0,
        typical_range_low=70.0,
        typical_range_high=140.0,
        description="Blood glucose measured at any random time.",
    ),
    "hba1c": MedicalParameterSpec(
        canonical_name="HbA1c",
        category="Blood Glucose",
        aliases=["hba1c", "glycated hemoglobin", "glycohemoglobin", "hemoglobin a1c", "a1c"],
        canonical_unit="%",
        accepted_units=["%", "mmol/mol"],
        critical_low=3.5,
        critical_high=14.0,
        typical_range_low=4.0,
        typical_range_high=5.6,
        description="Average blood glucose level over the preceding 2 to 3 months.",
    ),

    # ---------------------------------------------------------------------------
    # C. Lipid Profile
    # ---------------------------------------------------------------------------
    "total_cholesterol": MedicalParameterSpec(
        canonical_name="Total Cholesterol",
        category="Lipid Profile",
        aliases=["total cholesterol", "cholesterol total", "serum cholesterol", "cholesterol"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mmol/l"],
        critical_low=80.0,
        critical_high=400.0,
        typical_range_low=125.0,
        typical_range_high=200.0,
        description="Total circulating blood cholesterol.",
    ),
    "hdl_cholesterol": MedicalParameterSpec(
        canonical_name="HDL Cholesterol",
        category="Lipid Profile",
        aliases=["hdl cholesterol", "hdl", "hdl-c", "high density lipoprotein"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mmol/l"],
        critical_low=15.0,
        critical_high=150.0,
        typical_range_low=40.0,
        typical_range_high=60.0,
        description="High-density lipoprotein ('good' cholesterol).",
    ),
    "ldl_cholesterol": MedicalParameterSpec(
        canonical_name="LDL Cholesterol",
        category="Lipid Profile",
        aliases=["ldl cholesterol", "ldl", "ldl-c", "low density lipoprotein", "calculated ldl"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mmol/l"],
        critical_low=20.0,
        critical_high=300.0,
        typical_range_low=50.0,
        typical_range_high=100.0,
        description="Low-density lipoprotein ('bad' cholesterol).",
    ),
    "triglycerides": MedicalParameterSpec(
        canonical_name="Triglycerides",
        category="Lipid Profile",
        aliases=["triglycerides", "serum triglycerides", "tg", "trigs"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mmol/l"],
        critical_low=20.0,
        critical_high=800.0,
        typical_range_low=50.0,
        typical_range_high=150.0,
        description="Circulating fats synthesized in the liver from unused calories.",
    ),
    "vldl_cholesterol": MedicalParameterSpec(
        canonical_name="VLDL Cholesterol",
        category="Lipid Profile",
        aliases=["vldl cholesterol", "vldl", "vldl-c", "very low density lipoprotein"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mmol/l"],
        critical_low=5.0,
        critical_high=120.0,
        typical_range_low=5.0,
        typical_range_high=30.0,
        description="Very low-density lipoprotein cholesterol fraction.",
    ),

    # ---------------------------------------------------------------------------
    # D. Kidney Function Test (KFT)
    # ---------------------------------------------------------------------------
    "serum_creatinine": MedicalParameterSpec(
        canonical_name="Serum Creatinine",
        category="Kidney Function Test (KFT)",
        aliases=["creatinine", "serum creatinine", "s. creatinine", "cr"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "umol/l", "micromol/l"],
        critical_low=0.2,
        critical_high=8.0,
        typical_range_low=0.6,
        typical_range_high=1.3,
        description="Primary biomarker of renal glomerular filtration function.",
    ),
    "blood_urea": MedicalParameterSpec(
        canonical_name="Blood Urea",
        category="Kidney Function Test (KFT)",
        aliases=["blood urea", "serum urea", "urea"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mmol/l"],
        critical_low=5.0,
        critical_high=180.0,
        typical_range_low=15.0,
        typical_range_high=45.0,
        description="Waste product of protein digestion filtered by kidneys.",
    ),
    "bun": MedicalParameterSpec(
        canonical_name="BUN",
        category="Kidney Function Test (KFT)",
        aliases=["bun", "blood urea nitrogen"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "mmol/l"],
        critical_low=3.0,
        critical_high=100.0,
        typical_range_low=7.0,
        typical_range_high=20.0,
        description="Nitrogen content of urea in the blood.",
    ),
    "uric_acid": MedicalParameterSpec(
        canonical_name="Uric Acid",
        category="Kidney Function Test (KFT)",
        aliases=["uric acid", "serum uric acid", "s. uric acid"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "umol/l"],
        critical_low=1.5,
        critical_high=14.0,
        typical_range_low=3.5,
        typical_range_high=7.2,
        description="Byproduct of purine metabolism; elevated in gout and renal insufficiency.",
    ),
    "egfr": MedicalParameterSpec(
        canonical_name="eGFR",
        category="Kidney Function Test (KFT)",
        aliases=["egfr", "estimated gfr", "glomerular filtration rate", "gfr"],
        canonical_unit="mL/min/1.73m2",
        accepted_units=["ml/min/1.73m2", "ml/min", "ml/min/1.73 m^2"],
        critical_low=15.0,
        critical_high=160.0,
        typical_range_low=60.0,
        typical_range_high=120.0,
        description="Estimated rate of blood filtration through renal glomeruli.",
    ),

    # ---------------------------------------------------------------------------
    # E. Liver Function Test (LFT)
    # ---------------------------------------------------------------------------
    "alt_sgpt": MedicalParameterSpec(
        canonical_name="ALT (SGPT)",
        category="Liver Function Test (LFT)",
        aliases=["alt", "sgpt", "alanine aminotransferase", "alanine transaminase", "s.g.p.t."],
        canonical_unit="U/L",
        accepted_units=["u/l", "iu/l", "units/l"],
        critical_low=2.0,
        critical_high=1000.0,
        typical_range_low=7.0,
        typical_range_high=56.0,
        description="Enzyme concentrated in liver tissue; primary marker of acute hepatocellular injury.",
    ),
    "ast_sgot": MedicalParameterSpec(
        canonical_name="AST (SGOT)",
        category="Liver Function Test (LFT)",
        aliases=["ast", "sgot", "aspartate aminotransferase", "aspartate transaminase", "s.g.o.t."],
        canonical_unit="U/L",
        accepted_units=["u/l", "iu/l", "units/l"],
        critical_low=2.0,
        critical_high=1000.0,
        typical_range_low=10.0,
        typical_range_high=40.0,
        description="Enzyme found in liver and cardiac muscle.",
    ),
    "alp": MedicalParameterSpec(
        canonical_name="ALP",
        category="Liver Function Test (LFT)",
        aliases=["alp", "alkaline phosphatase", "alk phos"],
        canonical_unit="U/L",
        accepted_units=["u/l", "iu/l", "units/l"],
        critical_low=15.0,
        critical_high=800.0,
        typical_range_low=44.0,
        typical_range_high=147.0,
        description="Enzyme related to bile ducts and bone turnover.",
    ),
    "bilirubin_total": MedicalParameterSpec(
        canonical_name="Total Bilirubin",
        category="Liver Function Test (LFT)",
        aliases=["total bilirubin", "bilirubin total", "t. bilirubin", "s. bilirubin total", "bilirubin (total)"],
        canonical_unit="mg/dL",
        accepted_units=["mg/dl", "umol/l"],
        critical_low=0.1,
        critical_high=20.0,
        typical_range_low=0.2,
        typical_range_high=1.2,
        description="Total breakdown product of red blood cell hemoglobin.",
    ),
    "serum_albumin": MedicalParameterSpec(
        canonical_name="Serum Albumin",
        category="Liver Function Test (LFT)",
        aliases=["albumin", "serum albumin", "s. albumin"],
        canonical_unit="g/dL",
        accepted_units=["g/dl", "gm/dl", "g/l"],
        critical_low=1.8,
        critical_high=6.5,
        typical_range_low=3.4,
        typical_range_high=5.4,
        description="Major plasma protein synthesized by the liver.",
    ),
    "total_protein": MedicalParameterSpec(
        canonical_name="Total Protein",
        category="Liver Function Test (LFT)",
        aliases=["total protein", "serum total protein", "protein total"],
        canonical_unit="g/dL",
        accepted_units=["g/dl", "gm/dl", "g/l"],
        critical_low=3.5,
        critical_high=12.0,
        typical_range_low=6.0,
        typical_range_high=8.3,
        description="Sum of all proteins (albumin and globulin) in serum.",
    ),

    # ---------------------------------------------------------------------------
    # F. Thyroid Function Test (TFT)
    # ---------------------------------------------------------------------------
    "tsh": MedicalParameterSpec(
        canonical_name="TSH",
        category="Thyroid Function Test",
        aliases=["tsh", "thyroid stimulating hormone", "thyrotropin", "serum tsh", "s. tsh"],
        canonical_unit="uIU/mL",
        accepted_units=["uiu/ml", "miu/l", "microu/ml", "u/l"],
        critical_low=0.01,
        critical_high=50.0,
        typical_range_low=0.4,
        typical_range_high=4.5,
        description="Pituitary hormone regulating thyroid hormone secretion.",
    ),
    "total_t3": MedicalParameterSpec(
        canonical_name="Total T3",
        category="Thyroid Function Test",
        aliases=["total t3", "triiodothyronine", "t3 total", "t3"],
        canonical_unit="ng/dL",
        accepted_units=["ng/dl", "nmol/l"],
        critical_low=20.0,
        critical_high=500.0,
        typical_range_low=80.0,
        typical_range_high=200.0,
        description="Active thyroid hormone circulating in bound and free forms.",
    ),
    "total_t4": MedicalParameterSpec(
        canonical_name="Total T4",
        category="Thyroid Function Test",
        aliases=["total t4", "thyroxine", "t4 total", "t4"],
        canonical_unit="ug/dL",
        accepted_units=["ug/dl", "mcg/dl", "nmol/l"],
        critical_low=1.0,
        critical_high=25.0,
        typical_range_low=4.5,
        typical_range_high=12.0,
        description="Primary prohormone produced by the thyroid gland.",
    ),
    "free_t3": MedicalParameterSpec(
        canonical_name="Free T3",
        category="Thyroid Function Test",
        aliases=["free t3", "ft3", "free triiodothyronine"],
        canonical_unit="pg/mL",
        accepted_units=["pg/ml", "pmol/l"],
        critical_low=0.8,
        critical_high=15.0,
        typical_range_low=2.0,
        typical_range_high=4.4,
        description="Unbound, biologically active fraction of T3.",
    ),
    "free_t4": MedicalParameterSpec(
        canonical_name="Free T4",
        category="Thyroid Function Test",
        aliases=["free t4", "ft4", "free thyroxine"],
        canonical_unit="ng/dL",
        accepted_units=["ng/dl", "pmol/l"],
        critical_low=0.2,
        critical_high=6.0,
        typical_range_low=0.8,
        typical_range_high=1.8,
        description="Unbound, biologically active fraction of T4.",
    ),
}


def lookup_parameter_spec(candidate_name: str) -> Optional[Tuple[str, MedicalParameterSpec]]:
    """
    Matches an extracted parameter string against the medical parameter registry.
    Returns (key, MedicalParameterSpec) or None if unmapped.
    """
    clean_candidate = candidate_name.strip().lower()
    # 1. Exact match against aliases
    for key, spec in MEDICAL_PARAMETERS_REGISTRY.items():
        for alias in spec.aliases:
            if clean_candidate == alias:
                return key, spec

    # 2. Substring match with word boundary
    for key, spec in MEDICAL_PARAMETERS_REGISTRY.items():
        for alias in spec.aliases:
            # If alias is at least 3 chars and is an exact token
            if len(alias) >= 3 and (alias == clean_candidate or f" {alias} " in f" {clean_candidate} "):
                return key, spec

    return None


def normalize_unit(unit_str: Optional[str]) -> Optional[str]:
    """
    Normalizes common variations of measurement units.
    Preserves standard clinical casing and conventions.
    """
    if not unit_str:
        return None
    cleaned = unit_str.strip().lower()
    
    mapping = {
        "gm/dl": "g/dL",
        "g/dl": "g/dL",
        "g%": "g/dL",
        "gm%": "g/dL",
        "g/l": "g/L",
        "mg/dl": "mg/dL",
        "mg%": "mg/dL",
        "mg/100ml": "mg/dL",
        "mmol/l": "mmol/L",
        "umol/l": "umol/L",
        "µmol/l": "umol/L",
        "micromol/l": "umol/L",
        "mmol/mol": "mmol/mol",
        "/ul": "/uL",
        "/cumm": "/uL",
        "cells/cumm": "/uL",
        "cells/ul": "/uL",
        "10^3/ul": "10^3/uL",
        "thou/ul": "10^3/uL",
        "10^9/l": "10^3/uL",
        "million/ul": "million/uL",
        "mil/ul": "million/uL",
        "10^6/ul": "million/uL",
        "10^12/l": "million/uL",
        "lakh/cumm": "lakh/cumm",
        "10^5/cumm": "lakh/cumm",
        "fl": "fL",
        "pg": "pg",
        "%": "%",
        "percent": "%",
        "u/l": "U/L",
        "iu/l": "U/L",
        "units/l": "U/L",
        "uiu/ml": "uIU/mL",
        "miu/l": "uIU/mL",
        "ng/dl": "ng/dL",
        "ug/dl": "ug/dL",
        "mcg/dl": "ug/dL",
        "pg/ml": "pg/mL",
        "ml/min/1.73m2": "mL/min/1.73m2",
        "ml/min": "mL/min",
    }
    return mapping.get(cleaned, unit_str.strip())


def convert_parameter_value(
    canonical_name: str,
    value: float,
    from_unit: Optional[str],
    to_unit: Optional[str],
) -> Optional[Tuple[float, str, str]]:
    """
    Converts a laboratory parameter value between compatible units based on validated clinical conversion factors.
    Returns (converted_value, target_unit, conversion_audit_note) or None if incompatible or unsupported.
    """
    if from_unit is None or to_unit is None or value is None:
        return None

    u_from = normalize_unit(from_unit)
    u_to = normalize_unit(to_unit)

    if not u_from or not u_to:
        return None

    if u_from.lower() == u_to.lower():
        return value, u_to, "Identical units (no conversion required)"

    c_name = canonical_name.strip().title()

    # 1. Glucose: mg/dL <-> mmol/L (Factor: 18.0182)
    if any(k in c_name.lower() for k in ["glucose"]):
        if u_from == "mmol/L" and u_to == "mg/dL":
            converted = round(value * 18.0182, 2)
            return converted, "mg/dL", f"Converted {value} mmol/L to {converted} mg/dL (factor 18.0182)"
        elif u_from == "mg/dL" and u_to == "mmol/L":
            converted = round(value / 18.0182, 2)
            return converted, "mmol/L", f"Converted {value} mg/dL to {converted} mmol/L (factor 18.0182)"

    # 2. Total Cholesterol / HDL / LDL / VLDL: mg/dL <-> mmol/L (Factor: 38.67)
    if "cholesterol" in c_name.lower() or c_name in ["HDL Cholesterol", "LDL Cholesterol", "VLDL Cholesterol", "Total Cholesterol"]:
        if u_from == "mmol/L" and u_to == "mg/dL":
            converted = round(value * 38.67, 2)
            return converted, "mg/dL", f"Converted {value} mmol/L to {converted} mg/dL (factor 38.67)"
        elif u_from == "mg/dL" and u_to == "mmol/L":
            converted = round(value / 38.67, 2)
            return converted, "mmol/L", f"Converted {value} mg/dL to {converted} mmol/L (factor 38.67)"

    # 3. Triglycerides: mg/dL <-> mmol/L (Factor: 88.57)
    if "triglycerides" in c_name.lower():
        if u_from == "mmol/L" and u_to == "mg/dL":
            converted = round(value * 88.57, 2)
            return converted, "mg/dL", f"Converted {value} mmol/L to {converted} mg/dL (factor 88.57)"
        elif u_from == "mg/dL" and u_to == "mmol/L":
            converted = round(value / 88.57, 2)
            return converted, "mmol/L", f"Converted {value} mg/dL to {converted} mmol/L (factor 88.57)"

    # 4. Serum Creatinine: mg/dL <-> umol/L (Factor: 88.4)
    if "creatinine" in c_name.lower():
        if u_from in ["umol/L", "micromol/L"] and u_to == "mg/dL":
            converted = round(value / 88.4, 2)
            return converted, "mg/dL", f"Converted {value} umol/L to {converted} mg/dL (factor 88.4)"
        elif u_from == "mg/dL" and u_to in ["umol/L", "micromol/L"]:
            converted = round(value * 88.4, 1)
            return converted, "umol/L", f"Converted {value} mg/dL to {converted} umol/L (factor 88.4)"

    # 5. Hemoglobin / Total Protein / Serum Albumin: g/dL <-> g/L (Factor: 10.0)
    if any(k in c_name.lower() for k in ["hemoglobin", "protein", "albumin"]):
        if u_from == "g/L" and u_to == "g/dL":
            converted = round(value / 10.0, 2)
            return converted, "g/dL", f"Converted {value} g/L to {converted} g/dL (factor 10.0)"
        elif u_from == "g/dL" and u_to == "g/L":
            converted = round(value * 10.0, 2)
            return converted, "g/L", f"Converted {value} g/dL to {converted} g/L (factor 10.0)"

    # 6. Blood Urea: mg/dL <-> mmol/L (Factor: 6.006)
    if "blood urea" in c_name.lower() or c_name == "Blood Urea":
        if u_from == "mmol/L" and u_to == "mg/dL":
            converted = round(value * 6.006, 2)
            return converted, "mg/dL", f"Converted {value} mmol/L to {converted} mg/dL (factor 6.006)"
        elif u_from == "mg/dL" and u_to == "mmol/L":
            converted = round(value / 6.006, 2)
            return converted, "mmol/L", f"Converted {value} mg/dL to {converted} mmol/L (factor 6.006)"

    # 7. BUN: mg/dL <-> mmol/L (Factor: 2.801)
    if "bun" in c_name.lower():
        if u_from == "mmol/L" and u_to == "mg/dL":
            converted = round(value * 2.801, 2)
            return converted, "mg/dL", f"Converted {value} mmol/L to {converted} mg/dL (factor 2.801)"
        elif u_from == "mg/dL" and u_to == "mmol/L":
            converted = round(value / 2.801, 2)
            return converted, "mmol/L", f"Converted {value} mg/dL to {converted} mmol/L (factor 2.801)"

    # 8. Platelet Count scaling: /uL <-> 10^3/uL <-> lakh/cumm
    if "platelet" in c_name.lower():
        in_cumm = None
        if u_from == "/uL":
            in_cumm = value
        elif u_from in ["10^3/uL", "10^9/L"]:
            in_cumm = value * 1000.0
        elif u_from == "lakh/cumm":
            in_cumm = value * 100000.0

        if in_cumm is not None:
            if u_to == "/uL":
                return round(in_cumm, 1), "/uL", f"Converted {value} {u_from} to {round(in_cumm, 1)} /uL"
            elif u_to in ["10^3/uL", "10^9/L"]:
                conv = round(in_cumm / 1000.0, 1)
                return conv, "10^3/uL", f"Converted {value} {u_from} to {conv} 10^3/uL"
            elif u_to == "lakh/cumm":
                conv = round(in_cumm / 100000.0, 2)
                return conv, "lakh/cumm", f"Converted {value} {u_from} to {conv} lakh/cumm"

    # 9. WBC Count scaling: /uL <-> 10^3/uL
    if "wbc" in c_name.lower():
        if u_from in ["10^3/uL", "10^9/L"] and u_to == "/uL":
            converted = round(value * 1000.0, 1)
            return converted, "/uL", f"Converted {value} {u_from} to {converted} /uL"
        elif u_from == "/uL" and u_to in ["10^3/uL", "10^9/L"]:
            converted = round(value / 1000.0, 2)
            return converted, "10^3/uL", f"Converted {value} /uL to {converted} 10^3/uL"

    # 10. RBC Count scaling: million/uL <-> /uL
    if "rbc" in c_name.lower():
        if u_from == "million/uL" and u_to == "/uL":
            converted = round(value * 1_000_000.0, 1)
            return converted, "/uL", f"Converted {value} million/uL to {converted} /uL"
        elif u_from == "/uL" and u_to == "million/uL":
            converted = round(value / 1_000_000.0, 3)
            return converted, "million/uL", f"Converted {value} /uL to {converted} million/uL"

    # 11. HbA1c: % <-> mmol/mol (IFCC equation: mmol/mol = ( % - 2.15 ) * 10.929)
    if "hba1c" in c_name.lower():
        if u_from == "%" and u_to == "mmol/mol":
            converted = round((value - 2.15) * 10.929, 1)
            return converted, "mmol/mol", f"Converted {value}% to {converted} mmol/mol (IFCC formula)"
        elif u_from == "mmol/mol" and u_to == "%":
            converted = round((value / 10.929) + 2.15, 2)
            return converted, "%", f"Converted {value} mmol/mol to {converted}% (NGSP formula)"

    return None


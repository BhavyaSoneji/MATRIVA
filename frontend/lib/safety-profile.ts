/** Options for the safety profile. Codes match backend/app/data/guardrails/conditions.yaml. */

export const CONDITION_OPTIONS: { value: string; label: string }[] = [
  { value: "high blood pressure", label: "High blood pressure" },
  { value: "pre-eclampsia", label: "Pre-eclampsia (earlier or now)" },
  { value: "gestational diabetes", label: "Gestational diabetes" },
  { value: "diabetes", label: "Diabetes" },
  { value: "thyroid", label: "Thyroid condition" },
  { value: "epilepsy", label: "Epilepsy" },
  { value: "asthma", label: "Asthma" },
  { value: "anaemia", label: "Anaemia" },
  { value: "heart disease", label: "Heart disease" },
  { value: "kidney disease", label: "Kidney disease" },
  { value: "liver disease", label: "Liver disease" },
  { value: "placenta previa", label: "Low-lying placenta (praevia)" },
  { value: "cervical insufficiency", label: "Weak cervix or cerclage" },
  { value: "hiv", label: "HIV" },
  { value: "hepatitis b", label: "Hepatitis B" },
  { value: "hepatitis c", label: "Hepatitis C" },
  { value: "tuberculosis", label: "Tuberculosis" },
  { value: "pcos", label: "PCOS" },
  { value: "depression", label: "Depression or anxiety" },
  { value: "sickle cell", label: "Sickle cell disease or trait" },
  { value: "thalassemia", label: "Thalassaemia" },
  { value: "obesity", label: "Obesity" },
  { value: "clotting disorder", label: "Blood clot or clotting disorder" },
  { value: "lupus", label: "Lupus or autoimmune disease" },
  { value: "migraine", label: "Migraine" },
  { value: "urinary infection", label: "Repeated urine infections" },
];

export const RISK_FACTOR_OPTIONS: { value: string; label: string }[] = [
  { value: "twins", label: "Expecting twins or more" },
  { value: "previous_cesarean", label: "Previous caesarean section" },
  { value: "previous_preterm_birth", label: "Previous preterm birth" },
  { value: "previous_miscarriage", label: "Previous miscarriage" },
  { value: "previous_stillbirth", label: "Previous stillbirth" },
  { value: "rh_negative", label: "Rh-negative blood group" },
  { value: "ivf", label: "Pregnancy through IVF or fertility treatment" },
  { value: "smoker", label: "I smoke or chew tobacco" },
  { value: "drinks_alcohol", label: "I drink alcohol" },
];

export const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

export interface SafetyProfileState {
  conditions: string[];
  otherConditions: string;
  allergies: string;
  medications: string;
  riskFactors: string[];
  age: string;
  bloodGroup: string;
}

export const EMPTY_SAFETY_PROFILE: SafetyProfileState = {
  conditions: [],
  otherConditions: "",
  allergies: "",
  medications: "",
  riskFactors: [],
  age: "",
  bloodGroup: "",
};

const known = new Set(CONDITION_OPTIONS.map((c) => c.value));
const splitList = (text: string, pattern: RegExp) =>
  text.split(pattern).map((s) => s.trim()).filter(Boolean);

/** Read the stored health profile back into form state. */
export function fromHealth(health: Record<string, unknown> | null | undefined): SafetyProfileState {
  if (!health) return EMPTY_SAFETY_PROFILE;
  const stored = ((health.known_conditions as string[]) || []).map((s) => s.trim()).filter(Boolean);
  return {
    conditions: stored.filter((c) => known.has(c.toLowerCase())).map((c) => c.toLowerCase()),
    otherConditions: stored.filter((c) => !known.has(c.toLowerCase())).join(", "),
    allergies: ((health.allergies as string[]) || []).join(", "),
    medications: ((health.current_medications as string[]) || []).join("\n"),
    riskFactors: ((health.risk_factors as string[]) || []).filter((r) => RISK_FACTOR_OPTIONS.some((o) => o.value === r)),
    age: health.age_years ? String(health.age_years) : "",
    bloodGroup: (health.blood_group as string) || "",
  };
}

/** Fields for PUT /profile. */
export function toPayload(state: SafetyProfileState) {
  const age = Number(state.age);
  return {
    known_conditions: [...state.conditions, ...splitList(state.otherConditions, /[,\n]/)],
    allergies: splitList(state.allergies, /[,\n]/),
    current_medications: splitList(state.medications, /\n|,(?!\d)/),
    risk_factors: state.riskFactors,
    age_years: Number.isFinite(age) && age >= 10 && age <= 60 ? age : null,
    blood_group: state.bloodGroup || null,
  };
}

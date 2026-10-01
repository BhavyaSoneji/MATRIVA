export interface PlanVisit {
  week: number;
  date: string;
  days_away: number;
  status: "past" | "due_now" | "upcoming";
}

export interface PlanTask {
  id: string;
  title: string;
  detail: string;
  source: string;
  kind: "supplement" | "visit" | "learn";
  ask?: string;
}

export interface Supplement {
  id: string;
  label: string;
  active: boolean;
  instruction: string;
  source: string;
  url: string;
}

export interface CarePlan {
  week: number;
  day: number;
  trimester: number;
  stage: string;
  lmp: string;
  edd: string;
  days_to_edd: number;
  progress: number;
  source_of_dates: "lmp" | "edd" | "week";
  headline: string;
  next_visit: PlanVisit | null;
  visits: PlanVisit[];
  pmsma: { date: string; days_away: number; note: string; url: string } | null;
  supplements: Supplement[];
  this_week: PlanTask[];
  milestones: { title: string; detail: string }[];
  review: string;
}

export interface Reminder {
  id: string;
  priority: number;
  title: string;
  detail: string;
  action: "checkin" | "summary" | "readings" | null;
  kind: string;
}

export interface Checkin {
  date: string;
  mood: number | null;
  symptoms: string[];
  baby_movement: "normal" | "reduced" | "not_yet" | null;
  ifa_taken: boolean | null;
  note: string | null;
  red_flags: string[];
  triage_level: "none" | "soon" | "urgent" | "emergency";
}

export interface TriageFlag {
  id: string;
  text: string;
  level: string;
  source: string;
  url: string;
}

export interface Triage {
  level: "none" | "soon" | "urgent" | "emergency";
  title: string;
  action: string;
  flagged: TriageFlag[];
  emergency_numbers: { general: string; ambulance: string[] };
  maps_url: string;
  contact: { name: string; phone: string; relation: string } | null;
  disclaimer: string;
}

export interface ScreeningQuestion {
  id: string;
  level: "emergency" | "urgent" | "soon";
  text: string;
  source: string;
  url: string;
}

export interface ReadingFlag {
  level: "urgent" | "discuss" | "info";
  message: string;
  source: string;
  url: string;
}

export interface Reading {
  id: string;
  kind: "hb" | "bp" | "weight" | "glucose";
  date: string;
  value: number | null;
  systolic: number | null;
  diastolic: number | null;
  context: string | null;
  unit: string;
  source: string;
  flags: ReadingFlag[];
}

export interface ReadingCandidate {
  kind: Reading["kind"];
  value?: number;
  systolic?: number;
  diastolic?: number;
  date: string;
  context?: string | null;
  matched: string;
}

export interface WeightGain {
  baseline_kg: number;
  baseline: string;
  latest_kg: number;
  gain_kg: number;
  healthy_total_gain_kg: [number, number];
  note: string;
}

export interface MealItem {
  food_id: string;
  name: string;
  grams: number;
  portion: string;
  approximate: boolean;
}

export interface NutrientRow {
  nutrient: string;
  intake: number;
  target: number;
  percent: number;
}

export interface MealsDay {
  date: string;
  meals: { id: string; meal_type: string | null; text: string; items: MealItem[]; totals: Record<string, number> }[];
  totals: Record<string, number>;
  rows: NutrientRow[];
  suggestions: { nutrient: string; foods: { name: string; serving_g: number; amount: number }[] }[];
  note: string;
}

export interface DoctorSummary {
  generated_on: string;
  name: string | null;
  pregnancy: { week: number; day: number; trimester: number; edd: string; lmp: string; dates_from: string; next_visit: PlanVisit | null } | null;
  health: {
    known_conditions: string[];
    allergies: string[];
    doctor_restrictions: string[];
    diet: string | null;
    current_medications?: string[];
    risk_factors?: string[];
    blood_group?: string | null;
    age_years?: number | null;
  };
  readings: { latest: Record<string, Reading>; trend: Record<string, Reading[]>; weight_gain: WeightGain | null };
  iron_tablets: { days: number; checked_in: number; ifa_answered: number; ifa_taken: number; ifa_rate: number | null; ifa_streak: number };
  symptoms_last_14_days: Record<string, number>;
  red_flags: { date: string; flags: string[] }[];
  last_screening: { date: string; level: string; flagged: string[] } | null;
  nutrition: { days_logged: number; average_per_day: Record<string, number>; rows: NutrientRow[] } | null;
  questions_for_doctor: string[];
  disclaimer: string;
}

export interface FoodGuideBookItem {
  authority: string;
  text: string;
  page: number;
  paraphrased?: boolean;
}

export interface FoodGuideNeed {
  id: string;
  label: string;
  reason: string;
}

export interface FoodGuideFood {
  name: string;
  category: string;
  serving_g: number;
  amount: number;
  percent: number | null;
}

export interface FoodGuide {
  week: number | null;
  month: number | null;
  diet: string | null;
  traditional: {
    book: { title: string; author: string; chapter: string; section: string; scan_pages: string; note: string };
    evidence_level: string;
    month: number | null;
    months_available: number[];
    foods: FoodGuideBookItem[];
    medicated: FoodGuideBookItem[];
    procedures: FoodGuideBookItem[];
    skipped_for_diet?: number;
    skipped_for_allergy?: number;
    medicated_note?: string;
    rationale?: { page: string; points: string[] };
    avoid?: { page: string; items: { authority: string; text: string; page: number; modern?: string }[] };
  };
  modern: {
    needs: FoodGuideNeed[];
    need: { id: string; label: string; reason: string; unit: string; daily_allowance: number | null; tip?: string | null } | null;
    foods: FoodGuideFood[];
    empty_note?: string;
    allergy_notes?: string[];
    sources?: { name: string; url: string }[];
  };
  avoid_modern: { name: string; why: string; sources: { name: string; url: string }[] }[];
  notes: string[];
}

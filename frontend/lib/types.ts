export interface UserResponse {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserResponse;
}

export interface ProfileResponse {
  user_id: string;
  consent: boolean;
  consent_version: string | null;
  full_name: string | null;
  health: Record<string, unknown> | null;
  lifestyle: Record<string, unknown> | null;
  dietary: Record<string, unknown> | null;
  cultural: Record<string, unknown> | null;
}

export interface ProfileUpdateRequest {
  consent: boolean;
  consent_version?: string;
  full_name?: string | null;
  known_conditions?: string[];
  doctor_restrictions?: string[];
  dietary_restrictions?: string[];
  activity_restrictions?: string[];
  allergies?: string[];
  health_notes?: string | null;
  activity_level?: string | null;
  occupation?: string | null;
  sleep_hours?: number | null;
  stress_level?: string | null;
  lifestyle_preferences?: string[];
  diet_type?: string | null;
  region?: string | null;
  cuisine?: string | null;
  food_preferences?: string[];
  language?: string | null;
  traditional_practice_preference?: string | null;
  cultural_notes?: string | null;
}

export interface PregnancyResponse {
  current_week: number;
  due_date: string | null;
  first_pregnancy: boolean;
  stage: string;
  trimester: number;
}

export interface PregnancyUpdateRequest {
  current_week: number;
  due_date?: string | null;
  first_pregnancy: boolean;
}

export interface SourceResponse {
  id: string;
  name: string;
  title: string;
  source_type: string;
  authority: string | null;
  jurisdiction: string | null;
  topic: string | null;
  url: string | null;
  version: string | null;
  publication_date: string | null;
  review_status: string;
  evidence_level: string;
  evidence_label: string | null;
  page_or_section: string | null;
  extra_metadata: Record<string, unknown>;
}

export interface KnowledgeResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  domain: string;
  subdomain: string | null;
  region: string | null;
  pregnancy_stage: string | null;
  content: string;
  score: number;
  source: SourceResponse;
}

export interface KnowledgeSearchResponse {
  query: string;
  results: KnowledgeResult[];
  count: number;
}

export interface Citation {
  source_id: string;
  source_name: string;
  locator: string | null;
  evidence_level: string;
  source_type?: string | null;
  url?: string | null;
  domain?: string | null;
}

export interface RecommendationResponse {
  id: string;
  domain: string;
  title: string;
  description: string;
  reason: string;
  source_documents: string[];
  evidence_level: string;
  safety_status: string;
  score: number;
  is_saved: boolean;
  created_at: string;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  intent: string;
  safety_status: string;
  sources: SourceResponse[];
  citations: Citation[];
  evidence: Record<string, unknown>;
  recommendations: RecommendationResponse[];
}

export interface ChatHistoryResponse {
  conversation_id: string;
  messages: Record<string, unknown>[];
}

export interface FeedbackRequest {
  message_id?: string | null;
  recommendation_id?: string | null;
  rating: number;
  comment?: string | null;
}

export interface GuidelineResponse {
  id: string;
  authority: string;
  jurisdiction: string;
  version: string | null;
  effective_date: string | null;
  review_due_date: string | null;
  status: string;
  source: SourceResponse;
}

export interface DocumentResponse {
  id: string;
  source_id: string;
  title: string;
  domain: string;
  subdomain: string | null;
  language: string;
  region: string | null;
  pregnancy_stage: string | null;
  review_status: string;
  index_status: string;
  content_hash: string;
  file_name: string | null;
  mime_type: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  source: SourceResponse;
}

export interface EvaluationResponse {
  id: string;
  suite: string;
  status: string;
  metrics: Record<string, unknown>;
  report_path: string | null;
  error: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface NextVisitResponse {
  next_visit_week: number;
  current_week: number;
  message: string;
  source_id: string;
  evidence_level: string;
}

export interface DeleteResponse {
  message: string;
}

export interface FoodItem {
  id: string;
  name: string;
  local_names: string[];
  region: string | null;
  cuisine: string | null;
  ingredients: string[];
  dietary_types: string[];
  nutrition_metadata: Record<string, unknown>;
  cultural_relevance: string | null;
  pregnancy_context: string | null;
  evidence_status: string;
  safety_status: string;
  source_ids: string[];
}

export interface LifestyleItem {
  id: string;
  category: string;
  title: string;
  description: string;
  suitable_stages: string[];
  restrictions: string[];
  evidence_status: string;
  safety_status: string;
  source_ids: string[];
}

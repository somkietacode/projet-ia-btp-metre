// ─── Auth ────────────────────────────────────────────────────────────────────

export interface LoginPayload {
  email: string;
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface MeResponse {
  username: string;
  email: string;
  plan_id: number;
  quota_used: number;
  plan_quota: number;
}

// ─── Plans ───────────────────────────────────────────────────────────────────

export interface PlanResponse {
  id: number;
  name: string;
  description: string;
  quota: number;
  price: number;
}

// ─── Knowledge Base ──────────────────────────────────────────────────────────

export interface PublicDocumentResponse {
  id: number;
  filename: string;
  extension: string;
  upload_date: string;
  indexation_status: 'pending' | 'indexing' | 'indexed' | 'failed';
}

export interface PublicDocumentDetailResponse extends PublicDocumentResponse {
  text_content: string | null;
}

export interface VectorSearchChunkResult {
  score: number;
  chunk: string;
  description: string;
  keywords: string[];
  chunk_index: number;
  total_chunks: number;
  document: PublicDocumentDetailResponse;
}

export interface VectorSearchResponse {
  query: string;
  total_results: number;
  results: VectorSearchChunkResult[];
}

// ─── Errors ──────────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
}

// ─── Base de connaissance privée (utilisateur) ───────────────────────────────

export interface UserDocumentResponse {
  id: number;
  filename: string;
  extension: string;
  upload_date: string;
  indexation_status: 'pending' | 'indexing' | 'indexed' | 'failed';
}

export interface UserDocumentDetailResponse extends UserDocumentResponse {
  text_content: string | null;
}

export interface UserVectorSearchChunkResult {
  score: number;
  chunk: string;
  description: string;
  keywords: string[];
  chunk_index: number;
  total_chunks: number;
  document: UserDocumentDetailResponse;
}

export interface UserVectorSearchResponse {
  query: string;
  total_results: number;
  results: UserVectorSearchChunkResult[];
}

// ─── Questions système → utilisateur ──────────────────────────────────────────────────────

export interface QuestionResponse {
  id: number;
  project_id: number;
  project_name: string;
  ouvrage_id: number | null;
  ouvrage_name: string | null;
  question_text: string;
  answer_text: string | null;
  status: 'pending' | 'answered';
  asked_date: string;
  answered_date: string | null;
}

// ─── Projets ──────────────────────────────────────────────────────────────────

export interface MaterialCreateRequest {
  name: string;
  description?: string | null;
  unite_defaut: string;
  unite_commerciale?: string | null;
  conditionnement?: string | null;
  facteur_conversion?: number | null;
}

export interface MaterialImportResult {
  created: number;
  updated: number;
  errors: string[];
}

export interface MaterialResponse {
  id: number;
  name: string;
  description: string | null;
  unite_defaut: string;
  unite_commerciale: string | null;
  conditionnement: string | null;
  facteur_conversion: number | null;
}

export interface PlanBatimentResponse {
  id: number;
  name: string;
  description: string | null;
  upload_date: string;
  extension: string;
  project_id: number;
}

export interface LigneDeCalculResponse {
  id: number;
  description: string;
  quantity: number;
  unit: string;
  position: number;
  commercial_quantity: number | null;
  commercial_unit: string | null;
  material: MaterialResponse;
}

export interface OuvrageResponse {
  id: number;
  name: string;
  categorie: string;
  description: string | null;
  position: number;
  lignes_de_calcul: LigneDeCalculResponse[];
}

export interface ProjectSummaryResponse {
  id: number;
  name: string;
  description: string | null;
  creation_date: string;
  status: string;
  current_step: string | null;
  error_message: string | null;
  last_updated: string;
  ouvrages_count: number;
  questions_pending_count: number;
  plans_count: number;
  materials_count: number;
}

export interface ProjectDetailResponse extends ProjectSummaryResponse {
  materials: MaterialResponse[];
  ouvrages: OuvrageResponse[];
  questions: QuestionResponse[];
  plans_batiment: PlanBatimentResponse[];
}

export interface ProjectCreateRequest {
  name: string;
  description?: string | null;
}

export interface ProjectUpdateRequest {
  name?: string | null;
  description?: string | null;
}

// ─── Workflow agentique / SSE ─────────────────────────────────────────────────

export interface WorkflowQuestionResponse {
  id: number | null;
  text: string;
  ouvrage_id: number | null;
}

export interface WorkflowStatusResponse {
  status: 'calcul_running' | 'waiting_user' | 'done' | 'error';
  question: WorkflowQuestionResponse | null;
  message: string;
}

/**
 * Représente un événement reçu depuis le flux SSE ``GET /projects/{id}/stream``.
 *
 * Types possibles :
 * - ``step``       — étape en cours (message + ouvrage_id?)
 * - ``ouvrage``    — nouvel ouvrage créé (id, name, categorie, description)
 * - ``calcul``     — ligne de calcul ajoutée (id, description, quantity, unit, ouvrage_id)
 * - ``question``   — question posée (id, text, ouvrage_id)
 * - ``answer_received`` — réponse utilisateur prise en compte
 * - ``quota``      — quota mis à jour (quota_used, plan_quota)
 * - ``done``       — workflow terminé (message)
 * - ``error``      — erreur (message)
 */
export interface AgentStreamEvent {
  type: 'step' | 'ouvrage' | 'calcul' | 'question' | 'answer_received' | 'quota' | 'done' | 'error';
  message?: string;
  ouvrage_id?: number;
  // ouvrage
  id?: number;
  name?: string;
  categorie?: string;
  description?: string | null;
  // calcul
  quantity?: number;
  unit?: string;
  // question
  text?: string;
  // quota
  quota_used?: number;
  plan_quota?: number;
}


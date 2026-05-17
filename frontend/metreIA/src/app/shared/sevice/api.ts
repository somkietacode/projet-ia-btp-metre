import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  LoginPayload, MeResponse, PlanResponse,
  PublicDocumentDetailResponse, PublicDocumentResponse, Token,
  UserDocumentDetailResponse, UserDocumentResponse, UserVectorSearchResponse,
  VectorSearchResponse, QuestionResponse,
  MaterialCreateRequest, MaterialImportResult, MaterialResponse,
  ProjectSummaryResponse, ProjectDetailResponse,
  ProjectCreateRequest, ProjectUpdateRequest, PlanBatimentResponse,
  WorkflowStatusResponse, AgentStreamEvent,
} from '../model/interfaces';

@Injectable({
  providedIn: 'root',
})
export class Api {
  private readonly baseUrl = 'http://localhost:8742';

  constructor(private http: HttpClient) {}

  // ─── Auth ─────────────────────────────────────────────────────────────────

  /**
   * POST /auth/login
   * Authentifie un utilisateur et retourne un JWT.
   * Le backend attend un formulaire OAuth2 (username = email).
   */
  login(email: string, password: string): Observable<Token> {
    const body = new URLSearchParams();
    body.set('email', email);
    body.set('password', password);
    const headers = new HttpHeaders({ 'Content-Type': 'application/x-www-form-urlencoded' });
    return this.http.post<Token>(`${this.baseUrl}/auth/login`, body.toString(), { headers });
  }

  /**
   * POST /auth/register
   * Crée un compte utilisateur et retourne un JWT.
   */
  register(payload: LoginPayload): Observable<Token> {
    return this.http.post<Token>(`${this.baseUrl}/auth/register`, payload);
  }

  /**
   * GET /auth/me
   * Retourne les informations de l'utilisateur connecté.
   */
  me(token: string): Observable<MeResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<MeResponse>(`${this.baseUrl}/auth/me`, { headers });
  }

  // ─── Plans ────────────────────────────────────────────────────────────────

  /**
   * GET /plans
   * Retourne la liste des plans d'abonnement disponibles.
   */
  getPlans(): Observable<PlanResponse[]> {
    return this.http.get<PlanResponse[]>(`${this.baseUrl}/plans`);
  }

  // ─── Admin ───────────────────────────────────────────────────────────────────

  /**
   * GET /auth/admin
   * Authentifie un administrateur et retourne un JWT avec le rôle admin.
   * Le backend attend un formulaire OAuth2 (email + password).
   */
  loginAdmin(email: string, password: string): Observable<Token> {
    const body = new URLSearchParams();
    body.set('email', email);
    body.set('password', password);
    const headers = new HttpHeaders({ 'Content-Type': 'application/x-www-form-urlencoded' });
    return this.http.post<Token>(`${this.baseUrl}/auth/admin`, body.toString(), { headers });
  }

  /**
   * GET /admin/me
   * Retourne les informations de l'administrateur connecté.
   * Ce endpoint est utilisé pour vérifier que l'utilisateur a bien le rôle admin.
   */
  meAdmin(token: string): Observable<MeResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<MeResponse>(`${this.baseUrl}/admin/me`, { headers });
  }

  getAdminUsers(token: string): Observable<any[]> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<any[]>(`${this.baseUrl}/admin/users`, { headers });
  }

  updateUserPlan(token: string, userId: number, planId: number): Observable<any> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.patch<any>(`${this.baseUrl}/admin/users/${userId}/plan?plan_id=${planId}`, {}, { headers });
  }

  // ─── Knowledge Base (admin) ───────────────────────────────────────────────

  /**
   * GET /admin/knowledge-base
   * Liste les métadonnées de tous les documents publics.
   */
  getKnowledgeBaseDocs(token: string): Observable<PublicDocumentResponse[]> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<PublicDocumentResponse[]>(`${this.baseUrl}/admin/knowledge-base`, { headers });
  }

  /**
   * GET /admin/knowledge-base/{id}
   * Retourne les métadonnées + texte extrait d'un document.
   */
  getKnowledgeBaseDoc(token: string, id: number): Observable<PublicDocumentDetailResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<PublicDocumentDetailResponse>(`${this.baseUrl}/admin/knowledge-base/${id}`, { headers });
  }

  /**
   * POST /admin/knowledge-base
   * Upload un fichier dans la base documentaire publique.
   */
  uploadKnowledgeBaseDoc(token: string, file: File): Observable<PublicDocumentResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<PublicDocumentResponse>(`${this.baseUrl}/admin/knowledge-base`, formData, { headers });
  }

  /**
   * DELETE /admin/knowledge-base/{id}
   * Supprime un document de la base documentaire publique.
   */
  deleteKnowledgeBaseDoc(token: string, id: number): Observable<void> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.delete<void>(`${this.baseUrl}/admin/knowledge-base/${id}`, { headers });
  }

  /**
   * GET /admin/knowledge-base/{id}/download
   * Retourne le fichier binaire original pour téléchargement.
   */
  downloadKnowledgeBaseDoc(token: string, id: number): Observable<Blob> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get(`${this.baseUrl}/admin/knowledge-base/${id}/download`, {
      headers,
      responseType: 'blob',
    });
  }

  /**
   * POST /admin/knowledge-base/search
   * Recherche sémantique vectorielle dans la base documentaire publique.
   */
  searchKnowledgeBase(token: string, query: string, topK = 5): Observable<VectorSearchResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.post<VectorSearchResponse>(`${this.baseUrl}/admin/knowledge-base/search`, { query, top_k: topK }, {
      headers,
    });
  }

  // ─── Knowledge Base (utilisateur) ────────────────────────────────────────────

  /**
   * GET /knowledge-base
   * Liste les métadonnées des documents privés de l'utilisateur connecté.
   */
  getUserDocs(token: string): Observable<UserDocumentResponse[]> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<UserDocumentResponse[]>(`${this.baseUrl}/knowledge-base`, { headers });
  }

  /**
   * GET /knowledge-base/{id}
   * Retourne les métadonnées + texte extrait d'un document privé.
   */
  getUserDoc(token: string, id: number): Observable<UserDocumentDetailResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<UserDocumentDetailResponse>(`${this.baseUrl}/knowledge-base/${id}`, { headers });
  }

  /**
   * POST /knowledge-base
   * Upload un fichier dans la base documentaire privée de l'utilisateur.
   */
  uploadUserDoc(token: string, file: File): Observable<UserDocumentResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<UserDocumentResponse>(`${this.baseUrl}/knowledge-base`, formData, { headers });
  }

  /**
   * DELETE /knowledge-base/{id}
   * Supprime un document de la base documentaire privée.
   */
  deleteUserDoc(token: string, id: number): Observable<void> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.delete<void>(`${this.baseUrl}/knowledge-base/${id}`, { headers });
  }

  /**
   * GET /knowledge-base/{id}/download
   * Retourne le fichier binaire original pour téléchargement.
   */
  downloadUserDoc(token: string, id: number): Observable<Blob> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get(`${this.baseUrl}/knowledge-base/${id}/download`, {
      headers,
      responseType: 'blob',
    });
  }

  /**
   * POST /knowledge-base/search
   * Recherche sémantique vectorielle dans la base documentaire privée.
   */
  searchUserDocs(token: string, query: string, topK = 5): Observable<UserVectorSearchResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.post<UserVectorSearchResponse>(
      `${this.baseUrl}/knowledge-base/search`,
      { query, top_k: topK },
      { headers },
    );
  }

  // ─── Questions ────────────────────────────────────────────────────────

  /** GET /questions — liste les questions de l'utilisateur connecté */
  getQuestions(token: string, status?: string): Observable<QuestionResponse[]> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    const params: Record<string, string> = {};
    if (status) params['status'] = status;
    return this.http.get<QuestionResponse[]>(`${this.baseUrl}/questions`, { headers, params });
  }

  /** PATCH /questions/{id}/answer — soumet une réponse */
  answerQuestion(token: string, id: number, answerText: string): Observable<QuestionResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.patch<QuestionResponse>(
      `${this.baseUrl}/questions/${id}/answer`,
      { answer_text: answerText },
      { headers },
    );
  }

  /** POST /questions — crée une question (système / agent) */
  createQuestion(
    token: string,
    projectId: number,
    questionText: string,
    ouvrageId?: number,
  ): Observable<QuestionResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.post<QuestionResponse>(
      `${this.baseUrl}/questions`,
      { project_id: projectId, ouvrage_id: ouvrageId ?? null, question_text: questionText },
      { headers },
    );
  }

  // ─── Projets ──────────────────────────────────────────────────────────────

  /** GET /projects — liste les projets de l'utilisateur connecté */
  getProjects(token: string): Observable<ProjectSummaryResponse[]> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<ProjectSummaryResponse[]>(`${this.baseUrl}/projects`, { headers });
  }

  /** POST /projects — crée un nouveau projet */
  createProject(token: string, payload: ProjectCreateRequest): Observable<ProjectDetailResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.post<ProjectDetailResponse>(`${this.baseUrl}/projects`, payload, { headers });
  }

  /** GET /projects/materials — liste le catalogue global des matériaux */
  getAllUserMaterials(token: string): Observable<MaterialResponse[]> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<MaterialResponse[]>(`${this.baseUrl}/projects/materials`, { headers });
  }

  /** GET /projects/{id} — détail d'un projet */
  getProject(token: string, id: number): Observable<ProjectDetailResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<ProjectDetailResponse>(`${this.baseUrl}/projects/${id}`, { headers });
  }

  /** PATCH /projects/{id} — met à jour un projet */
  updateProject(token: string, id: number, payload: ProjectUpdateRequest): Observable<ProjectDetailResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.patch<ProjectDetailResponse>(`${this.baseUrl}/projects/${id}`, payload, { headers });
  }

  /** DELETE /projects/{id} — supprime un projet */
  deleteProject(token: string, id: number): Observable<void> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.delete<void>(`${this.baseUrl}/projects/${id}`, { headers });
  }

  /** POST /projects/{id}/plans — upload un plan de bâtiment */
  uploadPlanBatiment(
    token: string,
    projectId: number,
    file: File,
    name?: string,
    description?: string,
  ): Observable<PlanBatimentResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    const formData = new FormData();
    formData.append('file', file, file.name);
    if (name) formData.append('name', name);
    if (description) formData.append('description', description);
    return this.http.post<PlanBatimentResponse>(
      `${this.baseUrl}/projects/${projectId}/plans`,
      formData,
      { headers },
    );
  }

  /** DELETE /projects/{projectId}/plans/{planId} — supprime un plan de bâtiment */
  deletePlanBatiment(token: string, projectId: number, planId: number): Observable<void> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.delete<void>(`${this.baseUrl}/projects/${projectId}/plans/${planId}`, { headers });
  }

  // ─── Workflow agentique ───────────────────────────────────────────────────

  /** POST /projects/{id}/run — lance le workflow en arrière-plan */
  runProjectWorkflow(token: string, projectId: number): Observable<WorkflowStatusResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.post<WorkflowStatusResponse>(
      `${this.baseUrl}/projects/${projectId}/run`,
      {},
      { headers },
    );
  }

  /** POST /projects/{id}/resume — soumet la réponse utilisateur et reprend le workflow */
  resumeWorkflow(token: string, projectId: number, answer: string): Observable<WorkflowStatusResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.post<WorkflowStatusResponse>(
      `${this.baseUrl}/projects/${projectId}/resume`,
      { answer },
      { headers },
    );
  }

  /**
   * GET /projects/{id}/stream?token=… — flux SSE temps réel du workflow.
   *
   * Retourne un ``EventSource`` natif (pas un Observable) car l'API
   * ``EventSource`` du navigateur ne supporte pas les headers custom ;
   * le JWT est passé en query param.
   *
   * Usage :
   * ```ts
   * const es = this.api.streamProjectEvents(token, projectId);
   * es.onmessage = (e) => { const event: AgentStreamEvent = JSON.parse(e.data); ... };
   * es.onerror   = () => es.close();
   * ```
   */
  streamProjectEvents(token: string, projectId: number): EventSource {
    const url = `${this.baseUrl}/projects/${projectId}/stream?token=${encodeURIComponent(token)}`;
    return new EventSource(url);
  }

  // ─── Catalogue matériaux (admin) ──────────────────────────────────────────

  /** GET /admin/materials — liste le catalogue global */
  getAdminMaterials(token: string): Observable<MaterialResponse[]> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.get<MaterialResponse[]>(`${this.baseUrl}/admin/materials`, { headers });
  }

  /** POST /admin/materials — crée un matériau dans le catalogue global */
  createAdminMaterial(token: string, payload: MaterialCreateRequest): Observable<MaterialResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.post<MaterialResponse>(`${this.baseUrl}/admin/materials`, payload, { headers });
  }

  /** PATCH /admin/materials/{id} — met à jour un matériau */
  updateAdminMaterial(token: string, id: number, payload: Partial<MaterialCreateRequest>): Observable<MaterialResponse> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.patch<MaterialResponse>(`${this.baseUrl}/admin/materials/${id}`, payload, { headers });
  }

  /** DELETE /admin/materials/{id} — supprime un matériau du catalogue */
  deleteAdminMaterial(token: string, id: number): Observable<void> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    return this.http.delete<void>(`${this.baseUrl}/admin/materials/${id}`, { headers });
  }

  /** POST /admin/materials/import — importe un fichier Excel dans le catalogue */
  importAdminMaterials(token: string, file: File): Observable<MaterialImportResult> {
    const headers = new HttpHeaders({ Authorization: `Bearer ${token}` });
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<MaterialImportResult>(`${this.baseUrl}/admin/materials/import`, formData, { headers });
  }
}


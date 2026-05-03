import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { lastValueFrom } from 'rxjs';
import { Api } from '../../../../shared/sevice/api';
import { MaterialCreateRequest, MaterialResponse } from '../../../../shared/model/interfaces';

// ─── Matériaux suggérés par type d'ouvrage (issu de ouvrage.py) ──────────────
const OUVRAGES_MATERIAUX: Record<string, { name: string; unite_defaut: string; description?: string }[]> = {
  'Terrassement': [
    { name: 'Géotextile', unite_defaut: 'm²', description: 'Non-tissé 150 g/m² — séparation et filtration du sol' },
    { name: 'Grillage avertisseur', unite_defaut: 'ml', description: 'Grillage plastique rouge Ø 30 cm — signalisation des réseaux enterrés' },
    { name: 'Remblai', unite_defaut: 'm³', description: 'Tout-venant 0/80 — compacté en couches de 30 cm max' },
    { name: 'Sable de remblai', unite_defaut: 'm³', description: 'Sable 0/4 — remblayage et nivellement autour des ouvrages' },
  ],
  'Fondations': [
    { name: 'Béton de fondation', unite_defaut: 'm³', description: 'Béton C25/30 — semelles filantes ou isolées' },
    { name: 'Acier HA', unite_defaut: 'kg', description: 'Armature HA Fe500 — barres Ø 8 à 20 mm selon calcul béton armé' },
    { name: 'Treillis soudé', unite_defaut: 'm²', description: 'Treillis ST25 — maille 150×150 mm, fil Ø 5 mm' },
    { name: 'Coffrage fond de fouille', unite_defaut: 'm²', description: 'Coffrage bois ou métallique — parements de semelles de fondation' },
    { name: 'Parpaing plein', unite_defaut: 'U', description: 'Parpaing plein 20×20×50 cm — soubassement et murs enterrés' },
  ],
  'Maçonnerie': [
    { name: 'Parpaing creux 20×20×50', unite_defaut: 'U', description: 'Parpaing creux 20×20×50 cm — murs porteurs et doubles cloisons' },
    { name: 'Brique creuse', unite_defaut: 'U', description: 'Brique creuse 20×10×25 cm — cloisons intérieures légères' },
    { name: 'Mortier de montage', unite_defaut: 'sac', description: 'Mortier bâtard pré-dosé — sac 35 kg (~0,015 m³), joint 1 cm' },
    { name: 'Ciment CEM II', unite_defaut: 'sac', description: 'Ciment CEM II/B-LL 32.5R — sac 50 kg, enduits et bétons courants' },
    { name: 'Sable', unite_defaut: 'm³', description: 'Sable de rivière 0/4 — préparation des mortiers et bétons' },
    { name: 'Linteau préfabriqué', unite_defaut: 'U', description: 'Linteau béton 15×15 cm — longueur = largeur de baie + 2×20 cm appui' },
  ],
  'Plâtrerie / Placo': [
    { name: 'Plaque BA13', unite_defaut: 'm²', description: 'Plaque plâtre standard 13 mm — 2,50×1,20 m par plaque (3 m²)' },
    { name: 'Rail R48', unite_defaut: 'ml', description: 'Rail acier galvanisé R48 — fixation sol/plafond, entraxe 120 cm max' },
    { name: 'Montant M48', unite_defaut: 'ml', description: 'Montant acier galvanisé M48 — entraxe 60 cm entre montants' },
    { name: 'Enduit de finition', unite_defaut: 'sac', description: 'Enduit lissage en poudre — sac 20 kg, couvrance ≈ 10 m²/sac' },
    { name: 'Bande à joint', unite_defaut: 'ml', description: 'Bande armée papier 52 mm — traitement des joints entre plaques' },
    { name: 'Vis TF 25', unite_defaut: 'boîte', description: 'Vis autoforante TF 25 mm — boîte 500 pièces, fixation plaque/montant' },
  ],
  'Carrelage': [
    { name: 'Carrelage sol', unite_defaut: 'm²', description: 'Grès cérame 30×30 cm, ép. 8 mm — sol intérieur/extérieur (adapter selon modèle choisi)' },
    { name: 'Carrelage mur faïence', unite_defaut: 'm²', description: 'Faïence murale 20×25 cm, ép. 6 mm — salle de bain et cuisine (adapter selon modèle)' },
    { name: 'Colle à carrelage', unite_defaut: 'sac', description: 'Colle ciment C1 — sac 25 kg, couvrance ≈ 4–5 m²/sac (joint 6 mm)' },
    { name: 'Joint de carrelage', unite_defaut: 'sac', description: 'Mortier joint ciment — sac 5 kg, pour joint 2 à 4 mm' },
    { name: 'Plinthes', unite_defaut: 'ml', description: 'Plinthe carrelage assortie H 7 cm — longueur 1 ml, même pose que sol' },
  ],
  'Toiture': [
    { name: 'Tuile terre cuite', unite_defaut: 'U', description: 'Tuile canal/romane — ≈ 15 tuiles/m², poids unitaire ≈ 3,5 kg' },
    { name: 'Ardoise', unite_defaut: 'U', description: 'Ardoise naturelle 40×25 cm — ≈ 22 ardoises/m², ép. 4–6 mm' },
    { name: 'Chevron 60×80', unite_defaut: 'ml', description: 'Chevron sapin 60×80 mm raboté — entraxe 50 à 60 cm selon portée' },
    { name: 'Latte 40×25', unite_defaut: 'ml', description: 'Latte sapin 40×25 mm — entraxe selon pureau de la tuile' },
    { name: 'Sous-toiture HPV', unite_defaut: 'm²', description: 'Film HPV 150 g/m² — pare-pluie respirant posé sous lattage' },
    { name: 'Faitage', unite_defaut: 'ml', description: 'Faîtière ventilée PVC ou terre cuite — longueur totale du faîtage' },
    { name: 'Gouttière PVC', unite_defaut: 'ml', description: 'Gouttière demi-ronde PVC Ø 100 mm — longueur de rive de toit' },
  ],
  'Enduit / Crépi': [
    { name: 'Enduit de façade', unite_defaut: 'sac', description: 'Enduit monocouche hydraulique — sac 25 kg, consommation ≈ 15 kg/m² à 15 mm' },
    { name: 'Crépi minéral', unite_defaut: 'sac', description: 'Crépi grain 1,5 mm — sac 25 kg, couvrance ≈ 6–8 m²/sac' },
    { name: 'Sous-enduit', unite_defaut: 'sac', description: 'Gobetis d\'accrochage — sac 25 kg, couche d\'adhérence 3–5 mm' },
    { name: 'Grillage de façade', unite_defaut: 'm²', description: 'Treillis anti-fissure 160 g/m² — entoilage dans le corps d\'enduit' },
  ],
  'Chape / Dalle': [
    { name: 'Ciment de chape', unite_defaut: 'sac', description: 'Mortier de chape hydraulique — sac 35 kg, chape 5 cm ≈ 85 kg/m²' },
    { name: 'Sable de chape', unite_defaut: 'm³', description: 'Sable 0/4 lavé — chape traditionnelle dosée à 350 kg ciment/m³' },
    { name: 'Béton prêt à l\'emploi', unite_defaut: 'm³', description: 'Béton C20/25 — dalle sur terre-plein ou plancher (ép. min. 10 cm)' },
    { name: 'Treillis soudé ST25', unite_defaut: 'm²', description: 'Treillis soudé ST25 — maille 150×150 mm, fil Ø 5 mm, dalles ≥ 10 cm' },
    { name: 'Film polyane', unite_defaut: 'm²', description: 'Film PE 250 µm — barrière vapeur posée sous chape ou dalle béton' },
    { name: 'Isolant sous-chape', unite_defaut: 'm²', description: 'Panneau PSE 20 mm (R=0,65 m²·K/W) — isolation thermique et acoustique sous chape' },
  ],
};

// ─── Représentation locale d'un plan en attente d'upload ─────────────────────
export interface LocalPlanFile {
  file: File;
  name: string;
  description: string;
  previewUrl?: string;
}

@Component({
  selector: 'app-projet-new',
  imports: [CommonModule, FormsModule],
  templateUrl: './projet-new.html',
  styleUrl: './projet-new.scss',
})
export class ProjetNew implements OnInit {

  // ─── Étape courante (1 = infos, 2 = plans, 3 = matériaux) ───────────────
  public currentStep: 1 | 2 | 3 = 1;

  // ─── Step 1 : Informations projet ────────────────────────────────────────
  public projectName = '';
  public projectDescription = '';

  // ─── Step 2 : Plans de bâtiment ──────────────────────────────────────────
  public planFiles: LocalPlanFile[] = [];
  public isDragging = false;

  // ─── Step 3 : Matériaux ──────────────────────────────────────────────────
  public materials: MaterialCreateRequest[] = [];

  // Sélection du type d'ouvrage pour les suggestions
  public ouvrageCategories = Object.keys(OUVRAGES_MATERIAUX);
  public selectedOuvrageCategory = this.ouvrageCategories[0];
  public ouvrageMateriauxMap = OUVRAGES_MATERIAUX;

  // Formulaire ajout manuel
  public newMaterialName = '';
  public newMaterialUnite = '';
  public newMaterialDescription = '';
  public showMaterialForm = false;

  // Suggestions depuis anciens projets
  public suggestedMaterials: MaterialResponse[] = [];
  public isSuggestionsLoading = false;
  public suggestionsLoaded = false;

  // ─── État soumission ──────────────────────────────────────────────────────
  public isSubmitting = false;
  public submitProgress = '';
  public errorMessage = '';

  // ─── Candidat en cours d'édition avant ajout ──────────────────────────────
  public editingCandidate: { name: string; unite_defaut: string; description: string } | null = null;

  private token = localStorage.getItem('access_token') ?? '';

  constructor(
    private api: Api,
    private router: Router,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.loadSuggestions();
  }

  // ─── Navigation entre étapes ──────────────────────────────────────────────

  goToStep(step: 1 | 2 | 3): void {
    if (step === 1) { this.currentStep = 1; return; }
    if (this.canProceedStep1()) { this.currentStep = step; }
  }

  nextStep(): void {
    if (this.currentStep === 1 && this.canProceedStep1()) this.currentStep = 2;
    else if (this.currentStep === 2) this.currentStep = 3;
  }

  prevStep(): void {
    if (this.currentStep === 2) this.currentStep = 1;
    else if (this.currentStep === 3) this.currentStep = 2;
  }

  canProceedStep1(): boolean {
    return this.projectName.trim().length > 0;
  }

  // ─── Step 2 : Gestion des plans de bâtiment ──────────────────────────────

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      this.addFiles(Array.from(input.files));
      input.value = '';
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = true;
  }

  onDragLeave(): void {
    this.isDragging = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = false;
    if (event.dataTransfer?.files) {
      this.addFiles(Array.from(event.dataTransfer.files));
    }
  }

  private addFiles(files: File[]): void {
    const allowed = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
    for (const file of files) {
      if (!allowed.includes(file.type)) continue;
      const previewUrl = file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined;
      this.planFiles.push({
        file,
        name: file.name.replace(/\.[^.]+$/, ''),
        description: '',
        previewUrl,
      });
    }
    this.cdr.detectChanges();
  }

  removePlan(index: number): void {
    const plan = this.planFiles[index];
    if (plan.previewUrl) URL.revokeObjectURL(plan.previewUrl);
    this.planFiles.splice(index, 1);
    this.cdr.detectChanges();
  }

  // ─── Step 3 : Suggestions par type d'ouvrage ─────────────────────────────

  get suggestedByOuvrage(): { name: string; unite_defaut: string; description?: string }[] {
    return this.ouvrageMateriauxMap[this.selectedOuvrageCategory] ?? [];
  }

  importOuvrageMaterial(mat: { name: string; unite_defaut: string; description?: string }): void {
    if (this.isMaterialAdded(mat.name, mat.unite_defaut)) return;
    this.editingCandidate = {
      name: mat.name,
      unite_defaut: mat.unite_defaut,
      description: mat.description ?? '',
    };
    this.cdr.detectChanges();
  }

  isMaterialAdded(name: string, unite: string): boolean {
    return this.materials.some(m => m.name === name && m.unite_defaut === unite);
  }

  // ─── Suggestions depuis anciens projets ───────────────────────────────────

  loadSuggestions(): void {
    this.isSuggestionsLoading = true;
    this.api.getAllUserMaterials(this.token).subscribe({
      next: (mats) => {
        const seen = new Set<string>();
        this.suggestedMaterials = mats.filter(m => {
          const key = `${m.name}__${m.unite_defaut}`;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
        this.isSuggestionsLoading = false;
        this.suggestionsLoaded = true;
        this.cdr.detectChanges();
      },
      error: () => {
        this.isSuggestionsLoading = false;
        this.suggestionsLoaded = true;
        this.cdr.detectChanges();
      },
    });
  }

  importSuggestion(mat: MaterialResponse): void {
    if (this.isMaterialAdded(mat.name, mat.unite_defaut)) return;
    this.editingCandidate = {
      name: mat.name,
      unite_defaut: mat.unite_defaut,
      description: mat.description ?? '',
    };
    this.cdr.detectChanges();
  }

  isSuggestionImported(mat: MaterialResponse): boolean {
    return this.isMaterialAdded(mat.name, mat.unite_defaut);
  }

  // ─── Édition avant ajout ──────────────────────────────────────────────────

  confirmEditedMaterial(): void {
    if (!this.editingCandidate) return;
    const { name, unite_defaut, description } = this.editingCandidate;
    if (!name.trim() || !unite_defaut.trim()) return;
    if (!this.isMaterialAdded(name.trim(), unite_defaut.trim())) {
      this.materials = [
        ...this.materials,
        { name: name.trim(), unite_defaut: unite_defaut.trim(), description: description.trim() || null },
      ];
    }
    this.editingCandidate = null;
    this.cdr.detectChanges();
  }

  cancelEditedMaterial(): void {
    this.editingCandidate = null;
    this.cdr.detectChanges();
  }

  // ─── Ajout manuel ─────────────────────────────────────────────────────────

  addMaterial(): void {
    const name = this.newMaterialName.trim();
    const unite = this.newMaterialUnite.trim();
    if (!name || !unite) return;
    this.materials = [
      ...this.materials,
      { name, unite_defaut: unite, description: this.newMaterialDescription.trim() || null },
    ];
    this.newMaterialName = '';
    this.newMaterialUnite = '';
    this.newMaterialDescription = '';
    this.showMaterialForm = false;
    this.cdr.detectChanges();
  }

  removeMaterial(index: number): void {
    this.materials = this.materials.filter((_, i) => i !== index);
    this.cdr.detectChanges();
  }

  // ─── Soumission ───────────────────────────────────────────────────────────

  canSubmit(): boolean {
    return this.projectName.trim().length > 0 && !this.isSubmitting;
  }

  async submit(): Promise<void> {
    if (!this.canSubmit()) return;
    this.isSubmitting = true;
    this.errorMessage = '';
    this.submitProgress = 'Création du projet…';

    let projectId: number;
    try {
      const project = await lastValueFrom(
        this.api.createProject(this.token, {
          name: this.projectName.trim(),
          description: this.projectDescription.trim() || null,
          materials: this.materials,
        }),
      );
      projectId = project.id;
    } catch (err: any) {
      this.errorMessage = err?.error?.detail ?? 'Erreur lors de la création du projet.';
      this.isSubmitting = false;
      this.submitProgress = '';
      this.cdr.detectChanges();
      return;
    }

    // Upload des plans séquentiellement (non bloquant en cas d'échec unitaire)
    for (let i = 0; i < this.planFiles.length; i++) {
      const plan = this.planFiles[i];
      this.submitProgress = `Upload des plans (${i + 1} / ${this.planFiles.length})…`;
      this.cdr.detectChanges();
      try {
        await lastValueFrom(
          this.api.uploadPlanBatiment(
            this.token,
            projectId,
            plan.file,
            plan.name || undefined,
            plan.description || undefined,
          ),
        );
      } catch {
        // Upload non bloquant : on continue avec les plans suivants
      }
    }

    // Déclencher le workflow agentique une fois tous les plans uploadés
    this.submitProgress = 'Démarrage de l\'analyse…';
    this.cdr.detectChanges();
    try {
      await lastValueFrom(this.api.runProjectWorkflow(this.token, projectId));
    } catch {
      // Le workflow peut aussi être relancé manuellement depuis la page du projet
    }

    this.router.navigate(['/dashboard/projects', projectId]);
  }

  cancel(): void {
    this.router.navigate(['/dashboard/projects']);
  }
}

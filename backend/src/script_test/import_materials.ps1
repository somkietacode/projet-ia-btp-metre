# 1. FIX ENCODAGE : Force UTF-8 pour éviter les "Ã©"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 2. CONFIGURATION
$config = @{
    BaseUrl   = "http://localhost:8742"
    AdminData = @{
        email    = "superadmin@kube.ai"
        password = "SuperAdminPassword123!"
    }
}

$endpoints = @{
    adminLogin    = "$($config.BaseUrl)/auth/admin"
    createMaterial = "$($config.BaseUrl)/admin/materials"
    listMaterials = "$($config.BaseUrl)/admin/materials"
}

# 3. CATALOGUE COMPLET — TABLEAU DE MÉTRÉ BTP
# Champs : name, description, unite_defaut, unite_commerciale, conditionnement, facteur_conversion
# facteur_conversion = nb d'unités techniques (unite_defaut) contenues dans 1 unité commerciale
$materials = @(
    # ── LOT I — TERRASSEMENTS ──────────────────────────────────────────────
    @{ name="Décapage terre végétale";                       description="Décapage sur l'ensemble de l'emprise du bâtiment, épaisseur 20 cm";                              unite_defaut="m²";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Fouilles en pleine masse";                      description="Excavation générale terrain toutes natures jusqu'à côte projet";                                  unite_defaut="m³";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Fouilles en rigoles / tranchées";               description="Semelles filantes, longrines — largeur ≤ 2 m";                                                    unite_defaut="m³";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Fouilles en puits";                             description="Semelles isolées sous poteaux — dim. max ≤ 2 m, prof. > 2 m";                                     unite_defaut="m³";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Transport des terres (déblais)";                description="Évacuation à la décharge publique — appliquer coeff. foisonnement";                               unite_defaut="m³";  unite_commerciale="camion"; conditionnement="Camion 10 m³";                 facteur_conversion=10 },
    @{ name="Remblais primaires (terres du site)";           description="Remise en place et compactage autour des fondations";                                             unite_defaut="m³";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Apport matériaux nobles (remblai)";             description="Sable, gravelette ou 0/31,5 — hérisson sous dallage";                                             unite_defaut="m³";  unite_commerciale="big-bag"; conditionnement="Camion / big-bag";             facteur_conversion=$null },
    @{ name="Feuille géotextile anti-contaminant";           description="Sous hérisson / drainage — recouvrement lés 20-30 cm";                                            unite_defaut="m²";  unite_commerciale="rouleau"; conditionnement="Rouleau 2 m × 50 m (100 m²)"; facteur_conversion=100 },
    @{ name="Drainage périphérique";                         description="Tuyau drain ø100, gravier filtrant 20/40, regards de curage";                                     unite_defaut="ml";  unite_commerciale="couronne"; conditionnement="Couronne 50 m ou barre 6 m"; facteur_conversion=50 },

    # ── LOT II — FONDATIONS ───────────────────────────────────────────────
    @{ name="Béton de propreté (dosé 150 kg/m³)";           description="Ep. 5 cm, débord 10 cm/côté de semelle — sous toutes fondations";                                 unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Centrale à béton / toupie 6 m³"; facteur_conversion=6 },
    @{ name="Béton de structure — Semelles filantes";        description="Largeur × Hauteur × Longueur totale, pertes 3-5 %";                                               unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Toupie 6-8 m³";                facteur_conversion=6 },
    @{ name="Béton de structure — Semelles isolées";         description="Volume géométrique × nb semelles, pertes 3-5 %";                                                   unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Toupie 6-8 m³";                facteur_conversion=6 },
    @{ name="Béton de structure — Radier général";           description="Surface × épaisseur, pertes 3-5 % — dalle épaisse structurelle";                                  unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Toupie / pompe à béton";        facteur_conversion=$null },
    @{ name="Longrines / Poutres de fondation";              description="Béton armé reliant semelles isolées — section et longueurs plans BA";                              unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Toupie 6-8 m³";                facteur_conversion=6 },
    @{ name="Aciers HA — Semelles filantes (attentes incl.)"; description="Barres ø8 à ø16 mm — bordereau de ferraillage obligatoire";                                      unite_defaut="kg";  unite_commerciale="couronne"; conditionnement="Barre 12 m ou couronne 2 t"; facteur_conversion=2000 },
    @{ name="Aciers HA — Semelles isolées + avants-poteaux"; description="Barres ø10 à ø20 mm — avec attentes poteaux";                                                     unite_defaut="kg";  unite_commerciale="couronne"; conditionnement="Barre 12 m ou couronne 2 t"; facteur_conversion=2000 },
    @{ name="Treillis soudé — Radier / dallage";             description="Panneaux ST25, ST35 ou ST50 (6 m × 2,40 m) selon calcul";                                         unite_defaut="U";   unite_commerciale="palette"; conditionnement="Palette de 50 panneaux";       facteur_conversion=50 },
    @{ name="Enduit d'imperméabilisation bitumineux";        description="Application sur faces ext. soubassement — 2 couches";                                              unite_defaut="m²";  unite_commerciale="pot";     conditionnement="Pot 25 kg (≈ 15 m²/pot)";      facteur_conversion=15 },
    @{ name="Nappe de protection à excroissances (Delta-MS)"; description="Protection enduit bitu. / drainage vertical soubassement";                                        unite_defaut="m²";  unite_commerciale="rouleau"; conditionnement="Rouleau 2 m × 20 m (40 m²)";  facteur_conversion=40 },

    # ── LOT III — GROS ŒUVRE ÉLÉVATION ───────────────────────────────────
    @{ name="Béton armé — Poteaux";                          description="Volume géométrique × nb poteaux, ht. libre plancher à plancher";                                   unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Toupie / pompe";                facteur_conversion=$null },
    @{ name="Béton armé — Poutres principales et secondaires"; description="Section × longueur axe en axe — déduire croisements";                                           unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Toupie / pompe";                facteur_conversion=$null },
    @{ name="Béton armé — Dalle pleine";                     description="Surface × épaisseur — déduire trémies > 0,25 m²";                                                 unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Pompe à béton";                 facteur_conversion=$null },
    @{ name="Plancher à corps creux (Hourdis + Poutrelles)"; description="Surface nette — déduire retombées poutres et poteaux";                                             unite_defaut="m²";  unite_commerciale="palette"; conditionnement="Liasse poutrelles / palette hourdis"; facteur_conversion=$null },
    @{ name="Table de compression sur corps creux";          description="Béton fc28 ≥ 20 MPa — ep. 4 à 5 cm sur hourdis";                                                  unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Toupie";                        facteur_conversion=$null },
    @{ name="Aciers HA — Poteaux (cadres + barres long.)";   description="Bordereau de ferraillage — ø10 à ø20 mm";                                                         unite_defaut="kg";  unite_commerciale="couronne"; conditionnement="Barre 12 m ou couronne 2 t"; facteur_conversion=2000 },
    @{ name="Aciers HA — Poutres (barres + étriers)";        description="Bordereau de ferraillage — ø12 à ø25 mm";                                                         unite_defaut="kg";  unite_commerciale="barre";   conditionnement="Barre 12 m";                    facteur_conversion=$null },
    @{ name="Aciers HA — Dalles, chainages, linteaux";       description="Barres et treillis soudés selon plan ferraillage";                                                  unite_defaut="kg";  unite_commerciale="barre";   conditionnement="Barre 12 m / panneau TS";       facteur_conversion=$null },
    @{ name="Coffrage bois (banches) — Poteaux";             description="Surface coffrante × nb de mises en œuvre";                                                         unite_defaut="m²";  unite_commerciale="panneau"; conditionnement="Panneau contreplaqué 18 mm (244×122 cm)"; facteur_conversion=3 },
    @{ name="Coffrage bois — Poutres et dalles";             description="Surface horizontale + faces verticales retombées";                                                  unite_defaut="m²";  unite_commerciale="panneau"; conditionnement="Panneau contreplaqué 18 mm";    facteur_conversion=3 },
    @{ name="Maçonnerie — Blocs creux béton (Agglos 20)";    description="Volume net murs (L × H - baies) × épaisseur — mortier inclus";                                    unite_defaut="m³";  unite_commerciale="palette"; conditionnement="Palette 80 blocs (20×20×40)";   facteur_conversion=$null },
    @{ name="Maçonnerie — Briques creuses (10 ou 15 cm)";    description="Surface nette mur — baies déduites si > 0,5 m²";                                                   unite_defaut="m²";  unite_commerciale="palette"; conditionnement="Palette 300 briques";           facteur_conversion=$null },
    @{ name="Mortier de montage (CPJ 32,5 dosé 250 kg/m³)"; description="Joints maçonnerie et lits de pose — prévoir 0,025 m³/m² de mur";                                  unite_defaut="m³";  unite_commerciale="sac";     conditionnement="Sac 35 kg ou mortier prêt à l'emploi"; facteur_conversion=$null },
    @{ name="Chainages horizontaux BA (pér. + inter.)";      description="Section 15×20 ou 20×20 cm — périmètre × nb niveaux";                                               unite_defaut="ml";  unite_commerciale=$null;    conditionnement="Béton + armatures + coffrage inclus"; facteur_conversion=$null },
    @{ name="Escalier béton armé — Paillasse";               description="Volume béton paillasse + marches massif ou coulé";                                                  unite_defaut="m³";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Acrotère — Béton armé (toiture-terrasse)";      description="Périmètre × section (ex. 20×60 cm) + aciers";                                                      unite_defaut="ml";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },

    # ── LOT IV — COUVERTURE & ÉTANCHÉITÉ ─────────────────────────────────
    @{ name="Étanchéité multicouche — Bitume / asphalte";    description="Système 2 ou 3 couches — bicouche soudé auto-protégé";                                             unite_defaut="m²";  unite_commerciale="rouleau"; conditionnement="Rouleau 10 m × 1 m (10 m²)";  facteur_conversion=10 },
    @{ name="Isolation thermique toiture-terrasse (PSE/PU)"; description="Sous complexe étanchéité — ep. selon RT en vigueur";                                               unite_defaut="m²";  unite_commerciale="panneau"; conditionnement="Panneau 1,20×0,60 m";          facteur_conversion=0.72 },
    @{ name="Forme de pente béton léger";                    description="Pente 1,5 à 3 % vers évacuations — ep. min 4 cm";                                                  unite_defaut="m³";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Chéneau / Noue béton armé";                     description="Ml de chéneau central ou noue inclus étanchéité spécifique";                                       unite_defaut="ml";  unite_commerciale="bande";   conditionnement="Bande Siplast ou équivalent";   facteur_conversion=$null },
    @{ name="Couverture tuiles / tôles (bât. industriels)";  description="Surface réelle inclinée + débords de rive et égout";                                               unite_defaut="m²";  unite_commerciale="palette"; conditionnement="Palette tuiles 250 U ou feuille tôle 0,63 mm"; facteur_conversion=$null },
    @{ name="Charpente métallique (fermettes ou portiques)"; description="Poids total acier charpente selon plan structure";                                                  unite_defaut="kg";  unite_commerciale=$null;    conditionnement="Profilé IPN/HEA, UPN — livraison chantier"; facteur_conversion=$null },

    # ── LOT V — MENUISERIES ───────────────────────────────────────────────
    @{ name="Portes extérieures métal / alu (simples)";      description="Dimensions selon plan façades — avec quincaillerie et seuil";                                      unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Portes intérieures (isoplanes ou semi-pleines)"; description="Dim. standard 83×204 ou sur mesure — dormant + bâti inclus";                                      unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Fenêtres alu / PVC double vitrage";              description="Surface vitrée nette — joint + quincaillerie inclus";                                              unite_defaut="m²";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Baie vitrée coulissante / fixe";                 description="Selon plan façade — volets roulants ou persiennes en option";                                      unite_defaut="m²";  unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Volets roulants / persiennés";                   description="Caisson PVC ou alu intégré — motorisé ou manuel";                                                  unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Vitrage simple / double — Fourniture seule";     description="Si remplacement ou fourniture hors dormant";                                                       unite_defaut="m²";  unite_commerciale="feuille"; conditionnement="Feuille 3,21×2,25 m";          facteur_conversion=7.22 },

    # ── LOT VI — REVÊTEMENTS SOLS & MURS ─────────────────────────────────
    @{ name="Carrelage sol — grès cérame (int.)";             description="Surface nette pièce — déduire éléments fixes < 0,1 m²";                                           unite_defaut="m²";  unite_commerciale="boite";  conditionnement="Boîte 10 carreaux (1 m²)";      facteur_conversion=1 },
    @{ name="Carrelage mur — faïence salle de bain/cuisine"; description="Surface nette murale — hauteur selon plan";                                                         unite_defaut="m²";  unite_commerciale="boite";  conditionnement="Boîte 10 carreaux (1 m²)";      facteur_conversion=1 },
    @{ name="Colle à carrelage (C2 ou C2S)";                  description="0,3 à 0,5 kg/m² selon format — sac 25 kg";                                                        unite_defaut="sac";  unite_commerciale="palette"; conditionnement="Palette 40 sacs";              facteur_conversion=40 },
    @{ name="Joint de carrelage (coulis)";                    description="0,1 à 0,3 kg/m² selon largeur joint";                                                              unite_defaut="sac";  unite_commerciale="boite";  conditionnement="Boîte 10 sacs";                 facteur_conversion=10 },
    @{ name="Chape ciment (dosée 350 kg/m³ — ep. 5 cm)";     description="Surface × 0,05 m — déduction trémies";                                                             unite_defaut="m²";  unite_commerciale="sac";     conditionnement="Sac ciment 50 kg + sable";      facteur_conversion=$null },
    @{ name="Dallage béton (sol RDC — ep. 12 cm)";            description="Surface × 0,12 m — armé TS ou fibré";                                                              unite_defaut="m³";  unite_commerciale="toupie";  conditionnement="Toupie + pompe";                facteur_conversion=$null },
    @{ name="Revêtement souple (PVC, linoléum)";              description="Surface nette + 5 % découpes — largeur rouleau 2 m";                                               unite_defaut="m²";  unite_commerciale="rouleau"; conditionnement="Rouleau 2 m × 25 m (50 m²)";  facteur_conversion=50 },
    @{ name="Parquet flottant ou stratifié";                  description="Surface + 10 % chutes — pose diagonale +15 %";                                                     unite_defaut="m²";  unite_commerciale="boite";  conditionnement="Boîte 2,12 m² (standard)";      facteur_conversion=2.12 },
    @{ name="Peinture intérieure (2 couches + primaire)";     description="Surface murs + plafonds — déduction baies > 0,5 m²";                                               unite_defaut="m²";  unite_commerciale="pot";     conditionnement="Pot 15 L (≈ 30 m²/couche)";    facteur_conversion=30 },
    @{ name="Enduit de façade (mortier bâtard — ep. 20 mm)"; description="Surface façade — baies déduites — 2 couches";                                                       unite_defaut="m²";  unite_commerciale="sac";     conditionnement="Sac 40 kg (8-10 m²)";           facteur_conversion=9 },
    @{ name="Crépi projeté / enduit tyrolien (finition)";     description="Surface façade traitée";                                                                            unite_defaut="m²";  unite_commerciale="sac";     conditionnement="Sac 25 kg (5-8 m²)";            facteur_conversion=6.5 },

    # ── LOT VII — PLOMBERIE & SANITAIRES ─────────────────────────────────
    @{ name="Tuyauterie alimentation eau froide (PE ou PP)"; description="Ml de réseau EF — ø20, ø25, ø32 mm selon plans";                                                   unite_defaut="ml";  unite_commerciale="rouleau"; conditionnement="Barre 6 m ou rouleau 25 m";    facteur_conversion=25 },
    @{ name="Tuyauterie eau chaude (PP-R ou cuivre)";         description="Ml de réseau EC — ø15×21 à ø26×34 mm";                                                             unite_defaut="ml";  unite_commerciale="barre";   conditionnement="Barre 4 m ou rouleau";          facteur_conversion=4 },
    @{ name="Évacuations PVC (EU + EV)";                      description="Ml de réseau intérieur — ø32, ø40, ø50, ø100 mm";                                                  unite_defaut="ml";  unite_commerciale="barre";   conditionnement="Barre PVC 3 m ou 4 m";          facteur_conversion=3 },
    @{ name="Regard de branchement / boîte de sol";           description="Nb de regards — ø315 ou ø400 mm béton ou PVC";                                                     unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Lavabo céramique — fourni posé";                 description="Fourni + posé — robinetterie mitigeur incluse";                                                    unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="WC suspendu ou à poser — complet";               description="Cuvette + abattant + réservoir — mécanisme inclus";                                                unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Douche / Receveur + robinetterie";               description="Bac + colonne ou mitigeur thermostatique";                                                          unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Chauffe-eau électrique ou gaz (cumulus)";        description="Volume selon calcul besoins (50 à 300 L) — groupe sécurité inclus";                                unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },

    # ── LOT VIII — ÉLECTRICITÉ ────────────────────────────────────────────
    @{ name="Tableau électrique principal (TGBT)";            description="Nb de disjoncteurs selon plan électrique";                                                          unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Câble électrique (VGV 3G1,5 ou 3G2,5)";         description="Ml de câble — éclairage 1,5 / prises 2,5 / cuisine 6 mm²";                                        unite_defaut="ml";  unite_commerciale="rouleau"; conditionnement="Rouleau 100 m";                 facteur_conversion=100 },
    @{ name="Gaine IRL / ICT (encastrée ou apparent)";        description="Ml de gaine — ø16, ø20, ø25 mm";                                                                   unite_defaut="ml";  unite_commerciale="couronne"; conditionnement="Couronne 50 m ou barre 3 m"; facteur_conversion=50 },
    @{ name="Interrupteur / va-et-vient simple";              description="Nb selon plan électrique";                                                                          unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Prise de courant 2P+T (16A)";                    description="Nb selon plan — minimum 1 par 4 m² habitable";                                                     unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Point lumineux (boîte d'encastrement + support)"; description="Nb de points d'éclairage selon plan";                                                             unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Détecteur de fumée (DAAF) — certifié NF";        description="Minimum 1 par niveau — palier cage escalier";                                                      unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },

    # ── LOT IX — ISOLATION ────────────────────────────────────────────────
    @{ name="Isolation thermique murs (laine de roche/verre)"; description="Surface murs — doublage contre cloison ou sous enduit ext.";                                     unite_defaut="m²";  unite_commerciale="rouleau"; conditionnement="Rouleau 1,2 m × 5 m (6 m²)";  facteur_conversion=6 },
    @{ name="Isolation plancher bas / sol (PSE sous dallage)"; description="Surface × ep. 5 à 10 cm — sous chape";                                                            unite_defaut="m²";  unite_commerciale="panneau"; conditionnement="Panneau 1,20×0,60 m";          facteur_conversion=0.72 },
    @{ name="Doublage placo (BA13 + isolant 45 mm)";           description="Surface nette doublage — baies déduites";                                                          unite_defaut="m²";  unite_commerciale="plaque";  conditionnement="Plaque BA13 (120×250 cm)";      facteur_conversion=3 },
    @{ name="Cloison de distribution (placo BA13 double face)"; description="Surface nette — ouvertures déduites si > 0,5 m²";                                                unite_defaut="m²";  unite_commerciale="plaque";  conditionnement="Plaque BA13 (120×250 cm)";      facteur_conversion=3 },

    # ── LOT X — VRD & RÉSEAUX EXTÉRIEURS ─────────────────────────────────
    @{ name="Réseau EU / EP enterré (PVC assainissement ø200)"; description="Ml de collecteur — tranchée, lit de sable, remblai compris";                                    unite_defaut="ml";  unite_commerciale="barre";   conditionnement="Barre PVC 3 m";                 facteur_conversion=3 },
    @{ name="Regard de visite préfabriqué béton ø1000";        description="Nb de regards — couvercle fonte D400 ou C250";                                                    unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null },
    @{ name="Branchement eau potable (PE100 ø32 ou ø50)";      description="Ml du réseau public au bâtiment — vannes + compteur";                                             unite_defaut="ml";  unite_commerciale="rouleau"; conditionnement="Rouleau PE100 100 m";           facteur_conversion=100 },
    @{ name="Câble alimentation électrique enterré (U1000RO2V)"; description="Ml depuis TGBT / poste HTA — gaine TPC ø90";                                                   unite_defaut="ml";  unite_commerciale="rouleau"; conditionnement="Rouleau 100 m";                 facteur_conversion=100 },
    @{ name="Dallage béton extérieur — trottoir / parking";    description="Surface × ep. 15-20 cm armé ou fibré";                                                            unite_defaut="m²";  unite_commerciale=$null;    conditionnement="Toupie + pompe";                facteur_conversion=$null },
    @{ name="Clôture — Grillage rigide + poteaux métal";       description="Ml de clôture — H 1,5 à 2 m — fondation béton comprise";                                         unite_defaut="ml";  unite_commerciale="panneau"; conditionnement="Panneau 2,5 m";                 facteur_conversion=2.5 },
    @{ name="Portail / Portillon métallique";                  description="Unité — motorisé ou manuel — avec serrure et gâche";                                               unite_defaut="U";   unite_commerciale=$null;    conditionnement=$null;                          facteur_conversion=$null }
)

# 3. FONCTION DE REQUÊTE COMPATIBLE PS 5.1
function Invoke-ApiRequest {
    param (
        [Parameter(Mandatory=$true)][string]$Uri,
        [Parameter(Mandatory=$true)][string]$Method,
        [object]$Body = $null,
        [hashtable]$Headers = @{},
        [string]$ContentType = "application/json"
    )

    $params = @{
        Uri         = $Uri
        Method      = $Method
        Headers     = $Headers
        ContentType = $ContentType
        ErrorAction = "Stop"
    }

    if ($Body) {
        if ($ContentType -eq "application/json") {
            # Encode explicitement en UTF-8 pour éviter que PS5.1 envoie en Windows-1252
            $jsonStr = $Body | ConvertTo-Json -Compress -Depth 5
            $params.Body = [System.Text.Encoding]::UTF8.GetBytes($jsonStr)
        } else {
            $params.Body = $Body
        }
    }

    try {
        return Invoke-RestMethod @params
    }
    catch {
        $errorMsg = "$($_.Exception.GetType().Name): $($_.Exception.Message)"
        if ($_.Exception.Response) {
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $body = $reader.ReadToEnd()
                $reader.Close()
                if ($body) { $errorMsg += " | API: $body" }
            } catch { $errorMsg += " | (stream unreadable)" }
        }
        Write-Host "[!] Erreur $Method sur $Uri" -ForegroundColor Red
        Write-Host "    Details: $errorMsg" -ForegroundColor Yellow
        return $null
    }
}

# ---------------------------------------------------------------------------
# 4. EXÉCUTION
# ---------------------------------------------------------------------------

Write-Host "`n=== IMPORT DU CATALOGUE DE MATERIAUX ($($materials.Count) articles) ===" -ForegroundColor Cyan

# A. Authentification admin
Write-Host "`n[1/2] Authentification admin..."
$loginBody = "email=$([Uri]::EscapeDataString($config.AdminData.email))&password=$([Uri]::EscapeDataString($config.AdminData.password))"
$loginRes = Invoke-ApiRequest -Uri $endpoints.adminLogin `
                              -Method Post `
                              -Body $loginBody `
                              -ContentType "application/x-www-form-urlencoded"

if ($null -eq $loginRes -or -not $loginRes.access_token) {
    Write-Host " FATAL: Impossible d'obtenir le token admin. Verifiez vos identifiants." -ForegroundColor Red
    exit 1
}
$token = $loginRes.access_token
$authHeader = @{ Authorization = "Bearer $token" }
Write-Host " SUCCESS: Token admin obtenu." -ForegroundColor Green

# B. Insertion des matériaux un par un
Write-Host "`n[2/2] Insertion des materiaux..."
$created = 0
$errors  = 0

foreach ($mat in $materials) {
    # Construction du corps JSON — on exclut les champs null
    $body = [ordered]@{
        name         = $mat.name
        description  = $mat.description
        unite_defaut = $mat.unite_defaut
    }
    if ($null -ne $mat.unite_commerciale)  { $body.unite_commerciale  = $mat.unite_commerciale }
    if ($null -ne $mat.conditionnement)    { $body.conditionnement    = $mat.conditionnement }
    if ($null -ne $mat.facteur_conversion) { $body.facteur_conversion = $mat.facteur_conversion }

    $res = Invoke-ApiRequest -Uri $endpoints.createMaterial `
                             -Method Post `
                             -Body $body `
                             -Headers $authHeader

    if ($res -and $res.id) {
        $created++
        Write-Host "  [OK] #$($res.id) $($res.name)" -ForegroundColor Green
    } else {
        $errors++
        Write-Host "  [!!] $($mat.name)" -ForegroundColor Red
    }
}

# C. Résumé
Write-Host ""
Write-Host "=== RESULTAT ===" -ForegroundColor Cyan
Write-Host "  Inseres : $created / $($materials.Count)" -ForegroundColor Green
if ($errors -gt 0) {
    Write-Host "  Echecs  : $errors" -ForegroundColor Red
} else {
    Write-Host "  Echecs  : aucun" -ForegroundColor Green
}

# D. Vérification post-import
Write-Host "`n=== VERIFICATION POST-IMPORT ===" -ForegroundColor Cyan
$catalogRes = Invoke-ApiRequest -Uri $endpoints.listMaterials -Method Get -Headers $authHeader
if ($catalogRes) {
    Write-Host " Catalogue total : $($catalogRes.Count) materiaux en base." -ForegroundColor Green
    Write-Host ""
    Write-Host " Apercu (5 premiers) :" -ForegroundColor Cyan
    $catalogRes | Select-Object -First 5 | ForEach-Object {
        $conv = if ($_.facteur_conversion) { "1 $($_.unite_commerciale) = $($_.facteur_conversion) $($_.unite_defaut)" } else { "-" }
        Write-Host "    - $($_.name) | Unite: $($_.unite_defaut) | Commercial: $conv"
    }
}

Write-Host "`n=== IMPORT TERMINE ===" -ForegroundColor Cyan

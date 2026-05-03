# 1. FIX ENCODAGE : Force UTF-8 pour éviter les "Ã©"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 2. CONFIGURATION
$config = @{
    BaseUrl  = "http://localhost:8742"
    UserData = @{
        email    = "s.r.a.ouedraogo@gmail.com"
        password = "SecretPassword123!"
    }
}

$endpoints = @{
    register = "$($config.BaseUrl)/auth/register"
    login    = "$($config.BaseUrl)/auth/login"
    me       = "$($config.BaseUrl)/auth/me"
    plans    = "$($config.BaseUrl)/plans"
}

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

    # Correction PS 5.1 : Utilisation de IF au lieu de l'opérateur ternaire
    if ($Body) {
        if ($ContentType -eq "application/json") {
            $params.Body = $Body | ConvertTo-Json
        } else {
            $params.Body = $Body
        }
    }

    try {
        return Invoke-RestMethod @params
    }
    catch {
        $errorMsg = $_.Exception.Message
        # Lecture du flux d'erreur de l'API
        if ($_.Exception.Response) {
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $errorMsg = $reader.ReadToEnd()
                $reader.Close()
            } catch { }
        }
        
        Write-Host "[!] Erreur $Method sur $Uri" -ForegroundColor Red
        Write-Host "    Details: $errorMsg" -ForegroundColor Yellow
        return $null
    }
}

# ---------------------------------------------------------------------------
# 4. EXÉCUTION
# ---------------------------------------------------------------------------

Write-Host "`n=== DEBUT DES TESTS API ===" -ForegroundColor Cyan

# A. Inscription
Write-Host "`n[1/4] Test: Inscription..."
$regRes = Invoke-ApiRequest -Uri $endpoints.register -Method Post -Body $config.UserData
if ($regRes) { 
    Write-Host " SUCCESS: Utilisateur cree." -ForegroundColor Green 
} else {
    Write-Host " INFO: Echec ou utilisateur deja existant." -ForegroundColor Gray
}

# B. Login
Write-Host "`n[2/4] Test: Connexion (Auth)..."
$loginRes = Invoke-ApiRequest -Uri $endpoints.login `
                            -Method Post `
                            -Body $config.UserData `
                            -ContentType "application/x-www-form-urlencoded"

if ($null -eq $loginRes -or -not $loginRes.access_token) {
    Write-Host " FATAL: Impossible de recuperer le Token. Arret." -ForegroundColor Red
    return
}
$token = $loginRes.access_token
Write-Host " SUCCESS: Token obtenu." -ForegroundColor Green

# C. Profil
Write-Host "`n[3/4] Test: Profil (/me)..."
$authHeader = @{ Authorization = "Bearer $token" }
$meRes = Invoke-ApiRequest -Uri $endpoints.me -Method Get -Headers $authHeader
if ($meRes) { 
    Write-Host " SUCCESS: Connecte en tant que $($meRes.email)" -ForegroundColor Green 
    $meRes | ConvertTo-Json | Write-Host
}

# D. Plans
Write-Host "`n[4/4] Test: Liste des plans..."
$plansRes = Invoke-ApiRequest -Uri $endpoints.plans -Method Get
if ($plansRes) {
    Write-Host " SUCCESS: $($plansRes.Count) plans recuperes." -ForegroundColor Green
    $plansRes | ConvertTo-Json | Write-Host -ForegroundColor Cyan
}

Write-Host "`n=== FIN DES TESTS ===" -ForegroundColor Cyan
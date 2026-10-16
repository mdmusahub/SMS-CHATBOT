# Starts Open WebUI (installed in C:\Users\MSI\open-webui-env) on http://127.0.0.1:3000
# wired to the SMS chatbot service on port 8100. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File chatbot\start_open_webui.ps1
$ErrorActionPreference = 'Stop'

$EnvHome = if ($env:OPEN_WEBUI_ENV) { $env:OPEN_WEBUI_ENV } else { Join-Path $HOME 'open-webui-env' }
$DataDir = Join-Path $HOME 'open-webui-data'
$Exe     = Join-Path $EnvHome 'Scripts\open-webui.exe'
$DotEnv  = Join-Path (Split-Path $PSScriptRoot -Parent) '.env'   # single project-root .env
if (-not (Test-Path $Exe)) { throw "Open WebUI not found at $Exe" }
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

# Same key the chatbot service uses (read from the project-root .env, never printed).
$key = (Select-String -Path $DotEnv -Pattern '^CHATBOT_API_KEY=(.+)$').Matches.Groups[1].Value.Trim()
if ($key.Length -lt 32) { throw 'CHATBOT_API_KEY in the project .env is missing or too short.' }

# Persistent signing secret so logins survive restarts.
$secretFile = Join-Path $DataDir 'webui_secret.key'
if (-not (Test-Path $secretFile)) { [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N') | Set-Content $secretFile -NoNewline }

$env:DATA_DIR = $DataDir
$StaticDir = Join-Path $DataDir 'static'                    # keep our theme out of site-packages
New-Item -ItemType Directory -Force -Path $StaticDir | Out-Null
$env:STATIC_DIR = $StaticDir
$env:WEBUI_SECRET_KEY = Get-Content $secretFile -Raw
$env:WEBUI_AUTH = 'true'                                   # per-user login: required for per-user chatbot sessions
$env:ENABLE_SIGNUP = 'true'                                # first account becomes admin; turn off afterwards
$env:ENABLE_FORWARD_USER_INFO_HEADERS = 'true'             # sends X-OpenWebUI-User-Id / Chat-Id to the chatbot
$env:CORS_ALLOW_ORIGIN = 'http://127.0.0.1:3000;http://localhost:3000'   # not '*'
$env:ENABLE_OPENAI_API = 'true'
$env:OPENAI_API_BASE_URL = 'http://127.0.0.1:8100/v1'
$env:OPENAI_API_KEY = $key
$env:ENABLE_OLLAMA_API = 'false'
$env:ENABLE_TITLE_GENERATION = 'false'                     # background calls would hit the login gate
$env:ENABLE_TAGS_GENERATION = 'false'
$env:ENABLE_FOLLOW_UP_GENERATION = 'false'
$env:ENABLE_AUTOCOMPLETE_GENERATION = 'false'
$env:ENABLE_SEARCH_QUERY_GENERATION = 'false'
$env:ENABLE_RETRIEVAL_QUERY_GENERATION = 'false'
$env:ENABLE_WEB_SEARCH = 'false'
$env:ENABLE_CODE_EXECUTION = 'false'
$env:ENABLE_CODE_INTERPRETER = 'false'
$env:ENABLE_IMAGE_GENERATION = 'false'
$env:ENABLE_DIRECT_CONNECTIONS = 'false'
$env:BYPASS_EMBEDDING_AND_RETRIEVAL = 'true'
$env:ANONYMIZED_TELEMETRY = 'false'
$env:DO_NOT_TRACK = 'true'
$env:SCARF_NO_ANALYTICS = 'true'
$env:PYTHONUTF8 = '1'

# Open WebUI wipes and re-copies its static folder on every start, so the theme is copied in
# once the server is healthy (a browser refresh then picks it up).
$theme = Join-Path $PSScriptRoot 'branding\custom.css'
Start-Job -ArgumentList $theme, $StaticDir -ScriptBlock {
    param($theme, $dir)
    for ($i = 0; $i -lt 120; $i++) {
        try {
            if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:3000/health).StatusCode -eq 200) {
                Copy-Item $theme (Join-Path $dir 'custom.css') -Force; break
            }
        } catch { }
        Start-Sleep -Seconds 3
    }
} | Out-Null

& $Exe serve --host 127.0.0.1 --port 3000

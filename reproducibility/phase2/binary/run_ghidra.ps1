$ErrorActionPreference='Stop'
$p2Root=Split-Path -Parent $PSScriptRoot
$p2Workspace=Split-Path -Parent $p2Root
$env:JAVA_HOME=Join-Path $p2Workspace 'tools/jdk-21.0.12.1+1'
$env:PATH=(Join-Path $env:JAVA_HOME 'bin')+';'+$env:PATH
$env:APPDATA=Join-Path $PSScriptRoot 'ghidra-appdata'
$env:JAVA_TOOL_OPTIONS='-Dapplication.settingsdir="'+(Join-Path $PSScriptRoot 'ghidra-settings')+'" -Dapplication.cachedir="'+(Join-Path $PSScriptRoot 'ghidra-cache')+'" -Dapplication.tempdir="'+(Join-Path $PSScriptRoot 'tmp')+'"'
$p2Project=Join-Path $PSScriptRoot 'ghidra-project'
New-Item -ItemType Directory -Force -Path $env:APPDATA,$p2Project | Out-Null
& (Join-Path $p2Workspace 'tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless.bat') $p2Project ForestStudy -import (Join-Path $PSScriptRoot 'forest.dll') -scriptPath $PSScriptRoot -postScript RecoverForest.java (Join-Path $PSScriptRoot 'decompilation.txt') (Join-Path $PSScriptRoot 'recovered-rdata.bin') -analysisTimeoutPerFile 120 -max-cpu 2 -log (Join-Path $PSScriptRoot 'ghidra-application.log') -scriptlog (Join-Path $PSScriptRoot 'ghidra-script.log') 2>&1 | Tee-Object -FilePath (Join-Path $PSScriptRoot 'ghidra-headless.log')
exit $LASTEXITCODE

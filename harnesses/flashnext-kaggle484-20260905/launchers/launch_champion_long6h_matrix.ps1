param(
    [switch]$PreflightOnly,
    [ValidateSet('r1','r2')]
    [string[]]$OnlyReplica = @()
)

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'launch_champion_stall_ab.ps1'
$bundle = 'bundle-q38-flashnext-rtdv12-cap14-kaggle-winner-gcp.tgz'
$bundleMd5 = 'BAoDe9r+9Jvhc57/IBQV7A=='
$runnerSha = '1f37464a2c115aa1f68fcf54e4024ba80f3bcc957fff07ff52bc1025e9c565fe'
$runner = "gs://cellens-ai-artifacts/arc3-duck/code/baseline/v12-run-kaggle11p44-long6h-$runnerSha.py"
$feature = 'flashnext_rtdv12_cap14_kaggle_winner_long6h_cur6_noreplay_noreflection'
$goldenImage = 'arc3-flashnext-7b719225-runtime-v1'

$replicas = @(
    [pscustomobject]@{ Name='r1'; Slug='kwbase-long6h-r1'; Zone='us-east4-c'; StateStem='KWBASE_LONG6H_R1' },
    [pscustomobject]@{ Name='r2'; Slug='kwbase-long6h-r2'; Zone='us-east5-b'; StateStem='KWBASE_LONG6H_R2_RELOC2' }
)

foreach ($replica in $replicas) {
    if ($OnlyReplica.Count -and $replica.Name -notin $OnlyReplica) { continue }
    $stateStem = $replica.StateStem
    $parameters = @{
        ArmSlug = $replica.Slug
        CandidateBundle = $bundle
        CandidateBundleMd5 = $bundleMd5
        CandidateRunner = $runner
        CandidateFeature = $feature
        ReplayArm = 'C'
        ServingProfile = 'best-serving'
        ActionCap = 14
        PostLevelUncappedTurns = 0
        Queued22 = $true
        DisableReplay = $true
        ChampionLongRun = $true
        AnalyzerContextWindow = 32768
        PersistentHistoryAssistantTurns = 30
        MaxRuntimePerGame = 21600
        MaxRunRuntimeMinutes = 440
        DirectInstance = $true
        Zone = $replica.Zone
        GoldenRuntimeImage = $goldenImage
        StateFile = if ($PreflightOnly) {
            "$($stateStem)_PREFLIGHT.json"
        } else {
            "$($stateStem)_STATE.json"
        }
    }
    if ($PreflightOnly) {
        $parameters.PreflightOnly = $true
    }
    & $launcher @parameters
    if ($LASTEXITCODE -ne 0) {
        throw "Six-hour replica $($replica.Slug) failed with exit code $LASTEXITCODE"
    }
}

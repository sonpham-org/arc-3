param(
    [switch]$PreflightOnly,
    [ValidateSet('control','metadata','additive','replace')]
    [string[]]$OnlyMode = @()
)

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'launch_champion_stall_ab.ps1'
$bundle = 'bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-visual-transition-matrix-gcp-r1-20260905.tgz'
$bundleMd5 = 'LQXQM19V7XBtBjPIE3FC9A=='
$runner = 'gs://cellens-ai-artifacts/arc3-duck/code/baseline/v12-run-kaggle11p44-2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2.py'
$goldenImage = 'arc3-flashnext-7b719225-runtime-v1'

$arms = @(
    [pscustomobject]@{ Mode='control';  Slug='kwvtrans-ctl-r1';  Zone='us-east5-a';      StateStem='KWVTRANS_CONTROL_R1' },
    [pscustomobject]@{ Mode='metadata'; Slug='kwvtrans-meta-r1'; Zone='us-east4-c';      StateStem='KWVTRANS_METADATA_R1' },
    [pscustomobject]@{ Mode='additive'; Slug='kwvtrans-add-r1';  Zone='us-central1-b'; StateStem='KWVTRANS_ADDITIVE_RELOC3' },
    [pscustomobject]@{ Mode='replace';  Slug='kwvtrans-repl-r1'; Zone='us-central1-c';   StateStem='KWVTRANS_REPLACE_RELOC1' }
)

foreach ($arm in $arms) {
    if ($OnlyMode.Count -and $arm.Mode -notin $OnlyMode) { continue }
    $feature = "flashnext_rtdv12_cap14_kaggle_winner_visualtransition_$($arm.Mode)_log2cap8_cur6_noreplay_noreflection"
    $stateStem = $arm.StateStem
    $parameters = @{
        ArmSlug = $arm.Slug
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
        VisualTransitionMode = $arm.Mode
        DirectInstance = $true
        Zone = $arm.Zone
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
        throw "Visual-transition $($arm.Mode) arm failed with exit code $LASTEXITCODE"
    }
}

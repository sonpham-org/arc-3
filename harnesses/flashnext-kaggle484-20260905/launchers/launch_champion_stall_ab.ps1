param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[a-z0-9-]+$')]
    [string]$ArmSlug,
    [Parameter(Mandatory=$true)]
    [string]$CandidateBundle,
    [Parameter(Mandatory=$true)]
    [string]$CandidateBundleMd5,
    [Parameter(Mandatory=$true)]
    [string]$CandidateRunner,
    [Parameter(Mandatory=$true)]
    [string]$CandidateFeature,
    [Parameter(Mandatory=$true)]
    [ValidateSet('B','C')]
    [string]$ReplayArm,
    [ValidateSet('baseline','best-serving')]
    [string]$ServingProfile = 'best-serving',
    [ValidateSet(0,6,8,10,12,14,16)]
    [int]$ActionCap = 0,
    [ValidateRange(0,8)]
    [int]$PostLevelUncappedTurns = 0,
    [switch]$VerifiedQueue,
    [switch]$VerifiedHudV2,
    [switch]$VerifiedHudV3,
    [switch]$HypothesisLab,
    [string]$HudCpuBaseUrl = 'http://10.128.0.88:8080/v1',
    [switch]$ColocatedHudCpu,
    [ValidatePattern('^[0-9,-]+$')]
    [string]$ColocatedHudCpuSet = '24-47',
    [switch]$Queued22,
    [switch]$DisableCurator,
    [switch]$DisableReplay,
    [switch]$DynamicSlack,
    [switch]$ExactKaggleChampion,
    [switch]$ChampionLongRun,
    [switch]$Stall140Only,
    [switch]$ExactKaggleCuratorAblation,
    [switch]$ChampionReflectionV3,
    [switch]$ChampionRefinement,
    [switch]$ChampionContextSweep,
    [ValidateSet('none','control','metadata','additive','replace')]
    [string]$VisualTransitionMode = 'none',
    [ValidateSet('none','control','toolkit','reminder','combined')]
    [string]$ToolkitMatrixMode = 'none',
    [ValidateSet('none','toolkit','combined')]
    [string]$VisualToolkitMode = 'none',
    [ValidateRange(16384,65536)]
    [int]$AnalyzerContextWindow = 32768,
    [ValidateRange(1,120)]
    [int]$PersistentHistoryAssistantTurns = 30,
    [switch]$ReflectionV6,
    [ValidateSet('0.55','0.70','0.85')]
    [string]$ContextTriggerFraction = '0.70',
    [switch]$ResumeCompletedGames,
    [ValidatePattern('^[A-Za-z0-9._ -]*$')]
    [string]$GameSubset = '',
    [ValidateRange(60,21600)]
    [int]$MaxRuntimePerGame = 6480,
    [ValidateRange(60,540)]
    [int]$MaxRunRuntimeMinutes = 132,
    [switch]$DirectInstance,
    [switch]$PreflightOnly,
    [string]$Zone = 'us-central1-b',
    [string]$GoldenRuntimeImage = '',
    [string]$StateFile = ''
)

$ErrorActionPreference = 'Stop'

# Prefer the workspace-portable Cloud SDK when present. This avoids inheriting a
# stale machine-wide CLOUDSDK_ROOT_DIR when the launcher is invoked in a child
# PowerShell process.
$PortableGcloudRoot = Join-Path $PSScriptRoot 'gcloud-portable\google-cloud-sdk'
$PortableGcloudCommand = Join-Path $PortableGcloudRoot 'bin\gcloud.cmd'
if (Test-Path -LiteralPath $PortableGcloudCommand) {
    $env:CLOUDSDK_ROOT_DIR = $PortableGcloudRoot
    $env:PATH = "$(Join-Path $PortableGcloudRoot 'bin');$env:PATH"
    Set-Alias -Name gcloud -Value $PortableGcloudCommand -Scope Script
}

$Project = 'cellensml'
$Bucket = 'gs://cellens-ai-artifacts/arc3-duck'
$SourceTemplate = 'arc3-g4-q38-r6animrtdv7-p1r2-20260827203806'
$ExpectedStartupSha = '038C48EA9950835B4544B415256ECAB9A0CDB398E3F23B0D924888F58BBD368B'
$ExpectedBundle = 'bundle-q38-r6-animation-reformed-tool-v7-f180e41d-retry1.tgz'
$ExpectedBundleMd5 = 'v5/qZV0amPCKjEpvbyLY2Q=='
$ExactKaggleBundle = 'bundle-q38-flashnext-rtdv12-cap14-kaggle-winner-gcp.tgz'
$ExactKaggleBundleMd5 = 'BAoDe9r+9Jvhc57/IBQV7A=='
$ChampionContextSweepBundle = 'bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-context-sweep-r1-20260905.tgz'
$ChampionContextSweepBundleMd5 = 'E0eeWyhIHHgRyTMGORg/cg=='
$ChampionVisualTransitionBundle = 'bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-visual-transition-matrix-gcp-r1-20260905.tgz'
$ChampionVisualTransitionBundleMd5 = 'LQXQM19V7XBtBjPIE3FC9A=='
$ToolkitBundle = 'arc3-kaggle484-cpu-toolkit-20260905.tgz'
$ToolkitBundleMd5 = 'JmAOWQcCu9mwDRfiLfYDRA=='
$ToolkitBundleSha = '8841edbce38075456a6451252be79ba55ea1871f8b47161b7f8f932622989e25'
$ReminderBundle = 'arc3-kaggle484-baseline-reminder-20260905.tgz'
$ReminderBundleMd5 = 'EhUzh8QwrAqUbPEW+lTYeQ=='
$ReminderBundleSha = 'e5d2851317a3644565cff595b8670619e06b2b34aad2e033528264fcbd7421e1'
$ToolkitReminderBundle = 'arc3-kaggle484-toolkit-reminder-20260905.tgz'
$ToolkitReminderBundleMd5 = 'fGs+plCL/CNcYR6tD8gZ/g=='
$ToolkitReminderBundleSha = 'bd41632163c14736d7bdae596cd6bd4b4e206d9a664812cb12459aa0986b290b'
$MetadataToolkitBundle = 'arc3-kaggle484-metadata-toolkit-20260905.tgz'
$MetadataToolkitBundleMd5 = '1yUmaMz5WWLF5qw2YxOWQw=='
$MetadataToolkitBundleSha = '01c73733fdfc999182369da530542b1212e50007d5d8d3505f384f61cce9cfb2'
$MetadataToolkitReminderBundle = 'arc3-kaggle484-metadata-toolkit-reminder-20260905.tgz'
$MetadataToolkitReminderBundleMd5 = '+0SSHTax7cJIn7e/g5YhLQ=='
$MetadataToolkitReminderBundleSha = '45526064bf9adb073e9d4fc1f0575d0dda4aa9eb158e102bbb7d4545144b3d8a'
$Stall140Bundle = 'bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-stall140-only-gcp-r1-20260904.tgz'
$Stall140BundleMd5 = '52oe1haOORcOAMZyPrgEvg=='
$ChampionDynamicSlackBundle = 'bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-dynamicslack-gcp-r1-20260904.tgz'
$ChampionDynamicSlackBundleMd5 = 'pFLbKtwbkojwhgzgasLX2g=='
$Stall140DynamicSlackBundle = 'bundle-q38-flashnext-rtdv12-cap14-kaggle11p44-stall140-dynamicslack-gcp-r1-20260904.tgz'
$Stall140DynamicSlackBundleMd5 = 'toRAZEU9DU4qZgPu4O+/4g=='
$ExactKaggleSourceBundle = 'bundle-q38-flashnext-rtdv12-cap14-reflection-v3.tgz'
$ExactKaggleSourceBundleMd5 = 'wscPMpr8va3eu9SfuXEOww=='
$ExactKaggleWarmupSha = '758453bcbf5776c27705e9bf8ad8a174db4980e62a75d5db7c0e26d908d09156'
$ReflectionV6Bundle = 'bundle-q38-contextcompaction-v1.tgz'
$ReflectionV6BundleMd5 = 'HLrnFsY+T1V5MPXHhmXmcA=='
$ContextWarmupSha = '55bc7e832386e4b60012c72567c9bb294d7a74f903d2f5987bc3deff2b1a6d8c'
$DynamicSlackBundle = 'bundle-q38-flashnext-rtdv12-cap14-full-reflection-v3-cur0-noreplay-dynamic-slack-gcp-v2.tgz'
$DynamicSlackBundleMd5 = 'RRRe0v30b+tXBZL+BssCQA=='
$ExpectedRunner = 'gs://cellens-ai-artifacts/arc3-duck/code/v12_run-singlecopy-5d1ba33edecf91da360adb9e2353507fd9f29cc74f45a40aeb3f938f1d793cc5.py'
$ExactKaggleRunner = 'gs://cellens-ai-artifacts/arc3-duck/code/baseline/v12-run-kaggle11p44-2fc2be2e8d0db29b23d588413603d5bc5f36096b5e9fe092f9a3a38f3f1d4ee2.py'
$ChampionLongRunRunnerSha = '1f37464a2c115aa1f68fcf54e4024ba80f3bcc957fff07ff52bc1025e9c565fe'
$ChampionLongRunRunnerMd5 = 'pt3+gMNZqM7PVUMgOPft2g=='
$ChampionLongRunRunner = "$Bucket/code/baseline/v12-run-kaggle11p44-long6h-$ChampionLongRunRunnerSha.py"
$ChampionReflectionV3RunnerSha = '8fa07e58d23da92db1fabb2102f70a6f12b7bebdd82e5dc2fd326b6268fd7d4a'
$ChampionReflectionV3RunnerMd5 = '/T4MD6p14dfHuY+360JaSA=='
$ChampionReflectionV3Runner = "$Bucket/code/reasoning/v12-run-kaggle11p44-reflectionv3-$ChampionReflectionV3RunnerSha.py"
$ChampionRefinementRunnerSha = 'b0910d2bae2424b78f39f1df71d38b69b08c567152f1869ad2ceac1fc8c86ae6'
$ChampionRefinementRunnerMd5 = 'zD6QQG4GoGLrPzwgP3RYAw=='
$ChampionRefinementRunner = "$Bucket/code/reasoning/v12-run-kaggle11p44-refinement-$ChampionRefinementRunnerSha.py"
$ExpectedResumableRunner = 'gs://cellens-ai-artifacts/arc3-duck/code/resume/v12-run-resumable-0b5db6b1de033465b52e73bbde4b3e473d23c344190f6a6b61e87961756ab5ad.py'
$ExpectedCurator = 'gs://cellens-ai-artifacts/arc3-duck/code/sidecar/nvfp4-cross-game-curator-44b955abf8a819de178e908f7220be23fc1f3326134a5a8542fd4cea4613fab0.py'
$ExpectedBasePleSha = 'a71144c1d36e06f22a2da1b1ada900076597fe5e824a911e7ada86249a0993e7'
$RuntimeOverlayPromptsSha = '397bc786f7c01dfd534837a7e8570c59cd9d82c6611663745b41ba164de99e4c'
$RuntimeOverlaySandboxSha = '3140f6092a0fcbdfb379c4835c8357f5f3259ec5d91501df2d7a05de2ef7e992'
$RuntimeOverlayToolAgentV3Sha = 'b5f690c84614adddd84fbecf6e516d9c9b55a5f45cd7e3c6d1fd304f201f6d8e'
$RuntimeOverlayToolAgentV6Sha = 'f5c435290e3356ecc078263d82d8f11e69b5aeb1d8f7f337aa02d8f21ee81afe'
$RuntimeOverlayToolAgentSha = if ($ReflectionV6) { $RuntimeOverlayToolAgentV6Sha } else { $RuntimeOverlayToolAgentV3Sha }
$PlePatchSha = '2f0e6febb8c6fdeeeb5b85cc2d7098ba7ce7ee2464d690c33fdcf75e3215c33a'
$PlePatchObject = "$Bucket/code/flash-next/ple-layer-native-fp8-$PlePatchSha.py"
$ModelId = 'RadixArk/Qwen3.8-Flash-Next-NVFP4'
$ModelRevision = '7b719225242aacd3dbd3f9407468c2ee9a9d2594'
$ModelMirrorPrefix = "$Bucket/models/qwen3.8-flash-next-nvfp4-radixark/$ModelRevision"
$ContainerImage = 'vllm/vllm-openai@sha256:fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8'
$ExpectedGoldenRuntimeImage = 'arc3-flashnext-7b719225-runtime-v1'
$ConverterPath = Join-Path $PSScriptRoot 'convert_radix_ple_fp8_to_bf16.py'
$ScoreObserverPath = Join-Path $PSScriptRoot 'arc3_minute_score_observer.py'
$JsonPostHelperPath = Join-Path $PSScriptRoot 'gcp_json_post.py'
$ColocatedHudInstallerPath = Join-Path $PSScriptRoot 'start_colocated_hud_server.sh'
if (!$StateFile) { $StateFile = "FLASH_NEXT_MATRIX_$($ArmSlug.ToUpperInvariant().Replace('-','_'))_STATE.json" }
$StatePath = Join-Path $PSScriptRoot $StateFile
if ($GoldenRuntimeImage -and $GoldenRuntimeImage -ne $ExpectedGoldenRuntimeImage) {
    throw "Golden runtime image identity drift; expected $ExpectedGoldenRuntimeImage"
}
if ($HypothesisLab -and !$VerifiedQueue) {
    throw 'HypothesisLab requires VerifiedQueue so every executed action has CPU evidence.'
}
if ($VerifiedQueue -or $VerifiedHudV2 -or $VerifiedHudV3 -or $HypothesisLab -or $ColocatedHudCpu) {
    throw 'Replay B/C must remain a clean Cap-14 causal arm without queue, HUD, graph, or hypothesis-lab features.'
}
if ($ResumeCompletedGames -and $DirectInstance) {
    throw 'ResumeCompletedGames requires a managed instance group so Spot loss recreates the VM.'
}
$visualTransitionArm = $VisualTransitionMode -ne 'none'
$toolkitMatrixArm = $ToolkitMatrixMode -ne 'none'
$visualToolkitArm = $VisualToolkitMode -ne 'none'
$effectiveVisualTransitionMode = if ($visualTransitionArm) { $VisualTransitionMode } elseif ($visualToolkitArm) { 'metadata' } else { $null }
$toolkitEnabledForRun = ($toolkitMatrixArm -and $ToolkitMatrixMode -in @('toolkit','combined')) -or $visualToolkitArm
$reminderEnabledForRun = ($toolkitMatrixArm -and $ToolkitMatrixMode -in @('reminder','combined')) -or ($visualToolkitArm -and $VisualToolkitMode -eq 'combined')
$toolkitSelftestMode = if ($toolkitMatrixArm) { $ToolkitMatrixMode } elseif ($visualToolkitArm) { "metadata-$VisualToolkitMode" } else { 'none' }
$exactKaggleSemantics = $ExactKaggleChampion -or $ChampionLongRun -or $Stall140Only -or $ExactKaggleCuratorAblation -or $ChampionReflectionV3 -or $ChampionRefinement -or $ChampionContextSweep -or $visualTransitionArm -or $toolkitMatrixArm -or $visualToolkitArm
$reflectionVersion = if ($ChampionReflectionV3) { 'v3' } elseif ($exactKaggleSemantics) { 'disabled' } elseif ($ReflectionV6) { 'v6' } else { 'v3' }
$exactArmCount = 0
foreach ($flag in @($ExactKaggleChampion, $ChampionLongRun, $Stall140Only, $ExactKaggleCuratorAblation, $ChampionReflectionV3, $ChampionRefinement, $ChampionContextSweep, $visualTransitionArm, $toolkitMatrixArm, $visualToolkitArm)) {
    if ($flag) { $exactArmCount += 1 }
}
if ($exactArmCount -gt 1) {
    throw 'Choose exactly one exact-Kaggle arm.'
}
if ($exactKaggleSemantics) {
    if (!$DisableReplay) { throw 'Exact Kaggle semantics require DisableReplay.' }
    if (!$Queued22) { throw 'Exact Kaggle semantics require the 22-worker queue.' }
    if ($ActionCap -ne 14) { throw 'Exact Kaggle semantics require strict cumulative cap 14.' }
    if ($PostLevelUncappedTurns -ne 0) { throw 'Exact Kaggle semantics require PLU disabled.' }
    if ($ServingProfile -ne 'best-serving') { throw 'Exact Kaggle semantics require the locked best-serving profile.' }
    $expectedGameRuntime = if ($ChampionLongRun) { 21600 } else { 6480 }
    $expectedSuiteMinutes = if ($ChampionLongRun) { 440 } else { 132 }
    if ($MaxRuntimePerGame -ne $expectedGameRuntime -or $MaxRunRuntimeMinutes -ne $expectedSuiteMinutes) {
        throw "Exact Kaggle arm runtime drift; expected $expectedGameRuntime seconds/game and $expectedSuiteMinutes suite minutes."
    }
    $expectedExactBundle = if ($visualToolkitArm) {
        switch ($VisualToolkitMode) {
            'toolkit' { $MetadataToolkitBundle }
            'combined' { $MetadataToolkitReminderBundle }
        }
    } elseif ($toolkitMatrixArm) {
        switch ($ToolkitMatrixMode) {
            'control' { $ExactKaggleBundle }
            'toolkit' { $ToolkitBundle }
            'reminder' { $ReminderBundle }
            'combined' { $ToolkitReminderBundle }
        }
    } elseif ($visualTransitionArm) {
        $ChampionVisualTransitionBundle
    } elseif ($ChampionContextSweep) {
        $ChampionContextSweepBundle
    } elseif ($Stall140Only -and $DynamicSlack) {
        $Stall140DynamicSlackBundle
    } elseif ($DynamicSlack) {
        $ChampionDynamicSlackBundle
    } elseif ($Stall140Only) {
        $Stall140Bundle
    } else {
        $ExactKaggleBundle
    }
    $expectedExactBundleMd5 = if ($visualToolkitArm) {
        switch ($VisualToolkitMode) {
            'toolkit' { $MetadataToolkitBundleMd5 }
            'combined' { $MetadataToolkitReminderBundleMd5 }
        }
    } elseif ($toolkitMatrixArm) {
        switch ($ToolkitMatrixMode) {
            'control' { $ExactKaggleBundleMd5 }
            'toolkit' { $ToolkitBundleMd5 }
            'reminder' { $ReminderBundleMd5 }
            'combined' { $ToolkitReminderBundleMd5 }
        }
    } elseif ($visualTransitionArm) {
        $ChampionVisualTransitionBundleMd5
    } elseif ($ChampionContextSweep) {
        $ChampionContextSweepBundleMd5
    } elseif ($Stall140Only -and $DynamicSlack) {
        $Stall140DynamicSlackBundleMd5
    } elseif ($DynamicSlack) {
        $ChampionDynamicSlackBundleMd5
    } elseif ($Stall140Only) {
        $Stall140BundleMd5
    } else {
        $ExactKaggleBundleMd5
    }
    if ($CandidateBundle -ne $expectedExactBundle -or $CandidateBundleMd5 -ne $expectedExactBundleMd5) {
        throw 'Exact Kaggle arm bundle identity drift.'
    }
}
if (!$ChampionContextSweep -and ($AnalyzerContextWindow -ne 32768 -or $PersistentHistoryAssistantTurns -ne 30)) {
    throw 'Non-default context or history settings require ChampionContextSweep.'
}
if ($ChampionContextSweep) {
    if ($DisableCurator) { throw 'ChampionContextSweep requires the champion persistent top-six GPU curator.' }
    if ($DynamicSlack -or $Stall140Only -or $ChampionReflectionV3 -or $ChampionRefinement -or $ReflectionV6) {
        throw 'ChampionContextSweep must remain a sole-delta champion arm.'
    }
    if ($CandidateRunner -ne $ExactKaggleRunner) {
        throw 'ChampionContextSweep requires the post-unpickle 22-worker/6480-second baseline runner.'
    }
    $expectedContextFeature = "flashnext_rtdv12_cap14_kaggle_winner_ctx$($AnalyzerContextWindow)_fixed$($PersistentHistoryAssistantTurns)_cur6_noreplay_noreflection"
    if ($CandidateFeature -ne $expectedContextFeature) {
        throw "ChampionContextSweep feature identity drift; expected $expectedContextFeature"
    }
}
if ($visualTransitionArm) {
    if ($DisableCurator) { throw 'Visual-transition matrix requires the champion persistent top-six GPU curator.' }
    if ($DynamicSlack -or $Stall140Only -or $ChampionReflectionV3 -or $ChampionRefinement -or $ChampionContextSweep -or $ReflectionV6) {
        throw 'Visual-transition matrix must remain a sole-delta champion arm.'
    }
    if ($CandidateRunner -ne $ExactKaggleRunner) {
        throw 'Visual-transition matrix requires the post-unpickle 22-worker/6480-second baseline runner.'
    }
    $expectedVisualFeature = "flashnext_rtdv12_cap14_kaggle_winner_visualtransition_$($VisualTransitionMode)_log2cap8_cur6_noreplay_noreflection"
    if ($CandidateFeature -ne $expectedVisualFeature) {
        throw "Visual-transition feature identity drift; expected $expectedVisualFeature"
    }
}
if ($toolkitMatrixArm) {
    if ($DisableCurator) { throw 'Toolkit matrix requires the champion persistent top-six GPU curator.' }
    if ($DynamicSlack -or $Stall140Only -or $ChampionReflectionV3 -or $ChampionRefinement -or $ChampionContextSweep -or $ReflectionV6 -or $visualTransitionArm) {
        throw 'Toolkit matrix must remain a sole-delta champion experiment.'
    }
    if ($CandidateRunner -ne $ExactKaggleRunner) {
        throw 'Toolkit matrix requires the post-unpickle 22-worker/6480-second baseline runner.'
    }
    $expectedToolkitFeature = switch ($ToolkitMatrixMode) {
        'control' { 'flashnext_rtdv12_cap14_kaggle_winner_toolkit_control_cur6_noreplay_noreflection' }
        'toolkit' { 'flashnext_rtdv12_cap14_kaggle_winner_cpu_toolkit_cur6_noreplay_noreflection' }
        'reminder' { 'flashnext_rtdv12_cap14_kaggle_winner_budget_reminder_cur6_noreplay_noreflection' }
        'combined' { 'flashnext_rtdv12_cap14_kaggle_winner_cpu_toolkit_budget_reminder_cur6_noreplay_noreflection' }
    }
    if ($CandidateFeature -ne $expectedToolkitFeature) {
        throw "Toolkit matrix feature identity drift; expected $expectedToolkitFeature"
    }
}
if ($visualToolkitArm) {
    if ($DisableCurator) { throw 'Visual-toolkit crossover requires the champion persistent top-six GPU curator.' }
    if ($DynamicSlack -or $Stall140Only -or $ChampionReflectionV3 -or $ChampionRefinement -or $ChampionContextSweep -or $ReflectionV6 -or $visualTransitionArm -or $toolkitMatrixArm) {
        throw 'Visual-toolkit crossover must remain a clean combination experiment.'
    }
    if ($CandidateRunner -ne $ExactKaggleRunner) {
        throw 'Visual-toolkit crossover requires the post-unpickle 22-worker/6480-second baseline runner.'
    }
    $expectedCrossoverFeature = switch ($VisualToolkitMode) {
        'toolkit' { 'flashnext_rtdv12_cap14_kaggle_winner_visualtransition_metadata_cpu_toolkit_cur6_noreplay_noreflection' }
        'combined' { 'flashnext_rtdv12_cap14_kaggle_winner_visualtransition_metadata_cpu_toolkit_budget_reminder_cur6_noreplay_noreflection' }
    }
    if ($CandidateFeature -ne $expectedCrossoverFeature) {
        throw "Visual-toolkit crossover feature identity drift; expected $expectedCrossoverFeature"
    }
}
if ($Stall140Only) {
    if ($DisableCurator) { throw 'Stall140Only requires the champion persistent top-six GPU curator.' }
    if ($CandidateRunner -ne $ExactKaggleRunner) {
        throw 'Stall140Only requires the post-unpickle 22-worker/6480-second baseline runner.'
    }
    $expectedStallFeature = if ($DynamicSlack) {
        'flashnext_rtdv12_cap14_kaggle_winner_stall140_dynamicslack_cur6_noreplay_noreflection'
    } else {
        'flashnext_rtdv12_cap14_kaggle_winner_stall140_cur6_noreplay_noreflection'
    }
    if ($CandidateFeature -ne $expectedStallFeature) {
        throw 'Stall140Only feature identity drift.'
    }
}
if ($ChampionLongRun) {
    if ($DisableCurator) { throw 'ChampionLongRun requires the champion persistent top-six GPU curator.' }
    if ($DynamicSlack -or $Stall140Only -or $ChampionReflectionV3 -or $ChampionRefinement -or $ChampionContextSweep -or $ReflectionV6 -or $visualTransitionArm) {
        throw 'ChampionLongRun must remain a sole-delta exact-baseline arm.'
    }
    if ($CandidateRunner -ne $ChampionLongRunRunner) {
        throw 'ChampionLongRun requires the immutable audited six-hour runner.'
    }
    if ($CandidateFeature -ne 'flashnext_rtdv12_cap14_kaggle_winner_long6h_cur6_noreplay_noreflection') {
        throw 'ChampionLongRun feature identity drift.'
    }
}
if ($ExactKaggleChampion) {
    if ($DisableCurator) { throw 'ExactKaggleChampion requires the persistent top-six GPU curator.' }
    if ($CandidateRunner -ne $ExactKaggleRunner) {
        throw 'ExactKaggleChampion requires the post-unpickle 22-worker/6480-second baseline runner.'
    }
    $expectedChampionFeature = if ($DynamicSlack) {
        'flashnext_rtdv12_cap14_kaggle_winner_dynamicslack_cur6_noreplay_noreflection'
    } else {
        'flashnext_rtdv12_cap14_kaggle_winner_cur6_noreplay_noreflection'
    }
    if ($CandidateFeature -ne $expectedChampionFeature) {
        throw 'ExactKaggleChampion feature identity drift.'
    }
}
if ($ExactKaggleCuratorAblation) {
    if (!$DisableCurator) { throw 'ExactKaggleCuratorAblation requires curator disabled.' }
    if ($CandidateFeature -ne 'flashnext_rtdv12_cap14_kaggle_winner_cur0_noreplay_noreflection') {
        throw 'ExactKaggleCuratorAblation feature identity drift.'
    }
}
if ($ChampionReflectionV3) {
    if ($DisableCurator) { throw 'ChampionReflectionV3 requires the champion persistent top-six GPU curator.' }
    if ($DynamicSlack -or $Stall140Only -or $ChampionRefinement -or $ReflectionV6) {
        throw 'ChampionReflectionV3 must remain a sole-delta champion arm.'
    }
    if ($CandidateRunner -ne $ChampionReflectionV3Runner) {
        throw 'ChampionReflectionV3 runner identity drift.'
    }
    if ($CandidateFeature -ne 'flashnext_rtdv12_cap14_kaggle_winner_reflectionv3_cur6_noreplay') {
        throw 'ChampionReflectionV3 feature identity drift.'
    }
}
if ($ChampionRefinement) {
    if ($DisableCurator) { throw 'ChampionRefinement requires the champion persistent top-six GPU curator.' }
    if ($DynamicSlack -or $Stall140Only -or $ChampionReflectionV3 -or $ReflectionV6) {
        throw 'ChampionRefinement must remain a sole-delta champion arm.'
    }
    if ($CandidateRunner -ne $ChampionRefinementRunner) {
        throw 'ChampionRefinement runner identity drift.'
    }
    if ($CandidateFeature -ne 'flashnext_rtdv12_cap14_kaggle_winner_refinement_cur6_noreplay_noreflection') {
        throw 'ChampionRefinement feature identity drift.'
    }
}
if ($ReflectionV6) {
    if ($exactKaggleSemantics) { throw 'ReflectionV6 cannot be combined with exact no-reflection Kaggle semantics.' }
    if ($DisableReplay -or $ReplayArm -ne 'C') { throw 'Context-compaction cells require Replay-C enabled.' }
    if ($DisableCurator) { throw 'Context-compaction cells require the locked top-six curator.' }
    if (!$Queued22) { throw 'ReflectionV6 causal cells require the 22-worker queue.' }
    if (!$ResumeCompletedGames) { throw 'ReflectionV6 causal cells require resumable managed-instance execution.' }
    if ($ActionCap -ne 14) { throw 'ReflectionV6 causal cells require strict cumulative cap 14.' }
    if ($PostLevelUncappedTurns -ne 0) { throw 'ReflectionV6 causal cells require PLU disabled.' }
    if ($ServingProfile -ne 'best-serving') { throw 'ReflectionV6 causal cells require the locked best-serving profile.' }
    if ($MaxRuntimePerGame -ne 6180 -or $MaxRunRuntimeMinutes -ne 132) {
        throw 'ReflectionV6 causal cells require the 6180-second game cap and 132-minute suite boundary.'
    }
    if ($CandidateBundle -ne $ReflectionV6Bundle -or $CandidateBundleMd5 -ne $ReflectionV6BundleMd5) {
        throw 'ReflectionV6 bundle identity drift.'
    }
    if ($CandidateRunner -ne $ExpectedResumableRunner) { throw 'ReflectionV6 requires the pinned resumable runner.' }
    $triggerSlug = $ContextTriggerFraction.Replace('.', '')
    $expectedV6Feature = "flashnext_rtdv13_cap14_replayc_reflectionv6_cur6_ctx$triggerSlug"
    if ($CandidateFeature -ne $expectedV6Feature) { throw 'ReflectionV6 feature identity drift.' }
}
if ($DynamicSlack) {
    if ($ReflectionV6) { throw 'DynamicSlack cannot be combined with Reflection V6.' }
    if ($ResumeCompletedGames) { throw 'DynamicSlack uses the direct-instance fixed suite boundary.' }
    if (!$DirectInstance) { throw 'DynamicSlack requires direct-instance execution.' }
    if (!$exactKaggleSemantics) {
        if (!$DisableReplay) { throw 'DynamicSlack V5 requires replay disabled.' }
        if (!$DisableCurator) { throw 'DynamicSlack V5 requires the world-model curator disabled.' }
        if (!$Queued22) { throw 'DynamicSlack V5 requires the 22-worker queue.' }
        if ($ActionCap -ne 14) { throw 'DynamicSlack V5 requires strict cumulative cap 14.' }
        if ($PostLevelUncappedTurns -ne 0) { throw 'DynamicSlack V5 requires PLU disabled.' }
        if ($ServingProfile -ne 'best-serving') { throw 'DynamicSlack V5 requires the locked best-serving profile.' }
        if ($MaxRuntimePerGame -ne 6180 -or $MaxRunRuntimeMinutes -ne 132) {
            throw 'DynamicSlack V5 requires the 6180-second baseline game cap and 132-minute suite boundary.'
        }
        if ($CandidateBundle -ne $DynamicSlackBundle -or $CandidateBundleMd5 -ne $DynamicSlackBundleMd5) {
            throw 'DynamicSlack V5 bundle identity drift.'
        }
        if ($CandidateRunner -ne $ExpectedRunner) { throw 'DynamicSlack V5 requires the pinned single-copy runner.' }
        if ($CandidateFeature -ne 'flashnext_rtdv12_cap14_full_reflectionv3_cur0_noreplay_dynamic_slack') {
            throw 'DynamicSlack V5 feature identity drift.'
        }
    }
}

function Invoke-Gcloud([string[]]$Arguments) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & gcloud @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        throw "gcloud $($Arguments -join ' ') failed:`n$($output -join "`n")"
    }
    return ($output -join "`n")
}

function Invoke-GcpJsonPost([string]$Uri, [string]$Body) {
    $python = if ($env:CLOUDSDK_PYTHON) { $env:CLOUDSDK_PYTHON } else { 'python.exe' }
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = $Body | & $python $JsonPostHelperPath $Uri 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        throw "GCP JSON POST failed for $Uri`n$($output -join "`n")"
    }
    return (($output -join "`n") | ConvertFrom-Json)
}

function Get-StringSha256([string]$Text) {
    $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha256.ComputeHash($bytes))).Replace('-', '')
    } finally {
        $sha256.Dispose()
    }
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHashHex $Path 'SHA256').ToLowerInvariant()
}

function Get-FileHashHex([string]$Path, [string]$Algorithm) {
    $hasher = [Security.Cryptography.HashAlgorithm]::Create($Algorithm)
    if ($null -eq $hasher) { throw "Unsupported hash algorithm: $Algorithm" }
    $stream = [IO.File]::OpenRead($Path)
    try {
        return ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace('-', '')
    } finally {
        $stream.Dispose()
        $hasher.Dispose()
    }
}

function Wait-GlobalOperation([string]$Name) {
    for ($i = 1; $i -le 120; $i++) {
        $operation = (Invoke-Gcloud @('compute','operations','describe',$Name,'--global','--project',$Project,'--format=json')) | ConvertFrom-Json
        if ($operation.status -eq 'DONE') {
            if ($operation.error) { throw ($operation.error | ConvertTo-Json -Depth 20 -Compress) }
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "Timed out waiting for global operation $Name"
}

function Wait-ZonalOperation([string]$Name, [string]$OperationZone) {
    for ($i = 1; $i -le 120; $i++) {
        $operation = (Invoke-Gcloud @('compute','operations','describe',$Name,'--zone',$OperationZone,'--project',$Project,'--format=json')) | ConvertFrom-Json
        if ($operation.status -eq 'DONE') {
            if ($operation.error) { throw ($operation.error | ConvertTo-Json -Depth 20 -Compress) }
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "Timed out waiting for zonal operation $Name"
}

function Set-OrAddMetadata([Collections.ArrayList]$Items, [string]$Key, [string]$Value) {
    $matches = @($Items | Where-Object key -eq $Key)
    if ($matches.Count -gt 1) { throw "Duplicate metadata key $Key" }
    if ($matches.Count -eq 1) { $matches[0].value = $Value }
    else { [void]$Items.Add([pscustomobject]@{key=$Key; value=$Value}) }
}

function Assert-Absent([string[]]$Arguments, [string]$Label) {
    & gcloud @Arguments *> $null
    if ($LASTEXITCODE -eq 0) { throw "$Label already exists; refusing duplicate" }
}

if (!(Test-Path -LiteralPath $ConverterPath)) { throw "Missing converter: $ConverterPath" }
if (!(Test-Path -LiteralPath $ScoreObserverPath)) { throw "Missing score observer: $ScoreObserverPath" }
if (!(Test-Path -LiteralPath $JsonPostHelperPath)) { throw "Missing GCP JSON POST helper: $JsonPostHelperPath" }
if (Test-Path -LiteralPath $StatePath) { throw "Launch state already exists: $StatePath" }
if ($VerifiedHudV2 -and !$VerifiedQueue) { throw 'VerifiedHudV2 requires VerifiedQueue' }
if ($VerifiedHudV3 -and !$VerifiedQueue) { throw 'VerifiedHudV3 requires VerifiedQueue' }
if ($ColocatedHudCpu -and !$VerifiedHudV3) { throw 'ColocatedHudCpu requires VerifiedHudV3' }
if ($ColocatedHudCpu) {
    if (!(Test-Path -LiteralPath $ColocatedHudInstallerPath)) {
        throw "Missing colocated HUD installer: $ColocatedHudInstallerPath"
    }
    $HudCpuBaseUrl = 'http://127.0.0.1:8080/v1'
}

$adcToken = if ($env:CLOUDSDK_AUTH_ACCESS_TOKEN) {
    $env:CLOUDSDK_AUTH_ACCESS_TOKEN.Trim()
} else {
    ((@(& gcloud auth application-default print-access-token 2>$null)) -join '').Trim()
}
if (!$adcToken) { throw 'Application-default credentials did not return an access token' }
$env:CLOUDSDK_AUTH_ACCESS_TOKEN = $adcToken

$mirrorDone = (((Invoke-Gcloud @('storage','cat',"$ModelMirrorPrefix/_mirror/DONE")) -join "`n") | ConvertFrom-Json)
$mirrorManifest = (((Invoke-Gcloud @('storage','cat',"$ModelMirrorPrefix/_mirror/MANIFEST.json")) -join "`n") | ConvertFrom-Json)
if ($mirrorDone.revision -ne $ModelRevision -or $mirrorManifest.revision -ne $ModelRevision) {
    throw 'GCS Flash-Next mirror revision drift'
}
if ([int64]$mirrorDone.total_bytes -ne [int64]$mirrorManifest.total_bytes -or
    [int]$mirrorDone.file_count -ne [int]$mirrorManifest.file_count -or
    [int]$mirrorManifest.file_count -lt 400 -or [int64]$mirrorManifest.total_bytes -lt 130000000000) {
    throw 'GCS Flash-Next mirror manifest is incomplete or inconsistent'
}

$goldenImageInfo = $null
if ($GoldenRuntimeImage) {
    $goldenImageInfo = (Invoke-Gcloud @('compute','images','describe',$GoldenRuntimeImage,'--project',$Project,'--format=json')) | ConvertFrom-Json
    if ($goldenImageInfo.status -ne 'READY' -or $goldenImageInfo.family -ne 'arc3-flashnext-runtime') {
        throw 'Golden runtime image is not READY in the pinned ARC3 runtime family'
    }
    if ([string]$goldenImageInfo.sourceDisk -notmatch '/arc3-g4-q38-kwbase-r2e1$') {
        throw 'Golden runtime image source disk identity drift'
    }
}

$source = (Invoke-Gcloud @('compute','instance-templates','describe',$SourceTemplate,'--project',$Project,'--format=json')) | ConvertFrom-Json
$sourceMeta = @{}
foreach ($item in @($source.properties.metadata.items)) { $sourceMeta[$item.key] = [string]$item.value }
$sourceStartup = $sourceMeta['startup-script']
if ((Get-StringSha256 $sourceStartup) -ne $ExpectedStartupSha) { throw 'Source startup hash drift' }
if ($sourceMeta['arc3-bundle'] -ne $ExpectedBundle) { throw 'Reformed-tool bundle drift' }
if ($sourceMeta['arc3-runner-object'] -ne $ExpectedRunner) { throw 'Runner drift' }
if ($sourceMeta['arc3-curator-object'] -ne $ExpectedCurator) { throw 'Curator drift' }
if ($sourceMeta['arc3-influence-mode'] -ne 'gpu_world_model_curator') { throw 'Curator mode drift' }
if ($sourceMeta['arc3-feature-arm'] -ne 'animation_reformed_tool_description_v7') { throw 'Reformed-tool feature drift' }
$resumeShutdownText = $null
if ($ResumeCompletedGames) {
    $resumeShutdownText = ([string]$sourceMeta['shutdown-script']).Replace("`r`n", "`n").Replace("`r", "`n")
    $shutdownResize = @'
timeout 10 gcloud compute instance-groups managed resize "$MIG" --size=0 \
  --zone="$ZONE" >/dev/null 2>&1 || true
'@
    if ([regex]::Matches($resumeShutdownText, [regex]::Escape($shutdownResize)).Count -ne 1) {
        throw 'Shutdown resize guard drift'
    }
    $resumeShutdownText = $resumeShutdownText.Replace(
        $shutdownResize,
        'echo "resume-enabled shutdown: synchronized state retained for MIG recreation"'
    )
}

$bundleInfo = (Invoke-Gcloud @('storage','objects','describe',"$Bucket/tufa-exact/$ExpectedBundle",'--format=json')) | ConvertFrom-Json
if ($bundleInfo.md5_hash -ne $ExpectedBundleMd5) { throw 'Reformed-tool bundle content drift' }

$candidateBundleInfo = (Invoke-Gcloud @('storage','objects','describe',"$Bucket/tufa-exact/$CandidateBundle",'--format=json')) | ConvertFrom-Json
if ($candidateBundleInfo.md5_hash -ne $CandidateBundleMd5) { throw 'Candidate bundle content drift' }
$candidateBundleProbe = Join-Path $PSScriptRoot $CandidateBundle
if (!(Test-Path -LiteralPath $candidateBundleProbe)) {
    throw "Local candidate bundle is required for structural preflight: $candidateBundleProbe"
}
$candidateBundleProbeMd5Hex = Get-FileHashHex $candidateBundleProbe 'MD5'
$candidateBundleProbeMd5Bytes = [byte[]]::new($candidateBundleProbeMd5Hex.Length / 2)
for ($i = 0; $i -lt $candidateBundleProbeMd5Hex.Length; $i += 2) {
    $candidateBundleProbeMd5Bytes[$i / 2] = [Convert]::ToByte($candidateBundleProbeMd5Hex.Substring($i, 2), 16)
}
$candidateBundleProbeMd5 = [Convert]::ToBase64String($candidateBundleProbeMd5Bytes)
if ($candidateBundleProbeMd5 -ne $CandidateBundleMd5) {
    throw 'Local candidate bundle does not match the immutable cloud object'
}
$candidateBundleMembers = @(& tar -tzf $candidateBundleProbe 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw "Candidate bundle could not be inspected:`n$($candidateBundleMembers -join "`n")"
}
if (!($candidateBundleMembers | Where-Object { $_ -match '(^|/)pre_harness_warmup\.py$' })) {
    throw 'Candidate bundle is missing pre_harness_warmup.py'
}
if ($ReflectionV6) {
    $contextWarmupProbeRoot = Join-Path ([IO.Path]::GetTempPath()) ('arc3-context-warmup-' + [IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $contextWarmupProbeRoot | Out-Null
    try {
        & tar -xzf $candidateBundleProbe -C $contextWarmupProbeRoot ./pre_harness_warmup.py 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Context-compaction warmup extraction failed.' }
        $contextWarmupProbe = Join-Path $contextWarmupProbeRoot 'pre_harness_warmup.py'
        if ((Get-FileSha256 $contextWarmupProbe) -ne $ContextWarmupSha) {
            throw 'Context-compaction warmup hash drift.'
        }
    } finally {
        if (Test-Path -LiteralPath $contextWarmupProbeRoot) {
            Remove-Item -LiteralPath $contextWarmupProbeRoot -Recurse -Force
        }
    }
}
if ($exactKaggleSemantics) {
    $exactSourceInfo = (Invoke-Gcloud @('storage','objects','describe',"$Bucket/tufa-exact/$ExactKaggleSourceBundle",'--format=json')) | ConvertFrom-Json
    if ($exactSourceInfo.md5_hash -ne $ExactKaggleSourceBundleMd5) {
        throw 'Audited RTDv12 Kaggle source bundle content drift'
    }
    $exactSourceProbe = Join-Path $PSScriptRoot $ExactKaggleSourceBundle
    if (!(Test-Path -LiteralPath $exactSourceProbe)) {
        throw "Local audited RTDv12 Kaggle source bundle is required: $exactSourceProbe"
    }
    $exactSourceProbeMd5Hex = Get-FileHashHex $exactSourceProbe 'MD5'
    $exactSourceProbeMd5Bytes = [byte[]]::new($exactSourceProbeMd5Hex.Length / 2)
    for ($i = 0; $i -lt $exactSourceProbeMd5Hex.Length; $i += 2) {
        $exactSourceProbeMd5Bytes[$i / 2] = [Convert]::ToByte($exactSourceProbeMd5Hex.Substring($i, 2), 16)
    }
    if ([Convert]::ToBase64String($exactSourceProbeMd5Bytes) -ne $ExactKaggleSourceBundleMd5) {
        throw 'Local audited RTDv12 Kaggle source bundle content drift'
    }
    $exactSourceMembers = @(
        & tar -tzf $exactSourceProbe 2>&1 |
            Where-Object { $_ -and -not $_.EndsWith('/') } |
            ForEach-Object { $_ -replace '^\./', '' } |
            Sort-Object
    )
    if ($LASTEXITCODE -ne 0) { throw 'Audited RTDv12 Kaggle source bundle could not be inspected.' }
    $exactBundleMembers = @(
        $candidateBundleMembers |
            Where-Object { $_ -and -not $_.EndsWith('/') } |
            ForEach-Object { $_ -replace '^\./', '' } |
            Sort-Object
    )
    if (($toolkitMatrixArm -and $ToolkitMatrixMode -ne 'control') -or $visualToolkitArm) {
        $expectedToolkitSha = if ($visualToolkitArm) {
            switch ($VisualToolkitMode) {
                'toolkit' { $MetadataToolkitBundleSha }
                'combined' { $MetadataToolkitReminderBundleSha }
            }
        } else {
            switch ($ToolkitMatrixMode) {
                'toolkit' { $ToolkitBundleSha }
                'reminder' { $ReminderBundleSha }
                'combined' { $ToolkitReminderBundleSha }
            }
        }
        $expectedToolkitMembers = if ($visualToolkitArm) {
            if ($VisualToolkitMode -eq 'combined') { 90 } else { 88 }
        } else {
            switch ($ToolkitMatrixMode) {
                'toolkit' { 88 }
                'reminder' { 80 }
                'combined' { 90 }
            }
        }
        if ((Get-FileSha256 $candidateBundleProbe) -ne $expectedToolkitSha) {
            throw 'Toolkit matrix local candidate SHA256 drift.'
        }
        if ($exactBundleMembers.Count -ne $expectedToolkitMembers) {
            throw "Toolkit matrix archive member-count drift; expected $expectedToolkitMembers."
        }
        $requiredToolkitMembers = @('pre_harness_warmup.py')
        if ($toolkitEnabledForRun) {
            $requiredToolkitMembers += @(
                'src/ARC3-Inference/inference/agent/cpu_vision.py',
                'src/ARC3-Inference/inference/agent/persistent_helpers.py',
                'src/ARC3-Inference/inference/agent/vision_tools.py'
            )
        }
        if ($reminderEnabledForRun) {
            $requiredToolkitMembers += 'src/ARC3-Inference/inference/agent/budget_reminder.py'
        }
        foreach ($requiredToolkitMember in $requiredToolkitMembers) {
            if ($requiredToolkitMember -notin $exactBundleMembers) {
                throw "Toolkit matrix archive is missing pinned member: $requiredToolkitMember"
            }
        }
    } else {
        $memberDelta = @(Compare-Object $exactSourceMembers $exactBundleMembers)
        if ($memberDelta.Count -ne 1 -or
            $memberDelta[0].SideIndicator -ne '=>' -or
            $memberDelta[0].InputObject -ne 'pre_harness_warmup.py') {
            throw "GCP-ready exact-Kaggle arm must preserve champion membership plus pre_harness_warmup.py: $($memberDelta | ConvertTo-Json -Compress)"
        }
    }
    $warmupProbeRoot = Join-Path ([IO.Path]::GetTempPath()) ('arc3-warmup-' + [IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $warmupProbeRoot | Out-Null
    try {
        & tar -xzf $candidateBundleProbe -C $warmupProbeRoot ./pre_harness_warmup.py 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Pinned warmup extraction failed.' }
        $warmupProbe = Join-Path $warmupProbeRoot 'pre_harness_warmup.py'
        if ((Get-FileSha256 $warmupProbe) -ne $ExactKaggleWarmupSha) {
            throw 'Pinned Kaggle warmup hash drift.'
        }
    } finally {
        if (Test-Path -LiteralPath $warmupProbeRoot) {
            Remove-Item -LiteralPath $warmupProbeRoot -Recurse -Force
        }
    }
}
$candidateRunnerInfo = (Invoke-Gcloud @('storage','objects','describe',$CandidateRunner,'--format=json')) | ConvertFrom-Json
if ($ChampionReflectionV3 -or $ChampionRefinement -or $ChampionLongRun) {
    $expectedRunnerSha = if ($ChampionReflectionV3) { $ChampionReflectionV3RunnerSha } elseif ($ChampionRefinement) { $ChampionRefinementRunnerSha } else { $ChampionLongRunRunnerSha }
    $expectedRunnerMd5 = if ($ChampionReflectionV3) { $ChampionReflectionV3RunnerMd5 } elseif ($ChampionRefinement) { $ChampionRefinementRunnerMd5 } else { $ChampionLongRunRunnerMd5 }
    if ($candidateRunnerInfo.md5_hash -ne $expectedRunnerMd5) {
        throw 'Cloud champion-derived runner content drift.'
    }
    $runnerLeaf = ($CandidateRunner -split '/')[-1]
    $runnerProbe = if ($ChampionLongRun) {
        Join-Path $PSScriptRoot 'v12-run-kaggle11p44-long6h.py'
    } else {
        Join-Path $PSScriptRoot $runnerLeaf
    }
    if (!(Test-Path -LiteralPath $runnerProbe)) {
        throw "Local champion-derived runner is required for hash preflight: $runnerProbe"
    }
    if ((Get-FileSha256 $runnerProbe) -ne $expectedRunnerSha) {
        throw 'Champion-derived runner content drift.'
    }
}
[void](Invoke-Gcloud @('storage','objects','describe',$PlePatchObject,'--format=json'))

$converterSha = Get-FileSha256 $ConverterPath
$converterObject = "$Bucket/code/flash-next/convert-radix-ple-$converterSha.py"
Invoke-Gcloud @('storage','cp',$ConverterPath,$converterObject) | Out-Null
$scoreObserverSha = Get-FileSha256 $ScoreObserverPath
$scoreObserverObject = "$Bucket/code/observer/arc3-minute-score-$scoreObserverSha.py"
Invoke-Gcloud @('storage','cp',$ScoreObserverPath,$scoreObserverObject) | Out-Null
$colocatedHudInstallerSha = if ($ColocatedHudCpu) { Get-FileSha256 $ColocatedHudInstallerPath } else { $null }
$colocatedHudInstallerObject = if ($ColocatedHudCpu) {
    "$Bucket/code/hud/start-colocated-deepseek-coder-v2-lite-$colocatedHudInstallerSha.sh"
} else { $null }
if ($ColocatedHudCpu) {
    Invoke-Gcloud @('storage','cp',$ColocatedHudInstallerPath,$colocatedHudInstallerObject) | Out-Null
}

$serverBlock = @'
export PATH="$HOME/.local/bin:$PATH"
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  test -x /root/.local/bin/uv
  test -x /opt/arc3/pysrv/bin/python
  echo "golden runtime: reusing uv and curator/server client environment"
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
  uv venv --python 3.12.12 /opt/arc3/pysrv
fi

# Flash-Next uses the experimental PLE CPU-offload path packaged in this pinned
# vLLM image.  The PLE table is the only model component placed in host RAM.
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  command -v docker >/dev/null
  command -v nvidia-ctk >/dev/null
  echo "golden runtime: reusing Docker and NVIDIA container toolkit"
else
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io
  if ! command -v nvidia-ctk >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nvidia-container-toolkit
  fi
  nvidia-ctk runtime configure --runtime=docker
fi
systemctl enable --now docker

MODEL_DIR=/opt/arc3/flashnext-model
CONVERTER_OBJECT=$(meta arc3-converter-object)
CONTAINER_IMAGE='vllm/vllm-openai@sha256:fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8'
mkdir -p "$MODEL_DIR" /opt/arc3/vllm-cache
gcloud storage cp "$CONVERTER_OBJECT" /opt/arc3/convert_radix_ple.py

docker pull "$CONTAINER_IMAGE"
docker run --rm --gpus all --entrypoint nvidia-smi "$CONTAINER_IMAGE"
CONTAINER_PYTHON=$(docker run --rm --entrypoint /bin/sh "$CONTAINER_IMAGE" -lc '
  entry=$(command -v vllm)
  first=$(head -n 1 "$entry")
  case "$first" in
    "#!"*)
      candidate=${first#\#!}
      set -- $candidate
      if [ "$1" = /usr/bin/env ] && [ -n "${2:-}" ]; then
        command -v "$2" && exit 0
      fi
      [ -x "$1" ] && { printf "%s\n" "$1"; exit 0; }
      ;;
  esac
  for candidate in /opt/venv/bin/python /opt/venv/bin/python3 /opt/uv/python/*/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    [ -x "$candidate" ] && { printf "%s\n" "$candidate"; exit 0; }
  done
  exit 1
')
case "$CONTAINER_PYTHON" in
  /*) ;;
  *) echo "Could not resolve container Python: $CONTAINER_PYTHON"; exit 1 ;;
esac
echo "container python: $CONTAINER_PYTHON"

# Restore the immutable, checksummed GCS mirror.  The mirror is populated from
# the exact successful Flash-Next revision and gated by DONE + MANIFEST.
MODEL_GCS_PREFIX='gs://cellens-ai-artifacts/arc3-duck/models/qwen3.8-flash-next-nvfp4-radixark/7b719225242aacd3dbd3f9407468c2ee9a9d2594'
gcloud storage cp "$MODEL_GCS_PREFIX/_mirror/DONE" /opt/arc3/model-mirror-done.json
gcloud storage cp "$MODEL_GCS_PREFIX/_mirror/MANIFEST.json" /opt/arc3/model-mirror-manifest.json
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  printf 'golden runtime image %s: immutable model payload reused\n' "$GOLDEN_RUNTIME_IMAGE" | \
    tee /opt/arc3/model-download.log
else
  gcloud storage rsync --recursive "$MODEL_GCS_PREFIX" "$MODEL_DIR" \
    2>&1 | tee /opt/arc3/model-download.log
fi

docker run --rm -i --entrypoint "$CONTAINER_PYTHON" \
  -e ARC3_GOLDEN_RUNTIME_IMAGE="$GOLDEN_RUNTIME_IMAGE" \
  -v "$MODEL_DIR:/model:ro" \
  -v /opt/arc3/model-mirror-manifest.json:/manifest.json:ro \
  "$CONTAINER_IMAGE" - <<'PYVERIFY'
import hashlib
import json
import os
from pathlib import Path

model_id = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
revision = "7b719225242aacd3dbd3f9407468c2ee9a9d2594"
manifest = json.loads(Path("/manifest.json").read_text(encoding="utf-8"))
assert manifest["model_id"] == model_id
assert manifest["revision"] == revision
assert manifest["resolved_revision"] == revision
assert manifest["file_count"] == len(manifest["files"])
assert manifest["total_bytes"] == sum(row["size"] for row in manifest["files"])
for row in manifest["files"]:
    path = Path("/model") / row["path"]
    assert path.is_file(), f"missing mirrored model file: {row['path']}"
    assert path.stat().st_size == row["size"], f"size drift: {row['path']}"
    if not os.environ.get("ARC3_GOLDEN_RUNTIME_IMAGE"):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(16 * 1024 * 1024), b""):
                digest.update(block)
        assert digest.hexdigest() == row["sha256"], f"sha256 drift: {row['path']}"
print(
    "golden image size-manifest attestation passed"
    if os.environ.get("ARC3_GOLDEN_RUNTIME_IMAGE")
    else "full model SHA-256 verification passed",
    flush=True,
)
PYVERIFY

docker run --rm -i --entrypoint "$CONTAINER_PYTHON" \
  -v "$MODEL_DIR:/model" "$CONTAINER_IMAGE" - <<'PYINFO'
import json
with open("/model/download-info.json", "w", encoding="utf-8") as fh:
    json.dump({
        "model_id": "RadixArk/Qwen3.8-Flash-Next-NVFP4",
        "revision": "7b719225242aacd3dbd3f9407468c2ee9a9d2594",
        "source": "gs://cellens-ai-artifacts/arc3-duck/models/qwen3.8-flash-next-nvfp4-radixark/7b719225242aacd3dbd3f9407468c2ee9a9d2594/",
        "verified_from_manifest": True,
    }, fh, indent=2)
PYINFO

# RadixArk stores the 51.2B-entry PLE table as FP8 plus a scalar.  The vLLM
# offload worker consumes BF16, so dequantize only that lookup table.  Routed
# experts remain byte-identical NVFP4.
docker run --rm --entrypoint "$CONTAINER_PYTHON" \
  -v "$MODEL_DIR:/model" \
  -v /opt/arc3/convert_radix_ple.py:/converter.py:ro \
  "$CONTAINER_IMAGE" /converter.py /model --delete-fp8 \
  2>&1 | tee /opt/arc3/ple-conversion.log

/opt/arc3/pysrv/bin/python - <<'PYINFO'
import json
from pathlib import Path

root = Path("/opt/arc3/flashnext-model")
download = json.loads((root / "download-info.json").read_text())
conversion = json.loads((root / "ple-bf16-conversion.json").read_text())
info = {
    **download,
    "quantization": "RadixArk NVFP4 routed experts; PLE FP8 deterministically dequantized to BF16 for CPU offload",
    "ple_conversion": conversion,
    "mtp_enabled": False,
    "requested_server_sequences": 22,
    "context_length": 32768,
}
Path("/opt/arc3/model-info.json").write_text(json.dumps(info, indent=2) + "\n")
PYINFO

start_server() {
  local kv_dtype="$1"
  docker rm -f flashnext >/dev/null 2>&1 || true
  pkill -f "docker logs -f flashnext" >/dev/null 2>&1 || true
  : > /opt/arc3/vllm.log
  # Gloo needs a null-terminated hostname. GCE FQDNs can be exactly 64 bytes,
  # which makes ProcessGroupGloo fail with ENAMETOOLONG before model loading.
  docker run -d --name flashnext --hostname arc3-vllm --gpus all --ipc=host --network=host \
    --ulimit memlock=-1 --cap-add=SYS_PTRACE \
    -e VLLM_PLE_CPU_OFFLOAD=1 \
    -e VLLM_PLE_OFFLOAD_READY_TIMEOUT=1800 \
    -e TORCH_CUDA_ARCH_LIST=12.0f \
    -e PYTORCH_ALLOC_CONF=expandable_segments:True \
    -e HF_HUB_OFFLINE=1 \
    -e VLLM_NO_USAGE_STATS=1 \
    -v "$MODEL_DIR:/model:ro" \
    -v /opt/arc3/vllm-cache:/root/.cache \
    "$CONTAINER_IMAGE" \
    --model /model --served-model-name "$SERVED_MODEL_NAME" \
    --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
    --distributed-executor-backend mp \
    --gpu-memory-utilization 0.96 \
    --max-model-len 32768 --max-num-seqs 22 --max-num-batched-tokens 6144 \
    --kv-cache-dtype "$kv_dtype" \
    --enable-prefix-caching --enable-prompt-tokens-details --no-enable-flashinfer-autotune \
    --enable-auto-tool-choice --tool-call-parser qwen3_xml \
    --generation-config vllm \
    --default-chat-template-kwargs '{"preserve_thinking": true}' \
    --reasoning-parser qwen3
  nohup docker logs -f flashnext > /opt/arc3/vllm.log 2>&1 &
}

wait_server() {
  for _ in $(seq 1 180); do
    curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && return 0
    docker inspect -f '{{.State.Running}}' flashnext 2>/dev/null | grep -qx true || return 1
    sleep 10
  done
  return 1
}

# Prefer FP8 KV to make 22 live lanes comfortable.  If this experimental hybrid
# cache path is rejected, fall back to BF16/auto while keeping all other settings.
KV_DTYPE_USED=fp8
start_server "$KV_DTYPE_USED"
if ! wait_server; then
  cp /opt/arc3/vllm.log /opt/arc3/vllm-fp8-failed.log
  KV_DTYPE_USED=auto
  start_server "$KV_DTYPE_USED"
fi
if ! wait_server; then
  echo "Flash-Next vLLM failed for FP8 and auto KV" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  sync_all
  exit 1
fi
echo "$KV_DTYPE_USED" > /opt/arc3/kv-dtype-used.txt

docker exec -i flashnext "$CONTAINER_PYTHON" - <<'PYVERS' > /opt/arc3/serving-environment.txt
import platform
import torch
import transformers
import vllm
print("python", platform.python_version())
print("vllm", vllm.__version__)
print("torch", torch.__version__)
print("transformers", transformers.__version__)
print("cuda", torch.version.cuda)
PYVERS
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu \
  --format=csv,noheader > /opt/arc3/gpu-after-load.csv
free -h > /opt/arc3/ram-after-load.txt

# Verify ordinary text, vision, and 22 simultaneous long-prefix requests before
# starting gameplay.  Thinking is disabled only for this capacity smoke test.
export KV_DTYPE_USED
run_smoke() {
/opt/arc3/pysrv/bin/python - <<'PYSMOKE'
import base64
import concurrent.futures
import json
import os
import time
import urllib.request

URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "RadixArk/Qwen3.8-Flash-Next-NVFP4"

def call(messages, max_tokens=64, timeout=900):
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": True},
    }
    request = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("choices"):
        raise RuntimeError(result)
    choice = result["choices"][0]
    message = choice.get("message") or {}
    material = " ".join([
        str(choice.get("text") or ""),
        str(message.get("content") or ""),
        str(message.get("reasoning_content") or ""),
    ])
    if not material.strip() or "nan" in material.lower():
        raise RuntimeError({"invalid_generated_material": material, "response": result})
    return {"seconds": time.monotonic() - started, "response": result}

text = call([{"role": "user", "content": "Return exactly READY."}], max_tokens=32)

png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
vision = call([{"role": "user", "content": [
    {"type": "text", "text": "Describe this one-pixel image in one word."},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png}},
]}], max_tokens=32)

filler = "x " * 9000
def capacity_call(index):
    return call([{"role": "user", "content": (
        "This is capacity probe %d. Ignore the filler and return only OK. " % index
    ) + filler}], max_tokens=16)

capacity_started = time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=22) as pool:
    capacity = list(pool.map(capacity_call, range(22)))
capacity_seconds = time.monotonic() - capacity_started

summary = {
    "model": MODEL,
    "kv_dtype": os.environ["KV_DTYPE_USED"],
    "mtp_enabled": False,
    "max_num_seqs": 22,
    "text": text,
    "vision": vision,
    "capacity": {
        "requests": len(capacity),
        "wall_seconds": capacity_seconds,
        "min_seconds": min(x["seconds"] for x in capacity),
        "max_seconds": max(x["seconds"] for x in capacity),
        "mean_seconds": sum(x["seconds"] for x in capacity) / len(capacity),
        "all_returned": all(x["response"].get("choices") for x in capacity),
    },
}
with open("/opt/arc3/model-smoke.json", "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)
print(json.dumps(summary["capacity"], indent=2), flush=True)
PYSMOKE
}

if ! run_smoke; then
  if [ "$KV_DTYPE_USED" = fp8 ]; then
    cp /opt/arc3/vllm.log /opt/arc3/vllm-fp8-failed.log
    KV_DTYPE_USED=auto
    export KV_DTYPE_USED
    start_server "$KV_DTYPE_USED"
    if ! wait_server || ! run_smoke; then
      echo "Flash-Next capacity smoke failed for FP8 and auto KV" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
      sync_all
      exit 1
    fi
    echo "$KV_DTYPE_USED" > /opt/arc3/kv-dtype-used.txt
  else
    echo "Flash-Next capacity smoke failed with auto KV" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
    sync_all
    exit 1
  fi
fi

# Capture the final serving process (including any guarded KV fallback).
docker exec -i flashnext "$CONTAINER_PYTHON" - <<'PYVERS' > /opt/arc3/serving-environment.txt
import platform
import torch
import transformers
import vllm
print("python", platform.python_version())
print("vllm", vllm.__version__)
print("torch", torch.__version__)
print("transformers", transformers.__version__)
print("cuda", torch.version.cuda)
PYVERS
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu \
  --format=csv,noheader > /opt/arc3/gpu-after-load.csv
free -h > /opt/arc3/ram-after-load.txt
sync_all
'@

$startup = $sourceStartup.Replace("`r`n", "`n").Replace("`r", "`n")
$startupNewline = "`n"
if ($GoldenRuntimeImage) {
    $startupLogAnchor = 'exec > >(tee -a /var/log/arc3-qwen38-startup.log) 2>&1'
    if ([regex]::Matches($startup, [regex]::Escape($startupLogAnchor)).Count -ne 1) {
        throw 'Golden runtime startup-log anchor drift'
    }
    $startup = $startup.Replace($startupLogAnchor, 'exec > >(tee /var/log/arc3-qwen38-startup.log) 2>&1')
}
$runtimeWorkspaceAnchor = 'mkdir -p /opt/arc3/work /opt/arc3/bundle /opt/arc3/qwen38-model'
if ([regex]::Matches($startup, [regex]::Escape($runtimeWorkspaceAnchor)).Count -ne 1) {
    throw 'Inherited runtime workspace anchor drift'
}
$runtimeWorkspaceBlock = @'
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  # The image deliberately retains only reusable model, package, container, and
  # compilation caches. Never inherit gameplay or arm-specific telemetry.
  rm -rf /opt/arc3/work /opt/arc3/bundle /opt/arc3/curator \
    /opt/arc3/reviewed-themes /opt/arc3/engwheels
  rm -f /opt/arc3/v12.log /opt/arc3/model-smoke.json /opt/arc3/model-info.json \
    /opt/arc3/serving-environment.txt /opt/arc3/gpu-after-load.csv \
    /opt/arc3/ram-after-load.txt /opt/arc3/kv-dtype-used.txt \
    /opt/arc3/replay-selftest.log /opt/arc3/pre-harness-warmup.json \
    /opt/arc3/pre-harness-warmup.log /opt/arc3/model-download.log \
    /opt/arc3/vllm.log /opt/arc3/vllm-fp8-failed.log \
    /opt/arc3/vllm-start-attempt1.log
  echo "golden runtime: cleared prior run state while preserving immutable caches"
fi
mkdir -p /opt/arc3/work /opt/arc3/bundle /opt/arc3/qwen38-model
'@
$startup = $startup.Replace($runtimeWorkspaceAnchor, $runtimeWorkspaceBlock)
$aptUpdateAnchor = 'apt-get update -qq'
if ([regex]::Matches($startup, [regex]::Escape($aptUpdateAnchor)).Count -ne 1) {
    throw 'Inherited apt update anchor drift'
}
$startup = $startup.Replace(
    $aptUpdateAnchor,
    ('if [ -z "$GOLDEN_RUNTIME_IMAGE" ]; then' + $startupNewline +
     '  apt-get update -qq' + $startupNewline +
     'else' + $startupNewline +
     '  echo "golden runtime: skipping apt index refresh"' + $startupNewline +
     'fi')
)
$bootstrapAptAnchor = 'DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ffmpeg ninja-build'
if ([regex]::Matches($startup, [regex]::Escape($bootstrapAptAnchor)).Count -ne 1) {
    throw 'Inherited bootstrap apt anchor drift'
}
$bootstrapAptBlock = @'
# Prefer the reusable GCS bootstrap cache before apt computes its download queue.
# gcloud validates object checksums and apt independently validates each package
# against the signed Ubuntu package metadata before installation.
BOOTSTRAP_APT_PREFIX="$BUCKET/bootstrap-cache/ubuntu2404-ab4"
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  command -v ffmpeg >/dev/null
  command -v ninja >/dev/null
  command -v gcc >/dev/null
  echo "golden runtime: reusing OS build and media packages"
else
  mkdir -p /var/cache/apt/archives
  if gcloud storage ls "$BOOTSTRAP_APT_PREFIX/*.deb" >/dev/null 2>&1; then
    gcloud storage cp "$BOOTSTRAP_APT_PREFIX/*.deb" /var/cache/apt/archives/
  fi
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ffmpeg ninja-build
fi
'@
$startup = $startup.Replace($bootstrapAptAnchor, $bootstrapAptBlock)
if ($ResumeCompletedGames) {
    $attemptGuard = @'
if [ "$ATTEMPTS" -gt 1 ]; then
  echo "preemption/recreation detected; duplicate gameplay forbidden" | gcloud storage cp - \
    "$BUCKET/$RUN_ID/FAILED"
  exit 1
fi
'@
    if ([regex]::Matches($startup, [regex]::Escape($attemptGuard)).Count -ne 1) {
        throw 'Single-attempt guard drift'
    }
    $resumeGuard = @'
export ARC3_RESUME_ATTEMPT="$ATTEMPTS"
if [ "$ATTEMPTS" -gt 4 ]; then
  echo "resume attempt ceiling exceeded: $ATTEMPTS" | gcloud storage cp - \
    "$BUCKET/$RUN_ID/FAILED"
  gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true
  exit 1
fi
if [ "$ATTEMPTS" -gt 1 ]; then
  mkdir -p /opt/arc3/work /opt/arc3/curator
  gcloud storage rsync -r "$BUCKET/$RUN_ID/runs" /opt/arc3/work || true
  gcloud storage rsync -r "$BUCKET/$RUN_ID/curator" /opt/arc3/curator || true
  echo "resume restore complete: attempt=$ATTEMPTS"
fi
'@
    $startup = $startup.Replace($attemptGuard, $resumeGuard)

    $teardownResumeAnchor = '  trap - EXIT TERM INT'
    if ([regex]::Matches($startup, [regex]::Escape($teardownResumeAnchor)).Count -ne 1) {
        throw 'Teardown resume anchor drift'
    }
    $startup = $startup.Replace(
        $teardownResumeAnchor,
        ($teardownResumeAnchor + $startupNewline +
         '  if ! gcloud storage ls "$BUCKET/$RUN_ID/DONE" >/dev/null 2>&1; then' + $startupNewline +
         '    sync_all' + $startupNewline +
         '    echo "resume-enabled nonterminal exit; leaving MIG at size 1"' + $startupNewline +
         '    return' + $startupNewline +
         '  fi')
    )
}
if ($DisableCurator) {
    $modeCaseAnchor = '  cpu_reviewed_themes|gpu_theme_curator|gpu_world_model_curator) ;;'
    if ([regex]::Matches($startup, [regex]::Escape($modeCaseAnchor)).Count -ne 1) {
        throw 'Influence-mode case anchor drift'
    }
    $startup = $startup.Replace(
        $modeCaseAnchor,
        '  none|cpu_reviewed_themes|gpu_theme_curator|gpu_world_model_curator) ;;'
    )
    $curatorBranchAnchor = 'if [ "$INFLUENCE_MODE" = cpu_reviewed_themes ]; then'
    if ([regex]::Matches($startup, [regex]::Escape($curatorBranchAnchor)).Count -ne 1) {
        throw 'Curator bootstrap branch anchor drift'
    }
    $startup = $startup.Replace(
        $curatorBranchAnchor,
        ('if [ "$INFLUENCE_MODE" = none ]; then' + $startupNewline +
         '  unset ARC3_COMMON_THEMES_PATH ARC3_COMMON_THEMES_INJECTION_LOG' + $startupNewline +
         'elif [ "$INFLUENCE_MODE" = cpu_reviewed_themes ]; then')
    )
}
$bundleExtractAnchor = 'tar xzf /tmp/bundle.tgz -C /opt/arc3/bundle'
if ([regex]::Matches($startup, [regex]::Escape($bundleExtractAnchor)).Count -ne 1) { throw 'Bundle extraction anchor drift' }
$runtimeOverlayInstall = if ($exactKaggleSemantics) { @"
$bundleExtractAnchor
# Activate only the immutable gameplay package carried by the audited bundle.
# Keep the pinned deployment project's Makefile, lockfile, and deployment-only
# config (including configs/tufa0.json), which are not part of the Kaggle bundle.
cp -a /opt/arc3/bundle/src/ARC3-Inference/inference/. /opt/arc3/ARC3-Inference/inference/
find /opt/arc3/ARC3-Inference/inference -type f -name '*.pyc' -delete
"@.TrimEnd("`r", "`n")
} else { @"
$bundleExtractAnchor
echo '$RuntimeOverlayPromptsSha  /opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/prompts.py' | sha256sum -c -
echo '$RuntimeOverlaySandboxSha  /opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/python_tool_sandbox.py' | sha256sum -c -
echo '$RuntimeOverlayToolAgentSha  /opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/tool_agent.py' | sha256sum -c -
install -m 0644 /opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/prompts.py /opt/arc3/ARC3-Inference/inference/agent/prompts.py
install -m 0644 /opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/python_tool_sandbox.py /opt/arc3/ARC3-Inference/inference/agent/python_tool_sandbox.py
install -m 0644 /opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/tool_agent.py /opt/arc3/ARC3-Inference/inference/agent/tool_agent.py
echo '$RuntimeOverlayPromptsSha  /opt/arc3/ARC3-Inference/inference/agent/prompts.py' | sha256sum -c -
echo '$RuntimeOverlaySandboxSha  /opt/arc3/ARC3-Inference/inference/agent/python_tool_sandbox.py' | sha256sum -c -
echo '$RuntimeOverlayToolAgentSha  /opt/arc3/ARC3-Inference/inference/agent/tool_agent.py' | sha256sum -c -
"@.TrimEnd("`r", "`n") }
$startup = $startup.Replace($bundleExtractAnchor, $runtimeOverlayInstall)
$curatorMetaAnchor = 'CURATOR_OBJECT=$(meta arc3-curator-object)'
if ([regex]::Matches($startup, [regex]::Escape($curatorMetaAnchor)).Count -ne 1) { throw 'Curator metadata anchor drift' }
$startup = $startup.Replace(
    $curatorMetaAnchor,
    $curatorMetaAnchor + $startupNewline +
    'SCORE_OBSERVER_OBJECT=$(meta arc3-score-observer-object)' + $startupNewline +
    'GOLDEN_RUNTIME_IMAGE=$(meta arc3-golden-runtime-image 2>/dev/null || true)'
)
if ($ColocatedHudCpu) {
    $startup = $startup.Replace(
        'SCORE_OBSERVER_OBJECT=$(meta arc3-score-observer-object)',
        ('SCORE_OBSERVER_OBJECT=$(meta arc3-score-observer-object)' + $startupNewline + 'HUD_INSTALLER_OBJECT=$(meta arc3-hud-installer-object)')
    )
}
$runnerCopyAnchor = 'gcloud storage cp "$RUNNER_OBJECT" /opt/arc3/v12_run.py'
if ([regex]::Matches($startup, [regex]::Escape($runnerCopyAnchor)).Count -ne 1) { throw 'Runner copy anchor drift' }
$startup = $startup.Replace(
    $runnerCopyAnchor,
    $runnerCopyAnchor + $startupNewline + 'gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py'
)
$runnerLimitPatch = @'
python3 - <<'PYRUNLIMIT'
from pathlib import Path

path = Path('/opt/arc3/v12_run.py')
text = path.read_text(encoding='utf-8')
old = 'soft_end = datetime.now() + timedelta(hours=11, minutes=20)'
new = 'soft_end = datetime.now() + timedelta(minutes=__RUN_LIMIT_MINUTES__)'
if text.count(old) != 1:
    raise RuntimeError('runner soft-deadline anchor drift')
path.write_text(text.replace(old, new), encoding='utf-8')
PYRUNLIMIT
grep -F 'soft_end = datetime.now() + timedelta(minutes=__RUN_LIMIT_MINUTES__)' /opt/arc3/v12_run.py
'@.Replace('__RUN_LIMIT_MINUTES__', [string]$MaxRunRuntimeMinutes)
$startup = $startup.Replace(
    'gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py',
    'gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py' + $startupNewline + $runnerLimitPatch
)
if ($ColocatedHudCpu) {
    $startup = $startup.Replace(
        'gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py',
        ('gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py' + $startupNewline +
         'gcloud storage cp "$HUD_INSTALLER_OBJECT" /opt/arc3/start_colocated_hud_server.sh' + $startupNewline +
         "echo '$colocatedHudInstallerSha  /opt/arc3/start_colocated_hud_server.sh' | sha256sum -c -" + $startupNewline +
         'chmod 0755 /opt/arc3/start_colocated_hud_server.sh')
    )
}
$teardownObserverAnchor = if ($ResumeCompletedGames) {
    "  fi`n  sync_all"
} else {
    "  trap - EXIT TERM INT`n  sync_all"
}
if ([regex]::Matches($startup, [regex]::Escape($teardownObserverAnchor)).Count -ne 1) { throw 'Teardown observer anchor drift' }
$teardownObserverReplacement = if ($ResumeCompletedGames) {
    "  fi`n  pkill -TERM -f arc3_minute_score_observer.py 2>/dev/null || true`n  sleep 1`n  sync_all"
} else {
    "  trap - EXIT TERM INT`n  pkill -TERM -f arc3_minute_score_observer.py 2>/dev/null || true`n  sleep 1`n  sync_all"
}
$startup = $startup.Replace($teardownObserverAnchor, $teardownObserverReplacement)
$runnerStartAnchor = @'
set +e
./.venv/bin/python /opt/arc3/v12_run.py 2>&1 | tee /opt/arc3/v12.log
RUN_STATUS=${PIPESTATUS[0]}
set -e
sync_all
'@
if ([regex]::Matches($startup, [regex]::Escape($runnerStartAnchor)).Count -ne 1) { throw 'Runner start anchor drift' }
$runnerWithObserver = @'
mkdir -p /opt/arc3/work/score-observer
nice -n 19 ionice -c3 /opt/arc3/pysrv/bin/python /opt/arc3/arc3_minute_score_observer.py \
  --artifacts-dir /opt/arc3/work/artifacts \
  --output-dir /opt/arc3/work/score-observer \
  --interval-seconds 60 \
  > /opt/arc3/work/score-observer/observer.log 2>&1 &
SCORE_OBSERVER_PID=$!
echo "$SCORE_OBSERVER_PID" > /opt/arc3/work/score-observer/observer.pid

set +e
./.venv/bin/python /opt/arc3/v12_run.py 2>&1 | tee /opt/arc3/v12.log
RUN_STATUS=${PIPESTATUS[0]}
set -e
kill -TERM "$SCORE_OBSERVER_PID" 2>/dev/null || true
wait "$SCORE_OBSERVER_PID" 2>/dev/null || true
sync_all
'@
if ($ServingProfile -eq 'best-serving') {
    $warmupCommand = @'
./.venv/bin/python /opt/arc3/bundle/pre_harness_warmup.py \
  --output /opt/arc3/pre-harness-warmup.json \
  2>&1 | tee /opt/arc3/pre-harness-warmup.log

'@
    $runnerWithObserver = $warmupCommand + $runnerWithObserver
}
if ($ColocatedHudCpu) {
    $hudStartCommand = @"
HUD_CPUSET='$ColocatedHudCpuSet' HUD_PARALLEL=2 HUD_THREADS=12 HUD_MEMORY_LIMIT=20g \
  /opt/arc3/start_colocated_hud_server.sh
curl -sf -m 5 http://127.0.0.1:8080/health >/dev/null

"@
    $runnerWithObserver = $hudStartCommand + $runnerWithObserver
}
$startup = $startup.Replace($runnerStartAnchor, $runnerWithObserver)
if ($VerifiedQueue) {
    $selftestAnchor = 'mkdir -p /opt/arc3/work/score-observer'
    if ([regex]::Matches($startup, [regex]::Escape($selftestAnchor)).Count -ne 1) {
        throw 'Verified-queue self-test anchor drift'
    }
    $selftestBlock = @'
./.venv/bin/python /opt/arc3/bundle/test_verified_action_queue.py \
  2>&1 | tee /opt/arc3/verified-queue-selftest.log
mkdir -p /opt/arc3/work/score-observer
'@
    if ($VerifiedHudV3) {
        $selftestBlock = $selftestBlock.Replace(
            'mkdir -p /opt/arc3/work/score-observer',
            ('./.venv/bin/python -m py_compile /opt/arc3/bundle/src/ARC3-Inference/inference/agent/hud_analyst.py' + $startupNewline + 'mkdir -p /opt/arc3/work/score-observer')
        )
    }
    if ($HypothesisLab) {
        $selftestBlock = $selftestBlock.Replace(
            'mkdir -p /opt/arc3/work/score-observer',
            ('./.venv/bin/python /opt/arc3/bundle/test_hypothesis_lab.py 2>&1 | tee /opt/arc3/hypothesis-lab-selftest.log' + $startupNewline + './.venv/bin/python /opt/arc3/bundle/test_hypothesis_lab_tool_agent.py 2>&1 | tee -a /opt/arc3/hypothesis-lab-selftest.log' + $startupNewline + 'mkdir -p /opt/arc3/work/score-observer')
        )
    }
    $startup = $startup.Replace($selftestAnchor, $selftestBlock)
}
$replaySelftestAnchor = 'mkdir -p /opt/arc3/work/score-observer'
if ([regex]::Matches($startup, [regex]::Escape($replaySelftestAnchor)).Count -ne 1) {
    throw 'Replay self-test anchor drift'
}
$replaySelftestBlock = if ($ChampionReflectionV3) { @'
./.venv/bin/python - <<'PYCHAMPIONREFLECTION' 2>&1 | tee /opt/arc3/replay-selftest.log
import inspect
import os
from pathlib import Path

from inference.agent import tool_agent

assert "ARC3_REPLAY_ENABLED" not in os.environ
assert "ARC3_REPLAY_ARM" not in os.environ
assert "ARC3_REPLAY_TRIGGER_REMINDER" not in os.environ
assert os.environ["ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED"] == "1"
assert os.environ.get("ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION", "3") == "3"
assert os.environ["ARC3_ACTION_CAP"] == "14"
assert os.environ["ARC3_POST_LEVEL_UNCAPPED_TURNS"] == "0"
assert tool_agent._PERSISTENT_HISTORY_ASSISTANT_TURNS == 30
reflection, error = tool_agent._validated_level_reflection(
    '{"winning_world_model":"Match roles to reveal the exit.",'
    '"decisive_evidence":"The engine confirmed the level transition.",'
    '"minimal_recipe":"Apply the verified role rule once.",'
    '"redundant_actions":"No redundant action is required.",'
    '"next_level_rule":"Transfer the role rule and verify."}'
)
assert not error, error
assert "Winning world model:" in reflection
source = inspect.getsource(tool_agent.ToolAgent._generate_same_context_level_reflection)
assert "max_output_tokens_override=448" in source
assert "thinking_override=False" in source
runtime_tool_agent = Path(tool_agent.__file__).resolve()
bundle_tool_agent = Path("/opt/arc3/bundle/src/ARC3-Inference/inference/agent/tool_agent.py")
assert runtime_tool_agent == Path("/opt/arc3/ARC3-Inference/inference/agent/tool_agent.py").resolve()
assert runtime_tool_agent.read_bytes() == bundle_tool_agent.read_bytes()
print("exact Kaggle RTDv12 winner + guarded Reflection V3 self-test: ok")
PYCHAMPIONREFLECTION
mkdir -p /opt/arc3/work/score-observer
'@ } elseif ($exactKaggleSemantics) { @'
./.venv/bin/python - <<'PYCHAMPION' 2>&1 | tee /opt/arc3/replay-selftest.log
import os
from pathlib import Path

from inference.agent import tool_agent

assert "ARC3_REPLAY_ENABLED" not in os.environ
assert "ARC3_REPLAY_ARM" not in os.environ
assert "ARC3_REPLAY_TRIGGER_REMINDER" not in os.environ
assert "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED" not in os.environ
assert os.environ["ARC3_ACTION_CAP"] == "14"
assert os.environ["ARC3_POST_LEVEL_UNCAPPED_TURNS"] == "0"
assert tool_agent._PERSISTENT_HISTORY_ASSISTANT_TURNS == 30
agent = tool_agent.ToolAgent()
assert "Lossless replay memory:" not in agent._system_prompt
assert "replay.repeated_states()" not in tool_agent._PYTHON_TOOL_DESCRIPTION
assert "Winning world model:" not in agent._system_prompt
runtime_tool_agent = Path(tool_agent.__file__).resolve()
bundle_tool_agent = Path("/opt/arc3/bundle/src/ARC3-Inference/inference/agent/tool_agent.py")
assert runtime_tool_agent == Path("/opt/arc3/ARC3-Inference/inference/agent/tool_agent.py").resolve()
assert runtime_tool_agent.read_bytes() == bundle_tool_agent.read_bytes()
print("exact Kaggle RTDv12 winner: cap14, fixed30, no replay, reflection dormant")
PYCHAMPION
mkdir -p /opt/arc3/work/score-observer
'@ } elseif ($DisableReplay) { @'
./.venv/bin/python - <<'PYNOREPLAY' 2>&1 | tee /opt/arc3/replay-selftest.log
import inspect
import os

from inference.agent import tool_agent

assert os.environ["ARC3_REPLAY_ENABLED"] == "0"
assert "ARC3_REPLAY_ARM" not in os.environ
assert "ARC3_REPLAY_TRIGGER_REMINDER" not in os.environ
assert tool_agent._REPLAY_ENABLED is False
assert tool_agent._REPLAY_TRIGGER_REMINDER is False
agent = tool_agent.ToolAgent()
assert "Lossless replay memory:" not in agent._system_prompt
assert "replay.repeated_states()" not in tool_agent._PYTHON_TOOL_DESCRIPTION
assert os.environ["ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED"] == "1"
reflection, error = tool_agent._validated_level_reflection(
    '{"winning_world_model":"Match roles to reveal the exit.",'
    '"decisive_evidence":"The engine confirmed the level transition.",'
    '"minimal_recipe":"Apply the verified role rule once.",'
    '"redundant_actions":"No redundant action is required.",'
    '"next_level_rule":"Transfer the role rule and verify."}'
)
assert not error, error
assert "Winning world model:" in reflection
reflection_version = os.environ.get("ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION", "3")
if reflection_version == "6":
    source = inspect.getsource(tool_agent.ToolAgent._generate_same_context_level_reflection)
    assert "max_output_tokens_override=1536" in source
    assert "thinking_override=True" in source
    assert "max_output_tokens_override=448" in source
    assert "thinking_override=False" in source
print(f"no-replay + Reflection V{reflection_version} self-test: ok")
PYNOREPLAY
mkdir -p /opt/arc3/work/score-observer
'@ } else { @'
set +e
./.venv/bin/python /opt/arc3/bundle/test_episodic_replay.py \
  2>&1 | tee /opt/arc3/replay-selftest.log
REPLAY_SELFTEST_STATUS=${PIPESTATUS[0]}
set -e
if [ "$REPLAY_SELFTEST_STATUS" -ne 0 ]; then
  echo "episodic replay self-test failed with status $REPLAY_SELFTEST_STATUS" | \
    gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  sync_all
  exit "$REPLAY_SELFTEST_STATUS"
fi
./.venv/bin/python /opt/arc3/bundle/test_full_replay_reflection.py \
  2>&1 | tee -a /opt/arc3/replay-selftest.log
./.venv/bin/python /opt/arc3/bundle/test_reflection_v6.py \
  2>&1 | tee -a /opt/arc3/replay-selftest.log
./.venv/bin/python /opt/arc3/bundle/test_context_compaction.py \
  2>&1 | tee -a /opt/arc3/replay-selftest.log
mkdir -p /opt/arc3/work/score-observer
'@ }
$championSelftestMarker = 'exact Kaggle RTDv12 winner: cap14, fixed30, no replay, reflection dormant'
if ($ChampionContextSweep) {
    $contextSelftestMarker = "exact Kaggle RTDv12 context sweep: ctx$AnalyzerContextWindow, fixed$PersistentHistoryAssistantTurns, cap14, no replay, reflection dormant"
    $historyAssert = 'assert tool_agent._PERSISTENT_HISTORY_ASSISTANT_TURNS == 30'
    if ([regex]::Matches($replaySelftestBlock, [regex]::Escape($historyAssert)).Count -ne 1) {
        throw 'Champion context history self-test anchor drift'
    }
    $contextAssertions = @"
assert os.environ["LOCAL_ANALYZER_CONTEXT_WINDOW"] == "$AnalyzerContextWindow"
assert os.environ["ARC3_PERSISTENT_HISTORY_ASSISTANT_TURNS"] == "$PersistentHistoryAssistantTurns"
assert tool_agent._PERSISTENT_HISTORY_ASSISTANT_TURNS == $PersistentHistoryAssistantTurns
"@.TrimEnd("`r", "`n")
    $replaySelftestBlock = $replaySelftestBlock.Replace($historyAssert, $contextAssertions)
    $agentAnchor = 'agent = tool_agent.ToolAgent()'
    if ([regex]::Matches($replaySelftestBlock, [regex]::Escape($agentAnchor)).Count -ne 1) {
        throw 'Champion context budget self-test anchor drift'
    }
    $budgetAssert = "assert agent._context_budget_tokens == $($AnalyzerContextWindow - 1024)"
    $replaySelftestBlock = $replaySelftestBlock.Replace($agentAnchor, "$agentAnchor`n$budgetAssert")
    $replaySelftestBlock = $replaySelftestBlock.Replace($championSelftestMarker, $contextSelftestMarker)
    $championSelftestMarker = $contextSelftestMarker
}
if ($exactKaggleSemantics -and ($DynamicSlack -or $Stall140Only -or $ChampionRefinement -or $visualTransitionArm -or $toolkitMatrixArm -or $visualToolkitArm)) {
    $championSelftestPrint = "print(`"$championSelftestMarker`")"
    if ([regex]::Matches($replaySelftestBlock, [regex]::Escape($championSelftestPrint)).Count -ne 1) {
        throw 'Exact-Kaggle mechanism self-test anchor drift'
    }
    $championMechanismChecks = [Collections.Generic.List[string]]::new()
    if ($DynamicSlack) {
        $championMechanismChecks.Add(@'
import pickle

assert os.environ["ARC3_DYNAMIC_SLACK_ENABLED"] == "1"
assert os.environ["ARC3_DYNAMIC_SLACK_GRANT_FRACTION"] == "0.75"
assert os.environ["ARC3_DYNAMIC_SLACK_MAX_EXTRA_SECONDS"] == "1200"
with open("/opt/arc3/bundle/benchmark_initial.pkl", "rb") as stream:
    benchmark = pickle.load(stream)
assert benchmark.solver.dynamic_slack_enabled is True
assert benchmark.solver.dynamic_slack_grant_fraction == 0.75
assert benchmark.solver.dynamic_slack_max_extra_seconds == 1200.0
assert callable(benchmark.solver.runtime_limit_seconds_for_game)
print("champion Dynamic Slack activation self-test: ok")
'@)
    }
    if ($Stall140Only) {
        $championMechanismChecks.Add(@'
from inference.framework import solver as solver_module

assert solver_module.STALL_ACTION_LIMIT == 140
print("champion Stall-140 activation self-test: ok")
'@)
    }
    if ($ChampionRefinement) {
        $championMechanismChecks.Add(@'
assert os.environ["ARC3_REASONING_POLICY"] == "refinement"
print("champion routed Refinement environment self-test: ok")
'@)
    }
    if ($visualTransitionArm -or $visualToolkitArm) {
        $championMechanismChecks.Add(@"
from inference.agent import prompts
from inference.framework import solver as solver_module

visual_mode = "$effectiveVisualTransitionMode"
assert os.environ["ARC3_VISUAL_TRANSITION_MODE"] == visual_mode
assert prompts.VISUAL_TRANSITION_MODE == visual_mode
assert tool_agent._VISUAL_TRANSITION_MODE == visual_mode
assert tool_agent._VISUAL_TRANSITION_ENABLED is (visual_mode != "control")
assert tool_agent._VISUAL_TRANSITION_IMAGES is (visual_mode in {"additive", "replace"})
assert tool_agent._VISUAL_TRANSITION_REPLACES_LEGACY is (visual_mode == "replace")
assert solver_module._visual_transition_sample_indices(64) == (
    6, [0, 13, 25, 38, 50, 63]
)
has_region_tool = "last_animation.region" in (
    prompts.STRUCTURED_RUNTIME_STATE_ADDENDUM
    + prompts.PYTHON_ADDENDUM
    + tool_agent._PYTHON_TOOL_DESCRIPTION
)
assert has_region_tool is (visual_mode != "replace")
agent._pending_visual_transition_parts = [
    {"type": "text", "text": "queued transition evidence"}
]
ordered_message = agent._build_user_message("next reasoning prompt", None)
assert ordered_message["content"][0]["text"] == "queued transition evidence"
assert ordered_message["content"][1]["text"].startswith("next reasoning prompt")
print("champion visual-transition $effectiveVisualTransitionMode activation self-test: ok")
"@)
    }
    if ($toolkitMatrixArm -or $visualToolkitArm) {
        $toolkitEnabled = $toolkitEnabledForRun
        $reminderEnabled = $reminderEnabledForRun
        $championMechanismChecks.Add(@"
import importlib.util

toolkit_enabled = "$toolkitEnabled" == "True"
reminder_enabled = "$reminderEnabled" == "True"
assert (importlib.util.find_spec("inference.agent.cpu_vision") is not None) is toolkit_enabled
assert (importlib.util.find_spec("inference.agent.budget_reminder") is not None) is reminder_enabled
assert (os.environ.get("ARC3_BUDGET_REMINDER_ENABLED") == "1") is reminder_enabled
assert (getattr(agent, "_budget_reminder", None) is not None) is reminder_enabled
has_toolkit_prompt = "vision.help" in agent._system_prompt
assert has_toolkit_prompt is toolkit_enabled
print("champion toolkit matrix $toolkitSelftestMode activation self-test: ok")
"@)
    }
    $championSelftestReplacement = ($championMechanismChecks -join $startupNewline) + $startupNewline + $championSelftestPrint
    $replaySelftestBlock = $replaySelftestBlock.Replace($championSelftestPrint, $championSelftestReplacement)
}
$startup = $startup.Replace($replaySelftestAnchor, $replaySelftestBlock)
$startup = $startup.Replace('MODEL_ID="unsloth/Qwen3.8-27B-NVFP4"', "MODEL_ID=`"$ModelId`"")
$startup = $startup.Replace('MODEL_REVISION="7d6f8d4d72f56b92b3cdbf22f156b90e1bab0108"', "MODEL_REVISION=`"$ModelRevision`"")
$startup = $startup.Replace('/opt/arc3/qwen38-model', '/opt/arc3/flashnext-model')
$hardLifetimeSeconds = [Math]::Max(18000, $MaxRunRuntimeMinutes * 60 + 5400)
$startup = $startup.Replace('sleep 11700', "sleep $hardLifetimeSeconds")
$startup = $startup.Replace(
    '# Hard cost guard: 3h15m from VM startup, including package/model download.',
    "# Hard cost guard: $hardLifetimeSeconds seconds from VM startup, including setup."
)

$teardownAnchor = '  pkill -TERM -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true'
if (!$startup.Contains($teardownAnchor)) { throw 'Teardown anchor missing' }
$teardownContainers = "  docker stop -t 20 flashnext 2>/dev/null || true"
if ($ColocatedHudCpu) {
    $teardownContainers = "  docker stop -t 20 hud-codegen 2>/dev/null || true`n$teardownContainers"
}
$startup = $startup.Replace($teardownAnchor, "$teardownContainers`n$teardownAnchor")

$serverPattern = '(?s)curl -LsSf https://astral\.sh/uv/install\.sh \| sh\r?\n.*?PYSMOKE\r?\nsync_all'
if ([regex]::Matches($startup, $serverPattern).Count -ne 1) { throw 'Expected exactly one serving block' }
$startup = [regex]::Replace($startup, $serverPattern, $serverBlock)
$makeInstallAnchor = 'make install-a108'
if ([regex]::Matches($startup, [regex]::Escape($makeInstallAnchor)).Count -ne 1) {
    throw 'Harness environment install anchor drift'
}
$goldenHarnessInstall = @'
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  test -x ./.venv/bin/python
  ./.venv/bin/python -c 'import numpy, openai, PIL; print("golden runtime: harness environment import check passed")'
else
  make install-a108
fi
'@.TrimEnd("`r", "`n")
$startup = $startup.Replace($makeInstallAnchor, $goldenHarnessInstall)
foreach ($contextAnchor in @('"context_length": 32768', '--max-model-len 32768')) {
    if ([regex]::Matches($startup, [regex]::Escape($contextAnchor)).Count -ne 1) {
        throw "Serving context anchor drift: $contextAnchor"
    }
}
$startup = $startup.Replace('"context_length": 32768', "`"context_length`": $AnalyzerContextWindow")
$startup = $startup.Replace('--max-model-len 32768', "--max-model-len $AnalyzerContextWindow")

if ($ServingProfile -eq 'best-serving') {
    $startup = $startup.Replace(
        'CONVERTER_OBJECT=$(meta arc3-converter-object)',
        ('CONVERTER_OBJECT=$(meta arc3-converter-object)' + $startupNewline + 'PLE_PATCH_OBJECT=$(meta arc3-ple-patch-object)')
    )
    $startup = $startup.Replace(
        'gcloud storage cp "$CONVERTER_OBJECT" /opt/arc3/convert_radix_ple.py',
        ('gcloud storage cp "$CONVERTER_OBJECT" /opt/arc3/convert_radix_ple.py' + $startupNewline + 'gcloud storage cp "$PLE_PATCH_OBJECT" /opt/arc3/ple_layer_native_fp8.py' + $startupNewline + "echo '$PlePatchSha  /opt/arc3/ple_layer_native_fp8.py' | sha256sum -c -")
    )
    $basePleAnchor = 'docker run --rm --gpus all --entrypoint nvidia-smi "$CONTAINER_IMAGE"'
    $basePleAudit = @'
docker run --rm --gpus all --entrypoint nvidia-smi "$CONTAINER_IMAGE"
BASE_PLE_PATH=/usr/local/lib/python3.12/dist-packages/vllm/models/qwen3_8_flash_next/nvidia/ple_layer.py
BASE_PLE_SHA=$(docker run --rm --entrypoint sha256sum "$CONTAINER_IMAGE" "$BASE_PLE_PATH" | awk '{print $1}')
if [ "$BASE_PLE_SHA" != 'a71144c1d36e06f22a2da1b1ada900076597fe5e824a911e7ada86249a0993e7' ]; then
  echo "vLLM PLE source drift: $BASE_PLE_SHA" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  exit 1
fi
'@
    if ([regex]::Matches($startup, [regex]::Escape($basePleAnchor)).Count -ne 1) { throw 'Base PLE audit anchor drift' }
    $startup = $startup.Replace($basePleAnchor, $basePleAudit.TrimEnd("`r", "`n"))
    $conversionPattern = '(?s)# RadixArk stores the 51\.2B-entry PLE table as FP8 plus a scalar\..*?2>&1 \| tee /opt/arc3/ple-conversion\.log'
    if ([regex]::Matches($startup, $conversionPattern).Count -ne 1) { throw 'PLE conversion block drift' }
    $nativePleBlock = @'
# Keep the published PLE table in native FP8 form. The pinned runtime patch
# performs the same BF16 dequantization lazily on CPU lookup.
cat > /opt/arc3/flashnext-model/ple-bf16-conversion.json <<'JSON'
{"mode":"native_fp8_cpu_lookup","base_ple_sha256":"a71144c1d36e06f22a2da1b1ada900076597fe5e824a911e7ada86249a0993e7","runtime_patch_sha256":"2f0e6febb8c6fdeeeb5b85cc2d7098ba7ce7ee2464d690c33fdcf75e3215c33a"}
JSON
'@
    $startup = [regex]::Replace($startup, $conversionPattern, $nativePleBlock.TrimEnd("`r", "`n"))
    $serverMountAnchor = '    -v /opt/arc3/vllm-cache:/root/.cache \'
    if ([regex]::Matches($startup, [regex]::Escape($serverMountAnchor)).Count -ne 1) { throw 'Native PLE mount anchor drift' }
    $startup = $startup.Replace(
        $serverMountAnchor,
        ($serverMountAnchor + $startupNewline + '    -v "/opt/arc3/ple_layer_native_fp8.py:$BASE_PLE_PATH:ro" \')
    )
    $startup = $startup.Replace(
        'PLE FP8 deterministically dequantized to BF16 for CPU offload',
        'native FP8 PLE with pinned CPU lookup dequantization patch'
    )
    $startup = $startup.Replace(
        '-e VLLM_NO_USAGE_STATS=1 \',
        ('-e OMP_NUM_THREADS=1 \' + $startupNewline + '    -e VLLM_NO_USAGE_STATS=1 \')
    )
    $startup = $startup.Replace('--gpu-memory-utilization 0.96 \', '--gpu-memory-utilization 0.965 \')
    $startup = $startup.Replace(
        '--kv-cache-dtype "$kv_dtype" \',
        '--kv-cache-dtype "$kv_dtype" --scheduling-policy fcfs --watermark 0.000 --enable-chunked-prefill \'
    )
    $startup = $startup.Replace(
        '--reasoning-parser qwen3',
        ('--reasoning-parser qwen3 \' + $startupNewline + '    --cudagraph-capture-sizes 1 2 4 8 12 14 15 16 17 18 19 20 21 22 24 32 40')
    )
    $kvStartupPattern = '(?s)# Prefer FP8 KV to make 22 live lanes comfortable\..*?echo "\$KV_DTYPE_USED" > /opt/arc3/kv-dtype-used\.txt'
    if ([regex]::Matches($startup, $kvStartupPattern).Count -ne 1) { throw 'KV startup block drift' }
$kvStartup = @'
# The fixed-work serving sweep established auto/BF16 QSA KV as the
# quality-safe production setting for this model/runtime.
container_gpu_ready() {
  docker run --rm --gpus all --entrypoint "$CONTAINER_PYTHON" \
    "$CONTAINER_IMAGE" - <<'PYCUDACHECK'
import torch
assert torch.cuda.is_available(), "CUDA unavailable in serving container"
assert torch.cuda.device_count() == 1, torch.cuda.device_count()
print(torch.cuda.get_device_name(0))
PYCUDACHECK
}

if ! container_gpu_ready; then
  sleep 10
  container_gpu_ready
fi
KV_DTYPE_USED=auto
start_server "$KV_DTYPE_USED"
if ! wait_server; then
  cp /opt/arc3/vllm.log /opt/arc3/vllm-start-attempt1.log
  sleep 10
  container_gpu_ready
  start_server "$KV_DTYPE_USED"
fi
if ! wait_server; then
  echo "Flash-Next vLLM failed for auto KV" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  sync_all
  exit 1
fi
echo "$KV_DTYPE_USED" > /opt/arc3/kv-dtype-used.txt
'@
    $startup = [regex]::Replace($startup, $kvStartupPattern, $kvStartup)
}

$runtimeExports = [Collections.Generic.List[string]]::new()
if ($ActionCap -gt 0) { $runtimeExports.Add("export ARC3_ACTION_CAP=$ActionCap") }
$runtimeExports.Add("export ARC3_POST_LEVEL_UNCAPPED_TURNS=$PostLevelUncappedTurns")
if ($VerifiedQueue) {
    $runtimeExports.Add('export ARC3_VERIFIED_QUEUE_ENABLED=1')
    $runtimeExports.Add('export ARC3_VERIFIED_QUEUE_LOOP_STOP=1')
    $runtimeExports.Add('export ARC3_VERIFIED_QUEUE_MAX_CYCLE=2')
    $runtimeExports.Add('export ARC3_VERIFIED_QUEUE_LEDGER=1')
}
if ($VerifiedHudV2 -or $VerifiedHudV3) {
    $runtimeExports.Add('export ARC3_VERIFIED_QUEUE_HUD_MASK=1')
    $runtimeExports.Add('export ARC3_VERIFIED_QUEUE_HUD_EDGE_DEPTH=4')
}
if ($VerifiedHudV3) {
    $runtimeExports.Add('export ARC3_VERIFIED_QUEUE_HUD_V3=1')
    $runtimeExports.Add('export ARC3_VERIFIED_QUEUE_HUD_SAMPLE_FRAMES=5')
    $runtimeExports.Add("export ARC3_HUD_CPU_BASE_URL='$HudCpuBaseUrl'")
    $runtimeExports.Add('export ARC3_HUD_CPU_MODEL=deepseek-coder-v2-lite-q4km')
    $runtimeExports.Add('export ARC3_HUD_CPU_WORKERS=2')
    $runtimeExports.Add('export ARC3_HUD_CPU_TIMEOUT_SECONDS=120')
    $runtimeExports.Add('export ARC3_HUD_CPU_MAX_TOKENS=32')
}
if ($HypothesisLab) {
    $runtimeExports.Add('export ARC3_HYPOTHESIS_LAB_ENABLED=1')
}
if ($exactKaggleSemantics) {
    $runtimeExports.Add('unset ARC3_REPLAY_ENABLED ARC3_REPLAY_ARM ARC3_REPLAY_TRIGGER_REMINDER')
} elseif ($DisableReplay) {
    $runtimeExports.Add('export ARC3_REPLAY_ENABLED=0')
    $runtimeExports.Add('unset ARC3_REPLAY_ARM ARC3_REPLAY_TRIGGER_REMINDER')
} else {
    $runtimeExports.Add('export ARC3_REPLAY_ENABLED=1')
    $runtimeExports.Add("export ARC3_REPLAY_ARM=$ReplayArm")
    $runtimeExports.Add("export ARC3_REPLAY_TRIGGER_REMINDER=$(if ($ReplayArm -eq 'C') { 1 } else { 0 })")
}
$runtimeExports.Add($(if ($ChampionReflectionV3) { 'export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED=1' } elseif ($exactKaggleSemantics) { 'unset ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED' } else { 'export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED=1' }))
if ($ChampionReflectionV3) {
    $runtimeExports.Add('export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION=3')
} elseif ($exactKaggleSemantics) {
    $runtimeExports.Add('unset ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION')
} elseif ($ReflectionV6) {
    $runtimeExports.Add('export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION=6')
} else {
    $runtimeExports.Add('unset ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION')
}
if ($exactKaggleSemantics) {
    $runtimeExports.Add('unset ARC3_CONTEXT_COMPACTION_ENABLED ARC3_CONTEXT_COMPACTION_TRIGGER_FRACTION')
    $runtimeExports.Add('unset ARC3_CONTEXT_COMPACTION_KEEP_ASSISTANT_TURNS ARC3_CONTEXT_COMPACTION_MAX_TOKENS')
    $runtimeExports.Add('unset ARC3_CONTEXT_TRIM_TARGET_FRACTION ARC3_CONTEXT_HISTORY_MAX_ASSISTANT_TURNS')
} else {
    $runtimeExports.Add('export ARC3_CONTEXT_COMPACTION_ENABLED=1')
    $runtimeExports.Add("export ARC3_CONTEXT_COMPACTION_TRIGGER_FRACTION=$ContextTriggerFraction")
    $runtimeExports.Add('export ARC3_CONTEXT_COMPACTION_KEEP_ASSISTANT_TURNS=0')
    $runtimeExports.Add('export ARC3_CONTEXT_COMPACTION_MAX_TOKENS=1024')
    $runtimeExports.Add('export ARC3_CONTEXT_TRIM_TARGET_FRACTION=0.50')
    $runtimeExports.Add('export ARC3_CONTEXT_HISTORY_MAX_ASSISTANT_TURNS=0')
}
$runtimeExports.Add("export LOCAL_ANALYZER_CONTEXT_WINDOW=$AnalyzerContextWindow")
$runtimeExports.Add("export ARC3_PERSISTENT_HISTORY_ASSISTANT_TURNS=$PersistentHistoryAssistantTurns")
$runtimeExports.Add($(if ($visualTransitionArm -or $visualToolkitArm) { "export ARC3_VISUAL_TRANSITION_MODE=$effectiveVisualTransitionMode" } else { 'unset ARC3_VISUAL_TRANSITION_MODE' }))
$runtimeExports.Add($(if ($reminderEnabledForRun) { 'export ARC3_BUDGET_REMINDER_ENABLED=1' } else { 'unset ARC3_BUDGET_REMINDER_ENABLED' }))
$runtimeExports.Add($(if ($ChampionRefinement) { 'export ARC3_REASONING_POLICY=refinement' } else { 'unset ARC3_REASONING_POLICY' }))
if ($Queued22) {
    $runtimeExports.Add('export ARC3_BENCHMARK_CONCURRENCY=22')
}
if ($DynamicSlack) {
    $runtimeExports.Add('export ARC3_DYNAMIC_SLACK_ENABLED=1')
    $runtimeExports.Add('export ARC3_DYNAMIC_SLACK_GRANT_FRACTION=0.75')
    $runtimeExports.Add('export ARC3_DYNAMIC_SLACK_MAX_EXTRA_SECONDS=1200')
}
$runtimeExports.Add("export ARC3_MAX_RUNTIME_S_PER_GAME=$MaxRuntimePerGame")
$runtimeExports.Add("export ARC3_MAX_RUN_RUNTIME_MINUTES=$MaxRunRuntimeMinutes")
if ($runtimeExports.Count -gt 0) {
    $runtimeAnchor = 'export ARC3_REEXPLORE_STRICT="" ARC3_GAME_SUBSET="" ARC3_STATE_GRAPH="" ARC3_FRAME_MODE=full'
    if ([regex]::Matches($startup, [regex]::Escape($runtimeAnchor)).Count -ne 1) { throw 'Runtime export anchor drift' }
    $startup = $startup.Replace(
        $runtimeAnchor,
        (($runtimeExports -join $startupNewline) + $startupNewline + $runtimeAnchor)
    )
}
if ($GameSubset) {
    $emptySubset = 'ARC3_GAME_SUBSET=""'
    if ([regex]::Matches($startup, [regex]::Escape($emptySubset)).Count -ne 1) { throw 'Game-subset anchor drift' }
    $startup = $startup.Replace($emptySubset, "ARC3_GAME_SUBSET='$GameSubset'")
}

$syncTelemetryPattern = '(?m)(  \[ -f /opt/arc3/serving-environment\.txt \] && timeout 10 gcloud storage cp \\\r?\n    /opt/arc3/serving-environment\.txt "\$BUCKET/\$RUN_ID/serving-environment\.txt" >/dev/null 2>&1 \|\| true)'
if ([regex]::Matches($startup, $syncTelemetryPattern).Count -ne 1) { throw 'Serving telemetry sync anchor drift' }
$syncTelemetry = @'
$1
  for telemetry in model-download.log ple-conversion.log gpu-after-load.csv ram-after-load.txt kv-dtype-used.txt vllm.log vllm-fp8-failed.log vllm-start-attempt1.log verified-queue-selftest.log hypothesis-lab-selftest.log replay-selftest.log pre-harness-warmup.json pre-harness-warmup.log; do
    [ -f "/opt/arc3/$telemetry" ] && timeout 20 gcloud storage cp \
      "/opt/arc3/$telemetry" "$BUCKET/$RUN_ID/$telemetry" >/dev/null 2>&1 || true
  done
'@
$startup = [regex]::Replace($startup, $syncTelemetryPattern, $syncTelemetry)

foreach ($required in @(
    'RadixArk/Qwen3.8-Flash-Next-NVFP4',
    '--max-num-seqs 22',
    "--max-model-len $AnalyzerContextWindow",
    'VLLM_PLE_CPU_OFFLOAD=1',
    '--distributed-executor-backend mp',
    '--hostname arc3-vllm',
    '--tool-call-parser qwen3_xml',
    'bundle-q38-r6-animation-reformed-tool-v7-f180e41d-retry1.tgz'
)) {
    if (!$startup.Contains($required) -and $required -ne $ExpectedBundle) {
        throw "Patched startup missing: $required"
    }
}
if ($HypothesisLab) {
    foreach ($labSetting in @(
        'export ARC3_HYPOTHESIS_LAB_ENABLED=1',
        '/opt/arc3/bundle/test_hypothesis_lab.py',
        '/opt/arc3/bundle/test_hypothesis_lab_tool_agent.py'
    )) {
        if (!$startup.Contains($labSetting)) {
            throw "Hypothesis-lab setting missing: $labSetting"
        }
    }
}
if ($exactKaggleSemantics) {
    foreach ($disabledReplaySetting in @(
        'unset ARC3_REPLAY_ENABLED ARC3_REPLAY_ARM ARC3_REPLAY_TRIGGER_REMINDER'
    )) {
        if (!$startup.Contains($disabledReplaySetting)) {
            throw "Exact Kaggle replay setting missing: $disabledReplaySetting"
        }
    }
} elseif ($DisableReplay) {
    foreach ($disabledReplaySetting in @(
        'export ARC3_REPLAY_ENABLED=0',
        'unset ARC3_REPLAY_ARM ARC3_REPLAY_TRIGGER_REMINDER'
    )) {
        if (!$startup.Contains($disabledReplaySetting)) {
            throw "Replay-disable setting missing: $disabledReplaySetting"
        }
    }
} else {
    foreach ($replaySetting in @(
        'export ARC3_REPLAY_ENABLED=1',
        "export ARC3_REPLAY_ARM=$ReplayArm",
        "export ARC3_REPLAY_TRIGGER_REMINDER=$(if ($ReplayArm -eq 'C') { 1 } else { 0 })"
    )) {
        if (!$startup.Contains($replaySetting)) {
            throw "Replay setting missing: $replaySetting"
        }
    }
}
$reflectionSettings = if ($ChampionReflectionV3) { @(
    'export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED=1',
    'export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION=3',
    'exact Kaggle RTDv12 winner + guarded Reflection V3 self-test: ok'
) } elseif ($exactKaggleSemantics) { @(
    'unset ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED',
    $championSelftestMarker
) } else { @(
    'export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED=1',
    '/opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/prompts.py',
    '/opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/python_tool_sandbox.py',
    '/opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/tool_agent.py',
    $RuntimeOverlayPromptsSha,
    $RuntimeOverlaySandboxSha,
    $RuntimeOverlayToolAgentSha
) }
if ($exactKaggleSemantics -and !$startup.Contains('cp -a /opt/arc3/bundle/src/ARC3-Inference/inference/. /opt/arc3/ARC3-Inference/inference/')) {
    throw 'Exact Kaggle champion bundle source activation is missing'
}
if ($exactKaggleSemantics -and !$startup.Contains("find /opt/arc3/ARC3-Inference/inference -type f -name '*.pyc' -delete")) {
    throw 'Exact Kaggle champion stale bytecode cleanup is missing'
}
if ($exactKaggleSemantics -and !$ChampionReflectionV3) {
    foreach ($forbiddenChampionSetting in @(
        'export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED=1',
        '/opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/tool_agent.py',
        'no-replay + Reflection V3 self-test: ok'
    )) {
        if ($startup.Contains($forbiddenChampionSetting)) {
            throw "Exact Kaggle champion contains forbidden experimental setting: $forbiddenChampionSetting"
        }
    }
} elseif ($ChampionReflectionV3) {
    foreach ($forbiddenReflectionSetting in @(
        '/opt/arc3/bundle/runtime-overlay/ARC3-Inference/inference/agent/tool_agent.py',
        'unset ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED',
        'export ARC3_CONTEXT_COMPACTION_ENABLED=1'
    )) {
        if ($startup.Contains($forbiddenReflectionSetting)) {
            throw "Champion Reflection V3 contains forbidden setting: $forbiddenReflectionSetting"
        }
    }
} elseif ($DisableReplay) {
    $reflectionSettings += @(
        'reflection_version = os.environ.get("ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION", "3")',
        'assert tool_agent._REPLAY_ENABLED is False'
    )
    if ($ReflectionV6) {
        $reflectionSettings += @(
            'export ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION=6',
            'max_output_tokens_override=1536',
            'thinking_override=True',
            'max_output_tokens_override=448',
            'thinking_override=False'
        )
    }
} else {
    $reflectionSettings += @(
        '/opt/arc3/bundle/test_episodic_replay.py',
        '/opt/arc3/bundle/test_full_replay_reflection.py'
    )
}
foreach ($reflectionSetting in $reflectionSettings) {
    if (!$startup.Contains($reflectionSetting)) {
        throw "Reflection bundle setting missing: $reflectionSetting"
    }
}
if ($ChampionRefinement) {
    foreach ($refinementSetting in @(
        'export ARC3_REASONING_POLICY=refinement',
        'champion routed Refinement environment self-test: ok'
    )) {
        if (!$startup.Contains($refinementSetting)) {
            throw "Champion Refinement setting missing: $refinementSetting"
        }
    }
} elseif ($startup.Contains('export ARC3_REASONING_POLICY=refinement')) {
    throw 'Non-Refinement arm contains the Refinement policy export.'
}
if ($ChampionContextSweep) {
    foreach ($contextSweepSetting in @(
        "--max-model-len $AnalyzerContextWindow",
        "export LOCAL_ANALYZER_CONTEXT_WINDOW=$AnalyzerContextWindow",
        "export ARC3_PERSISTENT_HISTORY_ASSISTANT_TURNS=$PersistentHistoryAssistantTurns",
        $championSelftestMarker
    )) {
        if (!$startup.Contains($contextSweepSetting)) {
            throw "Champion context-sweep setting missing: $contextSweepSetting"
        }
    }
}
if ($visualTransitionArm -or $visualToolkitArm) {
    foreach ($visualTransitionSetting in @(
        "export ARC3_VISUAL_TRANSITION_MODE=$effectiveVisualTransitionMode",
        "champion visual-transition $effectiveVisualTransitionMode activation self-test: ok",
        '_visual_transition_sample_indices(64)',
        'queued transition evidence'
    )) {
        if (!$startup.Contains($visualTransitionSetting)) {
            throw "Visual-transition setting missing: $visualTransitionSetting"
        }
    }
} elseif ($startup.Contains('export ARC3_VISUAL_TRANSITION_MODE=')) {
    throw 'Non-visual arm contains the visual-transition mode export.'
}
if ($toolkitMatrixArm -or $visualToolkitArm) {
    $expectedReminderExport = if ($reminderEnabledForRun) {
        'export ARC3_BUDGET_REMINDER_ENABLED=1'
    } else {
        'unset ARC3_BUDGET_REMINDER_ENABLED'
    }
    foreach ($toolkitMatrixSetting in @(
        $expectedReminderExport,
        "champion toolkit matrix $toolkitSelftestMode activation self-test: ok",
        'importlib.util.find_spec'
    )) {
        if (!$startup.Contains($toolkitMatrixSetting)) {
            throw "Toolkit matrix setting missing: $toolkitMatrixSetting"
        }
    }
}
if ($ReflectionV6) {
    foreach ($contextSetting in @(
        '--enable-prompt-tokens-details',
        'export ARC3_CONTEXT_COMPACTION_ENABLED=1',
        "export ARC3_CONTEXT_COMPACTION_TRIGGER_FRACTION=$ContextTriggerFraction",
        'export ARC3_CONTEXT_COMPACTION_KEEP_ASSISTANT_TURNS=0',
        'export ARC3_CONTEXT_COMPACTION_MAX_TOKENS=1024',
        'export ARC3_CONTEXT_TRIM_TARGET_FRACTION=0.50',
        'export ARC3_CONTEXT_HISTORY_MAX_ASSISTANT_TURNS=0',
        '/opt/arc3/bundle/test_context_compaction.py',
        '/opt/arc3/bundle/test_reflection_v6.py'
    )) {
        if (!$startup.Contains($contextSetting)) {
            throw "Context-compaction setting missing: $contextSetting"
        }
    }
}
if ($DisableCurator) {
    foreach ($disabledSetting in @(
        'none|cpu_reviewed_themes|gpu_theme_curator|gpu_world_model_curator',
        'if [ "$INFLUENCE_MODE" = none ]; then',
        'unset ARC3_COMMON_THEMES_PATH ARC3_COMMON_THEMES_INJECTION_LOG'
    )) {
        if (!$startup.Contains($disabledSetting)) {
            throw "Curator-disable setting missing: $disabledSetting"
        }
    }
}
if ($GoldenRuntimeImage) {
    foreach ($goldenSetting in @(
        'GOLDEN_RUNTIME_IMAGE=$(meta arc3-golden-runtime-image 2>/dev/null || true)',
        'golden runtime: cleared prior run state while preserving immutable caches',
        'golden runtime: skipping apt index refresh',
        'golden runtime: reusing Docker and NVIDIA container toolkit',
        'golden runtime image %s: immutable model payload reused',
        '-e ARC3_GOLDEN_RUNTIME_IMAGE="$GOLDEN_RUNTIME_IMAGE"',
        'golden image size-manifest attestation passed',
        'golden runtime: harness environment import check passed'
    )) {
        if (!$startup.Contains($goldenSetting)) {
            throw "Golden runtime fast-path setting missing: $goldenSetting"
        }
    }
}
if ($startup.Contains('unsloth/Qwen3.8-27B-NVFP4')) { throw 'Old model survived startup patch' }
if ($startup.Contains('--speculative-config')) { throw 'MTP unexpectedly enabled' }
if ([regex]::Matches($startup, '--max-num-batched-tokens 6144').Count -ne 1) { throw 'Expected exactly one 6144-token serving cap' }
if ($startup.Contains('--max-num-batched-tokens 8192')) { throw 'Old 8192-token serving cap survived startup patch' }
if ($ServingProfile -eq 'best-serving') {
    foreach ($bestSetting in @(
        '--gpu-memory-utilization 0.965',
        '--scheduling-policy fcfs',
        '--watermark 0.000',
        '--enable-chunked-prefill',
        '--cudagraph-capture-sizes 1 2 4 8 12 14 15 16 17 18 19 20 21 22 24 32 40',
        'OMP_NUM_THREADS=1',
        'KV_DTYPE_USED=auto',
        'container_gpu_ready',
        'vllm-start-attempt1.log',
        '/opt/arc3/bundle/pre_harness_warmup.py',
        'a71144c1d36e06f22a2da1b1ada900076597fe5e824a911e7ada86249a0993e7',
        '2f0e6febb8c6fdeeeb5b85cc2d7098ba7ce7ee2464d690c33fdcf75e3215c33a',
        '/opt/arc3/ple_layer_native_fp8.py:$BASE_PLE_PATH:ro'
    )) {
        if (!$startup.Contains($bestSetting)) { throw "Best-serving setting missing: $bestSetting" }
    }
} elseif ($startup.Contains('--cudagraph-capture-sizes')) {
    throw 'Baseline serving arm unexpectedly contains explicit CUDA graph sizes'
}
if ($ActionCap -gt 0 -and !$startup.Contains("export ARC3_ACTION_CAP=$ActionCap")) {
    throw 'Action cap export missing'
}
if (!$startup.Contains("export ARC3_POST_LEVEL_UNCAPPED_TURNS=$PostLevelUncappedTurns")) {
    throw 'Post-level uncapped-turn export missing'
}
if ($VerifiedQueue) {
    foreach ($verifiedSetting in @(
        'export ARC3_VERIFIED_QUEUE_ENABLED=1',
        'export ARC3_VERIFIED_QUEUE_LOOP_STOP=1',
        'export ARC3_VERIFIED_QUEUE_MAX_CYCLE=2',
        'export ARC3_VERIFIED_QUEUE_LEDGER=1',
        '/opt/arc3/bundle/test_verified_action_queue.py'
    )) {
        if (!$startup.Contains($verifiedSetting)) {
            throw "Verified-queue setting missing: $verifiedSetting"
        }
    }
}
if ($VerifiedHudV2 -or $VerifiedHudV3) {
    foreach ($hudSetting in @(
        'export ARC3_VERIFIED_QUEUE_HUD_MASK=1',
        'export ARC3_VERIFIED_QUEUE_HUD_EDGE_DEPTH=4'
    )) {
        if (!$startup.Contains($hudSetting)) {
            throw "Verified-HUD setting missing: $hudSetting"
        }
    }
}
if ($VerifiedHudV3) {
    foreach ($hudV3Setting in @(
        'export ARC3_VERIFIED_QUEUE_HUD_V3=1',
        'export ARC3_VERIFIED_QUEUE_HUD_SAMPLE_FRAMES=5',
        "export ARC3_HUD_CPU_BASE_URL='$HudCpuBaseUrl'",
        'export ARC3_HUD_CPU_MODEL=deepseek-coder-v2-lite-q4km',
        'export ARC3_HUD_CPU_WORKERS=2',
        '/opt/arc3/bundle/src/ARC3-Inference/inference/agent/hud_analyst.py'
    )) {
        if (!$startup.Contains($hudV3Setting)) {
            throw "Verified-HUD-v3 setting missing: $hudV3Setting"
        }
    }
}
if ($ColocatedHudCpu) {
    foreach ($colocatedSetting in @(
        "export ARC3_HUD_CPU_BASE_URL='http://127.0.0.1:8080/v1'",
        '/opt/arc3/start_colocated_hud_server.sh',
        "HUD_CPUSET='$ColocatedHudCpuSet'",
        'HUD_MEMORY_LIMIT=20g',
        'docker stop -t 20 hud-codegen'
    )) {
        if (!$startup.Contains($colocatedSetting)) {
            throw "Colocated-HUD setting missing: $colocatedSetting"
        }
    }
}
if ($Queued22) {
    foreach ($queuedSetting in @('export ARC3_BENCHMARK_CONCURRENCY=22')) {
        if (!$startup.Contains($queuedSetting)) { throw "Queued-22 setting missing: $queuedSetting" }
    }
}
if ($DynamicSlack) {
    foreach ($dynamicSlackSetting in @(
        'export ARC3_DYNAMIC_SLACK_ENABLED=1',
        'export ARC3_DYNAMIC_SLACK_GRANT_FRACTION=0.75',
        'export ARC3_DYNAMIC_SLACK_MAX_EXTRA_SECONDS=1200'
    )) {
        if (!$startup.Contains($dynamicSlackSetting)) { throw "Dynamic-slack setting missing: $dynamicSlackSetting" }
    }
}
if (!$startup.Contains("export ARC3_MAX_RUNTIME_S_PER_GAME=$MaxRuntimePerGame")) {
    throw 'Per-game runtime export missing'
}
if (!$startup.Contains("export ARC3_MAX_RUN_RUNTIME_MINUTES=$MaxRunRuntimeMinutes")) {
    throw 'Whole-run runtime export missing'
}
if (!$startup.Contains("sleep $hardLifetimeSeconds")) {
    throw 'Scaled hard-lifetime guard missing'
}
if ($ResumeCompletedGames) {
    foreach ($resumeSetting in @(
        'export ARC3_RESUME_ATTEMPT="$ATTEMPTS"',
        'gcloud storage rsync -r "$BUCKET/$RUN_ID/runs" /opt/arc3/work',
        'resume-enabled nonterminal exit; leaving MIG at size 1',
        'resume attempt ceiling exceeded'
    )) {
        if (!$startup.Contains($resumeSetting)) { throw "Resume setting missing: $resumeSetting" }
    }
}
if (!$startup.Contains("soft_end = datetime.now() + timedelta(minutes=$MaxRunRuntimeMinutes)")) {
    throw 'Whole-run soft deadline patch missing'
}
if ($startup.Contains("./.venv/bin/python - <<'PYRUNLIMIT'")) {
    throw 'Runner deadline patch still depends on the not-yet-created harness virtual environment'
}
if (!$startup.Contains("python3 - <<'PYRUNLIMIT'")) {
    throw 'Runner deadline patch is not using bootstrap Python'
}
if ($GameSubset -and !$startup.Contains("ARC3_GAME_SUBSET='$GameSubset'")) {
    throw 'Game subset export missing'
}
if ($startup.Contains("`r")) {
    throw 'Generated bash startup still contains CR characters after LF normalization'
}

if ($DirectInstance) {
    # Direct Spot instances are used only when the legacy project-wide instance
    # template quota is saturated. Preserve the startup payload, but make both
    # Direct instances cannot resize a nonexistent MIG and the runtime service
    # account is not allowed to delete Compute Engine resources.  A local OS
    # shutdown is permission-independent and reliably stops GPU billing.
    $managedTeardown = 'gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE"'
    if ([regex]::Matches($startup, [regex]::Escape($managedTeardown)).Count -ne 2) {
        throw 'Expected exactly two managed-instance teardown commands'
    }
    $startup = $startup.Replace(
        $managedTeardown,
        '/sbin/shutdown -h now'
    )
}

$startupSha = Get-StringSha256 $startup
if ($PreflightOnly) {
    [ordered]@{
        arm=$ArmSlug
        bundle=$CandidateBundle
        runner=$CandidateRunner
        feature=$CandidateFeature
        replay_enabled=(-not $DisableReplay)
        replay_arm=if ($DisableReplay) { $null } else { $ReplayArm }
        reflection_version=$reflectionVersion
        reflection_v3=($reflectionVersion -eq 'v3')
        reflection_v6=($reflectionVersion -eq 'v6')
        context_compaction_enabled=[bool]$ReflectionV6
        context_compaction_trigger_fraction=if ($ReflectionV6) { [double]$ContextTriggerFraction } else { $null }
        context_compaction_keep_assistant_turns=if ($ReflectionV6) { 0 } else { $null }
        context_warmup_sha256=if ($ReflectionV6) { $ContextWarmupSha } else { $null }
        exact_kaggle_champion=[bool]$ExactKaggleChampion
        champion_long_run=[bool]$ChampionLongRun
        stall140_only=[bool]$Stall140Only
        exact_kaggle_curator_ablation=[bool]$ExactKaggleCuratorAblation
        champion_reflection_v3=[bool]$ChampionReflectionV3
        champion_refinement=[bool]$ChampionRefinement
        champion_context_sweep=[bool]$ChampionContextSweep
        visual_transition_mode=if ($visualTransitionArm -or $visualToolkitArm) { $effectiveVisualTransitionMode } else { $null }
        toolkit_matrix_mode=if ($toolkitMatrixArm) { $ToolkitMatrixMode } else { $null }
        visual_toolkit_mode=if ($visualToolkitArm) { $VisualToolkitMode } else { $null }
        cpu_toolkit_enabled=$toolkitEnabledForRun
        budget_reminder_enabled=$reminderEnabledForRun
        golden_runtime_image=if ($GoldenRuntimeImage) { $GoldenRuntimeImage } else { $null }
        golden_runtime_image_id=if ($GoldenRuntimeImage) { [string]$goldenImageInfo.id } else { $null }
        analyzer_context_window=$AnalyzerContextWindow
        persistent_history_assistant_turns=$PersistentHistoryAssistantTurns
        reasoning_policy=if ($ChampionRefinement) { 'refinement' } else { $null }
        exact_kaggle_warmup_sha256=if ($exactKaggleSemantics) { $ExactKaggleWarmupSha } else { $null }
        curator_enabled=(-not $DisableCurator)
        resume_completed_games=[bool]$ResumeCompletedGames
        serving_profile=$ServingProfile
        action_cap=$ActionCap
        post_level_uncapped_turns=$PostLevelUncappedTurns
        verified_queue=[bool]$VerifiedQueue
        verified_hud_v2=[bool]$VerifiedHudV2
        verified_hud_v3=[bool]$VerifiedHudV3
        hypothesis_lab=[bool]$HypothesisLab
        hud_cpu_base_url=if ($VerifiedHudV3) { $HudCpuBaseUrl } else { $null }
        hud_cpu_colocated=[bool]$ColocatedHudCpu
        hud_cpu_cpuset=if ($ColocatedHudCpu) { $ColocatedHudCpuSet } else { $null }
        hud_cpu_installer_sha256=$colocatedHudInstallerSha
        game_subset=$GameSubset
        max_runtime_s_per_game=$MaxRuntimePerGame
        max_run_runtime_minutes=$MaxRunRuntimeMinutes
        hard_lifetime_seconds=$hardLifetimeSeconds
        queued_22=[bool]$Queued22
        dynamic_slack_enabled=[bool]$DynamicSlack
        dynamic_slack_grant_fraction=if ($DynamicSlack) { 0.75 } else { $null }
        dynamic_slack_max_extra_seconds=if ($DynamicSlack) { 1200 } else { $null }
        direct_instance=[bool]$DirectInstance
        score_observer_sha256=$scoreObserverSha
        startup_sha256=$startupSha
    } | ConvertTo-Json -Depth 10
    return
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$templateStamp = Get-Date -Format 'yyyyMMddHHmmss'
$runId = "g4run-q38-$ArmSlug-$stamp"
$mig = "arc3-g4-q38-$ArmSlug"
$template = "arc3-g4-q38-$ArmSlug-$templateStamp"
$instance = $mig
$prefix = "$Bucket/$runId"

if ($DirectInstance) {
    Assert-Absent @('compute','instances','describe',$instance,'--project',$Project,'--zone',$Zone,'--format=value(name)') "instance $instance"
} else {
    Assert-Absent @('compute','instance-templates','describe',$template,'--project',$Project,'--format=value(name)') "template $template"
    Assert-Absent @('compute','instance-groups','managed','describe',$mig,'--project',$Project,'--zone',$Zone,'--format=value(name)') "MIG $mig"
}
$existing = & gcloud storage ls "$prefix/**" 2>$null
if ($LASTEXITCODE -eq 0 -and @($existing).Count) { throw "GCS prefix already exists: $prefix" }

$gpuUtil = if ($ServingProfile -eq 'best-serving') { 0.965 } else { 0.96 }
$kvRequested = if ($ServingProfile -eq 'best-serving') { 'auto' } else { 'fp8' }
$clientWorkers = if ($Queued22) { 22 } else { 28 }
$perGameSeconds = $MaxRuntimePerGame
$exactCudaGraphs = $ServingProfile -eq 'best-serving'
$schedulerWatermark = if ($ServingProfile -eq 'best-serving') { 0.0 } else { $null }
$ompThreads = if ($ServingProfile -eq 'best-serving') { 1 } else { $null }
$actionCapState = if ($ActionCap -gt 0) { $ActionCap } else { $null }
$causalChanges = [Collections.Generic.List[string]]::new()
$causalChanges.Add("candidate bundle: $CandidateFeature")
if ($ChampionReflectionV3) {
    $causalChanges.Add('audited scored Kaggle RTDv12 harness semantics with the sole reasoning delta of guarded same-context Reflection V3 after every engine-verified level completion')
} elseif ($ChampionContextSweep) {
    $causalChanges.Add("audited scored Kaggle RTDv12 harness semantics with the sole context delta of max context $AnalyzerContextWindow tokens and fixed $PersistentHistoryAssistantTurns retained assistant turns")
} elseif ($visualToolkitArm) {
    $crossoverChange = if ($VisualToolkitMode -eq 'combined') {
        'metadata-only animation evidence plus optional CPU vision toolkit, bounded cache, persistent helpers, and compact advisory budget reminder'
    } else {
        'metadata-only animation evidence plus optional CPU vision toolkit, bounded cache, and persistent helpers; budget reminder absent'
    }
    $causalChanges.Add($crossoverChange)
} elseif ($visualTransitionArm) {
    $visualChange = switch ($VisualTransitionMode) {
        'control' { 'four-arm visual-transition control: exact champion model-facing prompts and evidence with all new evidence paths dormant' }
        'metadata' { 'compact multi-frame action/count/change/sample-position metadata before next reasoning; legacy ASCII storyboard and region tools retained' }
        'additive' { 'log2/cap8 uniformly sampled raw transition images before next reasoning; legacy ASCII storyboard and region tools retained' }
        'replace' { 'log2/cap8 uniformly sampled raw transition images before next reasoning, replacing model-facing ASCII storyboard, reminder prose, and region tools' }
    }
    $causalChanges.Add($visualChange)
} elseif ($toolkitMatrixArm) {
    $toolkitChange = switch ($ToolkitMatrixMode) {
        'control' { 'toolkit 2x2 control: byte-identical champion source with CPU toolkit and budget reminder absent' }
        'toolkit' { 'optional CPU vision toolkit, transparent bounded per-game cache, and persistent Python helper registry; budget reminder absent' }
        'reminder' { 'compact advisory per-request remaining-time and cumulative generated-token reminder; CPU toolkit and persistent helpers absent' }
        'combined' { 'optional CPU vision toolkit, bounded cache and persistent helpers plus compact advisory budget reminder' }
    }
    $causalChanges.Add($toolkitChange)
} elseif ($ChampionLongRun) {
    $causalChanges.Add('audited scored Kaggle RTDv12 baseline with the sole resource delta of 21600 seconds per game and a proportionally scaled 440-minute suite boundary')
} elseif ($exactKaggleSemantics) {
    $causalChanges.Add('audited scored Kaggle RTDv12 harness semantics; strict cumulative cap14, fixed30 history, and same-context reflection absent and dormant')
} elseif ($ReflectionV6) {
    $causalChanges.Add('guarded same-context Reflection V6 after every engine-verified level completion: thinking enabled with a 1536-token ceiling and one no-thinking 448-token recovery')
    $causalChanges.Add("whole-history context compaction at fraction $ContextTriggerFraction, zero raw turns retained, 1024-token ledger cap, and 50% emergency low-water trim")
} else {
    $causalChanges.Add('guarded same-context Reflection V3 after every engine-verified level completion')
}
if ($Stall140Only) {
    $causalChanges.Add('sole gameplay delta: abandon an unresolved level after 140 actions and release its worker slot')
}
if ($ChampionRefinement) {
    $causalChanges.Add('sole reasoning delta: route observably hard turns through one text-only medium draft, one independent text-only medium critic, and one xhigh action-capable revision; at most four multipass turns concurrently')
}
if ($exactKaggleSemantics) {
    $causalChanges.Add('episodic replay code and environment absent, matching the scored Kaggle winner')
} elseif ($DisableReplay) {
    $causalChanges.Add('episodic replay disabled; no replay lookup, replay reminder, or replay prompt injection')
} else {
    $causalChanges.Add("read-only episodic replay arm $ReplayArm with complete settled-event history and host-only usage telemetry")
    if ($ReplayArm -eq 'C') {
        $causalChanges.Add('one short model-visible replay reminder only when the current settled grid exactly repeats')
    }
}
if ($DisableCurator) {
    $causalChanges.Add('top-six GPU world-model curator disabled; no curator request stream and no curator prompt injection')
} else {
    $causalChanges.Add('top-six GPU world-model curator enabled with per-input injection')
}
if ($ResumeCompletedGames) {
    $causalChanges.Add('Spot recreation preserves completed games, restarts only in-flight games, and retains one fixed suite deadline')
}
if ($DynamicSlack) {
    $causalChanges.Add('dynamic fair-slack allocator: each early finish contributes 75% of unused baseline time to a shared pool, with at most 1200 extra seconds granted to a game')
}
if ($GoldenRuntimeImage) {
    $causalChanges.Add("provisioning-only acceleration: immutable golden runtime image $GoldenRuntimeImage; prior gameplay state cleared and cached model/package/container artifacts reused")
}
$causalChanges.Add("serving profile: $ServingProfile")
$causalChanges.Add("harness scheduling: $clientWorkers workers, one full-suite pass, $perGameSeconds seconds per game")
if ($ActionCap -gt 0) { $causalChanges.Add("cumulative per-model-turn action cap: $ActionCap") }
if ($PostLevelUncappedTurns -gt 0) {
    $causalChanges.Add("post-level uncapped action-bearing model turns: $PostLevelUncappedTurns")
}
if ($VerifiedQueue) {
    $causalChanges.Add('CPU-only expectation-checked action queues with exact two-step cycle interruption and a lossless delta ledger')
}
if ($VerifiedHudV2) {
    $causalChanges.Add('CPU-only per-level edge-cadence HUD mask for expectation counts and queue-cycle hashes')
}
if ($VerifiedHudV3) {
    $causalChanges.Add('stateful whole-game CPU HUD analyst with first-five, per-level, reset, and predictor-failure refreshes through a two-worker centralized FIFO')
}
if ($HypothesisLab) {
    $causalChanges.Add('shadow-only persistent per-game hypothesis tournament with canonical predicate deduplication, bounded replay scoring, and action-indexed incremental CPU checks')
}
if ($ColocatedHudCpu) {
    $causalChanges.Add("co-located CPU HUD server on loopback, pinned to logical CPUs $ColocatedHudCpuSet, CPU-only, low-share, and limited to 20 GiB RAM")
}

$state = [ordered]@{
    experiment="Flash-Next ARC3 matrix arm $ArmSlug"
    status='preparing'
    created_at=(Get-Date).ToUniversalTime().ToString('o')
    project=$Project
    zone=$Zone
    bucket=$Bucket
    run_id=$runId
    mig=$mig
    template=$template
    instance=if ($DirectInstance) { $instance } else { $null }
    deployment=if ($DirectInstance) { 'direct_spot_instance' } else { 'managed_instance_group' }
    prefix=$prefix
    source=[ordered]@{
        template=$SourceTemplate
        golden_runtime_image=if ($GoldenRuntimeImage) { $GoldenRuntimeImage } else { $null }
        golden_runtime_image_id=if ($GoldenRuntimeImage) { [string]$goldenImageInfo.id } else { $null }
        golden_runtime_source_disk=if ($GoldenRuntimeImage) { [string]$goldenImageInfo.sourceDisk } else { $null }
        startup_sha256=$ExpectedStartupSha
        bundle=$CandidateBundle
        bundle_md5=$CandidateBundleMd5
        runner=$CandidateRunner
        curator=$ExpectedCurator
        feature=$CandidateFeature
        base_bundle=$ExpectedBundle
        base_runner=$ExpectedRunner
        exact_kaggle_warmup_sha256=if ($exactKaggleSemantics) { $ExactKaggleWarmupSha } else { $null }
        context_warmup_sha256=if ($ReflectionV6) { $ContextWarmupSha } else { $null }
        base_runtime_object="$Bucket/code/arc3-code-tufa0.tgz"
        base_runtime_sha256='d6a3a6f98365b5dd58767d9882671c7839ad549c5b868f3f8ca7b3457c0f1d3b'
        runtime_overlay=if ($exactKaggleSemantics) { $null } else { [ordered]@{
            prompts_sha256=$RuntimeOverlayPromptsSha
            sandbox_sha256=$RuntimeOverlaySandboxSha
            tool_agent_sha256=$RuntimeOverlayToolAgentSha
        } }
    }
    model=[ordered]@{
        id=$ModelId
        revision=$ModelRevision
        source='gcs_verified_mirror'
        mirror_prefix=$ModelMirrorPrefix
        mirror_file_count=[int]$mirrorManifest.file_count
        mirror_total_bytes=[int64]$mirrorManifest.total_bytes
        checkpoint_bytes=135253622894
        container=$ContainerImage
        converter_object=$converterObject
        converter_sha256=$converterSha
        ple_storage=if ($ServingProfile -eq 'best-serving') { 'native FP8 CPU PLE with pinned runtime lookup patch' } else { 'FP8 checkpoint table deterministically dequantized to BF16 pinned CPU RAM' }
        ple_base_sha256=if ($ServingProfile -eq 'best-serving') { $ExpectedBasePleSha } else { $null }
        ple_patch_object=if ($ServingProfile -eq 'best-serving') { $PlePatchObject } else { $null }
        ple_patch_sha256=if ($ServingProfile -eq 'best-serving') { $PlePatchSha } else { $null }
        routed_experts='RadixArk NVFP4 unchanged'
    }
    serving=[ordered]@{
        max_num_seqs=22
        max_num_batched_tokens=6144
        max_model_len=$AnalyzerContextWindow
        profile=$ServingProfile
        gpu_memory_utilization=$gpuUtil
        kv_cache_requested=$kvRequested
        kv_cache_fallback='auto'
        exact_cuda_graphs=$exactCudaGraphs
        scheduler_watermark=$schedulerWatermark
        omp_threads=$ompThreads
        mtp=$false
        ple_cpu_offload=$true
        distributed_executor='mp'
    }
    harness=[ordered]@{
        prompt_variant=$CandidateFeature
        replay_enabled=(-not $DisableReplay)
        replay_arm=if ($DisableReplay) { $null } else { $ReplayArm }
        replay_trigger_reminder=((-not $DisableReplay) -and $ReplayArm -eq 'C')
        same_context_level_reflection=$reflectionVersion
        context_compaction_enabled=[bool]$ReflectionV6
        context_compaction_trigger_fraction=if ($ReflectionV6) { [double]$ContextTriggerFraction } else { $null }
        context_compaction_keep_assistant_turns=if ($ReflectionV6) { 0 } else { $null }
        context_compaction_max_tokens=if ($ReflectionV6) { 1024 } else { $null }
        context_trim_target_fraction=if ($ReflectionV6) { 0.5 } else { $null }
        exact_kaggle_champion=[bool]$ExactKaggleChampion
        champion_long_run=[bool]$ChampionLongRun
        stall140_only=[bool]$Stall140Only
        exact_kaggle_curator_ablation=[bool]$ExactKaggleCuratorAblation
        champion_reflection_v3=[bool]$ChampionReflectionV3
        champion_refinement=[bool]$ChampionRefinement
        champion_context_sweep=[bool]$ChampionContextSweep
        visual_transition_mode=if ($visualTransitionArm -or $visualToolkitArm) { $effectiveVisualTransitionMode } else { $null }
        toolkit_matrix_mode=if ($toolkitMatrixArm) { $ToolkitMatrixMode } else { $null }
        visual_toolkit_mode=if ($visualToolkitArm) { $VisualToolkitMode } else { $null }
        cpu_toolkit_enabled=$toolkitEnabledForRun
        budget_reminder_enabled=$reminderEnabledForRun
        visual_transition_frame_cap=if ($visualTransitionArm -or $visualToolkitArm) { 8 } else { $null }
        visual_transition_log_base=if ($visualTransitionArm -or $visualToolkitArm) { 2 } else { $null }
        visual_transition_slot=if ($visualTransitionArm -or $visualToolkitArm) { 'after action tool result, before next reasoning' } else { $null }
        reasoning_policy=if ($ChampionRefinement) { 'refinement' } else { $null }
        client_game_workers=$clientWorkers
        official_games=if ($GameSubset) { @($GameSubset -split ' ' | Where-Object { $_ }).Count } else { 25 }
        passes=1
        max_runtime_s_per_game=$perGameSeconds
        max_run_runtime_minutes=$MaxRunRuntimeMinutes
        dynamic_slack_enabled=[bool]$DynamicSlack
        dynamic_slack_grant_fraction=if ($DynamicSlack) { 0.75 } else { $null }
        dynamic_slack_max_extra_seconds=if ($DynamicSlack) { 1200 } else { $null }
        hard_lifetime_seconds=$hardLifetimeSeconds
        resume_completed_games=[bool]$ResumeCompletedGames
        resume_max_attempts=if ($ResumeCompletedGames) { 4 } else { 1 }
        cumulative_action_cap=$actionCapState
        post_level_uncapped_turns=$PostLevelUncappedTurns
        verified_queue_enabled=[bool]$VerifiedQueue
        verified_queue_loop_stop=[bool]$VerifiedQueue
        verified_queue_max_cycle=if ($VerifiedQueue) { 2 } else { $null }
        verified_queue_ledger=[bool]$VerifiedQueue
        verified_hud_v2=[bool]$VerifiedHudV2
        verified_hud_v3=[bool]$VerifiedHudV3
        hypothesis_lab_enabled=[bool]$HypothesisLab
        verified_hud_edge_depth=if ($VerifiedHudV2 -or $VerifiedHudV3) { 4 } else { $null }
        verified_hud_sample_frames=if ($VerifiedHudV3) { 5 } else { $null }
        hud_cpu_base_url=if ($VerifiedHudV3) { $HudCpuBaseUrl } else { $null }
        hud_cpu_model=if ($VerifiedHudV3) { 'deepseek-coder-v2-lite-q4km' } else { $null }
        hud_cpu_workers=if ($VerifiedHudV3) { 2 } else { $null }
        hud_cpu_colocated=[bool]$ColocatedHudCpu
        hud_cpu_cpuset=if ($ColocatedHudCpu) { $ColocatedHudCpuSet } else { $null }
        hud_cpu_memory_limit=if ($ColocatedHudCpu) { '20g' } else { $null }
        hud_cpu_installer_object=$colocatedHudInstallerObject
        hud_cpu_installer_sha256=$colocatedHudInstallerSha
        model_reasoning=$true
        analyzer_context_window=$AnalyzerContextWindow
        persistent_history_assistant_turns=$PersistentHistoryAssistantTurns
        analyzer_max_output=0
        influence_mode=if ($DisableCurator) { 'none' } else { 'gpu_world_model_curator' }
        max_entries=if ($DisableCurator) { 0 } else { 6 }
        curator_max_tokens=if ($DisableCurator) { 0 } else { 3600 }
    }
    causal_changes=@($causalChanges)
    startup_sha256=$startupSha
    target_size=0
}
$state | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $StatePath -Encoding utf8

$createdMig = $false
$createdInstance = $false
try {
    $props = (($source.properties | ConvertTo-Json -Depth 100) | ConvertFrom-Json)
    $props.metadata.PSObject.Properties.Remove('fingerprint')
    $props.metadata.PSObject.Properties.Remove('kind')
    $props.disks[0].initializeParams.diskSizeGb = '400'
    $items = [Collections.ArrayList]@($props.metadata.items)
    if ($GoldenRuntimeImage) {
        $props.disks[0].initializeParams.sourceImage = "https://www.googleapis.com/compute/v1/projects/$Project/global/images/$GoldenRuntimeImage"
        foreach ($driverItem in @($items | Where-Object key -eq 'install-nvidia-driver')) {
            [void]$items.Remove($driverItem)
        }
    }
    if ($ResumeCompletedGames) {
        $shutdownItem = @($items | Where-Object key -eq 'shutdown-script')
        if ($shutdownItem.Count -ne 1) { throw 'Shutdown-script metadata drift' }
        $shutdownItem[0].value = $resumeShutdownText
    }
    Set-OrAddMetadata $items 'arc3-run-id' $runId
    Set-OrAddMetadata $items 'arc3-mig' $mig
    Set-OrAddMetadata $items 'arc3-source-template' $SourceTemplate
    Set-OrAddMetadata $items 'arc3-bundle' $CandidateBundle
    Set-OrAddMetadata $items 'arc3-runner-object' $CandidateRunner
    Set-OrAddMetadata $items 'arc3-feature-arm' $CandidateFeature
    Set-OrAddMetadata $items 'arc3-influence-mode' $(if ($DisableCurator) { 'none' } else { 'gpu_world_model_curator' })
    Set-OrAddMetadata $items 'arc3-matrix-arm' $ArmSlug
    Set-OrAddMetadata $items 'arc3-serving-profile' $ServingProfile
    Set-OrAddMetadata $items 'arc3-model-mirror-prefix' $ModelMirrorPrefix
    if ($GoldenRuntimeImage) {
        Set-OrAddMetadata $items 'arc3-golden-runtime-image' $GoldenRuntimeImage
        Set-OrAddMetadata $items 'arc3-golden-runtime-image-id' ([string]$goldenImageInfo.id)
    }
    Set-OrAddMetadata $items 'arc3-converter-object' $converterObject
    if ($ServingProfile -eq 'best-serving') {
        Set-OrAddMetadata $items 'arc3-ple-patch-object' $PlePatchObject
        Set-OrAddMetadata $items 'arc3-ple-base-sha256' $ExpectedBasePleSha
        Set-OrAddMetadata $items 'arc3-ple-patch-sha256' $PlePatchSha
    }
    Set-OrAddMetadata $items 'arc3-score-observer-object' $scoreObserverObject
    Set-OrAddMetadata $items 'arc3-score-observer-sha256' $scoreObserverSha
    Set-OrAddMetadata $items 'arc3-serving-max-num-seqs' '22'
    Set-OrAddMetadata $items 'arc3-serving-max-num-batched-tokens' '6144'
    Set-OrAddMetadata $items 'arc3-analyzer-context-window' ([string]$AnalyzerContextWindow)
    Set-OrAddMetadata $items 'arc3-persistent-history-assistant-turns' ([string]$PersistentHistoryAssistantTurns)
    if ($ActionCap -gt 0) { Set-OrAddMetadata $items 'arc3-action-cap' ([string]$ActionCap) }
    Set-OrAddMetadata $items 'arc3-post-level-uncapped-turns' ([string]$PostLevelUncappedTurns)
    if ($VerifiedQueue) {
        Set-OrAddMetadata $items 'arc3-verified-queue' 'cpu-v1'
    }
    if ($VerifiedHudV2) {
        Set-OrAddMetadata $items 'arc3-verified-hud-mask' 'edge-cadence-v2'
    }
    if ($VerifiedHudV3) {
        Set-OrAddMetadata $items 'arc3-verified-hud-mask' 'stateful-cpu-model-v3'
        Set-OrAddMetadata $items 'arc3-hud-cpu-base-url' $HudCpuBaseUrl
        Set-OrAddMetadata $items 'arc3-hud-cpu-model' 'deepseek-coder-v2-lite-q4km'
    }
    if ($ColocatedHudCpu) {
        Set-OrAddMetadata $items 'arc3-hud-cpu-mode' 'colocated-loopback'
        Set-OrAddMetadata $items 'arc3-hud-cpu-cpuset' $ColocatedHudCpuSet
        Set-OrAddMetadata $items 'arc3-hud-installer-object' $colocatedHudInstallerObject
        Set-OrAddMetadata $items 'arc3-hud-installer-sha256' $colocatedHudInstallerSha
    }
    if ($Queued22) {
        Set-OrAddMetadata $items 'arc3-harness-concurrency' '22'
    }
    Set-OrAddMetadata $items 'arc3-replay-enabled' $(if ($DisableReplay) { '0' } else { '1' })
    Set-OrAddMetadata $items 'arc3-replay-arm' $(if ($DisableReplay) { 'none' } else { $ReplayArm })
    Set-OrAddMetadata $items 'arc3-replay-trigger-reminder' $(if (!$DisableReplay -and $ReplayArm -eq 'C') { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-same-context-level-reflection' $reflectionVersion
    Set-OrAddMetadata $items 'arc3-context-compaction-enabled' $(if ($ReflectionV6) { '1' } else { '0' })
    if ($ReflectionV6) {
        Set-OrAddMetadata $items 'arc3-context-compaction-trigger-fraction' $ContextTriggerFraction
        Set-OrAddMetadata $items 'arc3-context-compaction-keep-assistant-turns' '0'
    }
    Set-OrAddMetadata $items 'arc3-exact-kaggle-champion' $(if ($ExactKaggleChampion) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-champion-long-run' $(if ($ChampionLongRun) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-stall140-only' $(if ($Stall140Only) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-exact-kaggle-curator-ablation' $(if ($ExactKaggleCuratorAblation) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-champion-reflection-v3' $(if ($ChampionReflectionV3) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-champion-refinement' $(if ($ChampionRefinement) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-champion-context-sweep' $(if ($ChampionContextSweep) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-visual-transition-mode' $(if ($visualTransitionArm -or $visualToolkitArm) { $effectiveVisualTransitionMode } else { 'none' })
    Set-OrAddMetadata $items 'arc3-toolkit-matrix-mode' $(if ($toolkitMatrixArm) { $ToolkitMatrixMode } else { 'none' })
    Set-OrAddMetadata $items 'arc3-visual-toolkit-mode' $(if ($visualToolkitArm) { $VisualToolkitMode } else { 'none' })
    Set-OrAddMetadata $items 'arc3-cpu-toolkit-enabled' $(if ($toolkitEnabledForRun) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-budget-reminder-enabled' $(if ($reminderEnabledForRun) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-reasoning-policy' $(if ($ChampionRefinement) { 'refinement' } else { 'baseline' })
    Set-OrAddMetadata $items 'arc3-curator-enabled' $(if ($DisableCurator) { '0' } else { '1' })
    Set-OrAddMetadata $items 'arc3-resume-completed-games' $(if ($ResumeCompletedGames) { '1' } else { '0' })
    Set-OrAddMetadata $items 'arc3-max-runtime-s-per-game' ([string]$MaxRuntimePerGame)
    Set-OrAddMetadata $items 'arc3-dynamic-slack-enabled' $(if ($DynamicSlack) { '1' } else { '0' })
    if ($DynamicSlack) {
        Set-OrAddMetadata $items 'arc3-dynamic-slack-grant-fraction' '0.75'
        Set-OrAddMetadata $items 'arc3-dynamic-slack-max-extra-seconds' '1200'
    }
    if ($GameSubset) { Set-OrAddMetadata $items 'arc3-game-subset' $GameSubset }
    Set-OrAddMetadata $items 'startup-script' $startup
    $props.metadata.items = $items
    foreach ($disk in @($props.disks)) {
        $disk.PSObject.Properties.Remove('index')
        $disk.PSObject.Properties.Remove('kind')
    }
    foreach ($nic in @($props.networkInterfaces)) {
        $nic.PSObject.Properties.Remove('kind')
        $nic.PSObject.Properties.Remove('name')
        foreach ($access in @($nic.accessConfigs)) { $access.PSObject.Properties.Remove('kind') }
    }

    if ($DirectInstance) {
        if ($props.machineType -notmatch '/') {
            $props.machineType = "projects/$Project/zones/$Zone/machineTypes/$($props.machineType)"
        }
        foreach ($disk in @($props.disks)) {
            if ($disk.initializeParams.diskType -and $disk.initializeParams.diskType -notmatch '/') {
                $disk.initializeParams.diskType = "projects/$Project/zones/$Zone/diskTypes/$($disk.initializeParams.diskType)"
            }
        }
        $props | Add-Member -NotePropertyName name -NotePropertyValue $instance -Force
        $operation = Invoke-GcpJsonPost `
            "https://compute.googleapis.com/compute/v1/projects/$Project/zones/$Zone/instances" `
            ($props | ConvertTo-Json -Depth 100 -Compress)
        Wait-ZonalOperation $operation.name $Zone
        $createdInstance = $true
    } else {
        $operation = Invoke-GcpJsonPost `
            "https://compute.googleapis.com/compute/v1/projects/$Project/global/instanceTemplates" `
            ([ordered]@{name=$template;properties=$props} | ConvertTo-Json -Depth 100 -Compress)
        Wait-GlobalOperation $operation.name
        Invoke-Gcloud @('compute','instance-groups','managed','create',$mig,'--project',$Project,'--zone',$Zone,'--base-instance-name',$mig,'--size','0','--template',$template) | Out-Null
        $createdMig = $true
        Invoke-Gcloud @('compute','instance-groups','managed','resize',$mig,'--project',$Project,'--zone',$Zone,'--size','1') | Out-Null
    }
    Invoke-Gcloud @('storage','cp',$StatePath,"$prefix/LAUNCH_STATE.json") | Out-Null
    $state.status='launched'
    $state.launched_at=(Get-Date).ToUniversalTime().ToString('o')
    $state.target_size=1
    $state | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $StatePath -Encoding utf8
    Invoke-Gcloud @('storage','cp',$StatePath,"$prefix/LAUNCH_STATE.json") | Out-Null
    $state | ConvertTo-Json -Depth 30
} catch {
    if ($createdInstance) {
        & gcloud compute instances delete $instance --project $Project --zone $Zone --quiet *> $null
    }
    if ($createdMig) {
        & gcloud compute instance-groups managed resize $mig --project $Project --zone $Zone --size 0 *> $null
    }
    $state.status=if ($DirectInstance) { 'launch_failed_owned_instance_deleted' } else { 'launch_failed_owned_mig_forced_zero' }
    $state.error=$_.Exception.Message
    $state | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $StatePath -Encoding utf8
    throw
}

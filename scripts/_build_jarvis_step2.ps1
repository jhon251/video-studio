# JARVIS build step 2: TTS voiceover via Windows System.Speech (offline)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$manifest = Get-Content 'output\production_002\build\manifest.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('Microsoft Huihui Desktop')
$synth.Rate = -1
$synth.Volume = 100
$count = 0
foreach ($m in $manifest) {
  $narration = ($m.narration | Out-String).Trim()
  if (-not $narration -or $m.role -eq 'fact' -or $m.role -eq 'gap') { continue }
  $out = Join-Path 'output\production_002\build\wav' ($m.scene_id + '.wav')
  $synth.SetOutputToWaveFile($out)
  $synth.Speak($narration)
  $synth.SetOutputToNull()
  $count++
  Write-Output ("TTS {0} ok (len={1})" -f $m.scene_id, $narration.Length)
}
$synth.Dispose()
Write-Output ("TTS done: {0} scenes" -f $count)

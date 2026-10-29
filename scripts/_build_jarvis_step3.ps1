# JARVIS build step 3 (v3): render scene cards + mux TTS -> final MP4
$ErrorActionPreference = 'Continue'
$root = 'output\production_002\build'
$manifest = Get-Content "$root\manifest.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$ff = (Resolve-Path 'bin\ffmpeg.exe').Path
$font = 'C\:/Windows/Fonts/msyh.ttc'

function Get-WavDuration([string]$path) {
  $bytes = [System.IO.File]::ReadAllBytes($path)
  if ($bytes.Length -lt 44) { return 5.0 }
  $byteRate = [BitConverter]::ToInt32($bytes, 28)
  $dataSize = [BitConverter]::ToInt32($bytes, 40)
  if ($byteRate -le 0) { return 5.0 }
  return [math]::Round($dataSize / $byteRate, 2)
}

$list = @()
$log = Join-Path $root 'ffmpeg.log'
if (Test-Path $log) { Remove-Item $log }

foreach ($m in $manifest) {
  $sid = $m.scene_id
  $bg = $m.bg
  $beat = (($m.beat | Out-String).Trim()) -replace "'", ''
  $wav = Join-Path $root ("wav\" + $sid + '.wav')
  $txtRel = $m.txt.Replace('\', '/')
  $mp4 = Join-Path $root ("scene_" + $sid + '.mp4')

  if (Test-Path $wav) {
    $dur = (Get-WavDuration $wav) + 0.6
    $aIn = $wav
  } else {
    $dh = $m.duration_hint -replace '[^0-9.]', ''
    $dur = if ($dh) { [double]$dh } else { 6 }
    $aIn = $null
  }
  $dur = [math]::Round($dur, 2)

  # vf：两张卡片文本（beat 标题 + 口播/字幕正文），textfile 用正斜杠相对路径
  $vf = "drawtext=fontfile=$font`:text='$beat'`:fontsize=38`:fontcolor=0x9aa5b1`:x=(w-text_w)/2`:y=56,drawtext=fontfile=$font`:textfile=$txtRel`:fontsize=32`:fontcolor=white`:x=(w-text_w)/2`:y=(h-text_h)/2`:line_spacing=16"

  if ($aIn) {
    & $ff -hide_banner -loglevel error -y -f lavfi -i "color=c=$bg`:s=1280x720`:r=25`:d=$dur" -i $wav -vf $vf -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest $mp4 *>> $log
  } else {
    & $ff -hide_banner -loglevel error -y -f lavfi -i "color=c=$bg`:s=1280x720`:r=25`:d=$dur" -f lavfi -i "anullsrc=r=44100`:cl=stereo" -vf $vf -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest $mp4 *>> $log
  }
  if (Test-Path $mp4) {
    $list += "file '$mp4'"
    Write-Output ("render {0} dur={1}s OK" -f $sid, $dur)
  } else {
    Write-Output ("render {0} FAILED" -f $sid)
  }
}

$listFile = Join-Path $root 'concat.txt'
Set-Content -Path $listFile -Value $list -Encoding ASCII
$final = 'output\production_002\JARVIS_final.mp4'
& $ff -hide_banner -loglevel error -y -f concat -safe 0 -i $listFile -c copy $final *>> $log
if (Test-Path $final) {
  $sz = [math]::Round((Get-Item $final).Length / 1MB, 2)
  Write-Output ("FINAL OK: {0} ({1} MB)" -f $final, $sz)
} else {
  Write-Output "FINAL FAILED - see ffmpeg.log"
}

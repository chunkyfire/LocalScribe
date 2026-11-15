# Spricht jede Zeile aus saetze.txt mit der deutschen Windows-Stimme in eine eigene WAV-Datei (16 kHz mono).
param([string]$Dir)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$de = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'de*' } | Select-Object -First 1
$s.SelectVoice($de.VoiceInfo.Name)
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$i = 0
foreach ($line in [IO.File]::ReadAllLines("$Dir\saetze.txt", [Text.Encoding]::UTF8)) {
    $i++
    $s.SetOutputToWaveFile(("{0}\s{1:D4}.wav" -f $Dir, $i), $fmt)
    $s.Speak($line)
}
$s.SetOutputToNull()
"fertig $i" | Set-Content "$Dir\tts_fertig.txt"

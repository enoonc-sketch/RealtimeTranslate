# Windows 自带 OCR：Windows.Media.Ocr（Photos 应用用的同一个引擎）。
# 只能用 Windows PowerShell 5.1（powershell.exe）跑，PowerShell 7 不支持 WinRT。
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File winocr.ps1 -Path 图片.bmp [-Language en-US] [-Json]
#   默认输出识别到的每一行文字；-Json 输出 {"lines":[{"text":...,"words":[{"text":..,"x":..,"y":..,"w":..,"h":..}]}]}
# 做法参考 HumanEquivalentUnit/PowerShell-Misc 的 Get-Win10OcrTextFromImage.ps1（MIT 思路的公开写法）。
[CmdletBinding()]
Param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateNotNullOrEmpty()]
    [string]$Path,
    [string]$Language,
    [switch]$Json
)

if ($PSVersionTable.PSVersion.Major -ne 5) {
    throw "截图 OCR 需要 Windows PowerShell 5.1（powershell.exe），当前是 PowerShell $($PSVersionTable.PSVersion)，它不支持 WinRT OCR。"
}
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Foundation.IAsyncOperation`1, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.RandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]

# WinRT 方法全是异步的，PowerShell 里用 GetAwaiter 等它完成。
$getAwaiterBaseMethod = [WindowsRuntimeSystemExtensions].GetMember('GetAwaiter').Where({ $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }, 'First')[0]
function Await($AsyncTask, $ResultType) {
    $getAwaiterBaseMethod.MakeGenericMethod($ResultType).Invoke($null, @($AsyncTask)).GetResult()
}

# 选 OCR 语言：指定了就按指定的来，没有 / 不支持就按系统语言，最后用第一个可用的。
$ocrEngine = $null
if ($Language) {
    try {
        $langObj = [Windows.Globalization.Language]::new($Language)
        $ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($langObj)
    } catch { $ocrEngine = $null }
}
if ($null -eq $ocrEngine) {
    $ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if ($null -eq $ocrEngine) {
    $langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
    if ($langs.Count -gt 0) {
        $ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($langs[0])
    }
}
if ($null -eq $ocrEngine) {
    throw "本机没有可用的 OCR 语言。请在 Windows 设置里安装 OCR 语言包（设置 → 语言 → 添加语言，或 PowerShell 执行 Get-WindowsCapability -Online | Where-Object Name -like 'Language.OCR*')。"
}

$p = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
$storageFile = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
$fileStream = Await $storageFile.OpenAsync([Windows.Storage.FileAccessMode]::Read) ([Windows.Storage.Streams.IRandomAccessStream])
$bitmapDecoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($fileStream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$softwareBitmap = Await $bitmapDecoder.GetSoftwareBitmapAsync() ([Windows.Graphics.Imaging.SoftwareBitmap])
if ($softwareBitmap.BitmapPixelFormat -ne [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8) {
    $softwareBitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert($softwareBitmap, [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8)
}

$result = Await $ocrEngine.RecognizeAsync($softwareBitmap) ([Windows.Media.Ocr.OcrResult])

if ($Json) {
    $lines = @()
    foreach ($line in $result.Lines) {
        $words = @()
        foreach ($word in $line.Words) {
            $r = $word.BoundingRect
            $words += @{ text = $word.Text; x = [int]$r.X; y = [int]$r.Y; w = [int]$r.Width; h = [int]$r.Height }
        }
        $lines += @{ text = $line.Text; words = $words }
    }
    @{ lines = $lines } | ConvertTo-Json -Depth 5 -Compress
} else {
    foreach ($line in $result.Lines) { $line.Text }
}

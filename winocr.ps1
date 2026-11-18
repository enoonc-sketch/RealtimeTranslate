# Windows built-in OCR (Windows.Media.Ocr, the engine used by the Photos app).
# IMPORTANT: this file is pure ASCII on purpose. Windows PowerShell 5.1 reads a .ps1 without a BOM
# using the system ANSI code page (GBK on Chinese Windows), so any UTF-8 Chinese text in here can
# swallow a closing quote and break the whole script (v2.12 and earlier). Error messages are
# therefore short ASCII codes ("OCR_xxx: ..."); the Python side (ocr_win.py) turns them into Chinese.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File winocr.ps1 -Path img.bmp [-Language en-US|auto] [-Json]
#   default: one recognized line per output line
#   -Json  : {"lines":[{"text":..,"words":[{"text":..,"x":..,"y":..,"w":..,"h":..}]}]}
[CmdletBinding()]
Param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateNotNullOrEmpty()]
    [string]$Path,
    [string]$Language,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -ne 5) {
    throw "OCR_PS_VERSION: need Windows PowerShell 5.1 (powershell.exe), got $($PSVersionTable.PSVersion)"
}
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Foundation.IAsyncOperation`1, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapTransform, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.ExifOrientationMode, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.ColorManagementMode, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Storage.Streams.RandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
    $null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
    $null = [Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime]
} catch {
    throw "OCR_WINRT: cannot load WinRT OCR types: $($_.Exception.Message)"
}

# WinRT calls are async; wait for them with GetAwaiter.
$getAwaiterBaseMethod = [WindowsRuntimeSystemExtensions].GetMember('GetAwaiter').Where({ $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }, 'First')[0]
function Await($AsyncTask, $ResultType) {
    $getAwaiterBaseMethod.MakeGenericMethod($ResultType).Invoke($null, @($AsyncTask)).GetResult()
}

# ---- pick OCR engines -------------------------------------------------------
# Requested language (exact tag, then any installed language with the same primary tag) ->
# user profile languages -> every installed OCR language.
# "auto" / empty: try the profile engine AND English (when installed) and keep whichever reads more,
# because a Chinese-only engine reads English poorly and vice versa.
function New-Engine($tag) {
    try {
        $l = New-Object Windows.Globalization.Language($tag)
        return [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($l)
    } catch { return $null }
}
function Find-Engine($want) {
    $e = New-Engine $want
    if ($e) { return $e }
    $prim = ($want -split '-')[0].ToLower()
    foreach ($l in [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages) {
        if (($l.LanguageTag -split '-')[0].ToLower() -eq $prim) {
            $e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($l)
            if ($e) { return $e }
        }
    }
    return $null
}

$engines = @()
$auto = (-not $Language) -or ($Language -eq 'auto')
if (-not $auto) {
    $e = Find-Engine $Language
    if ($e) { $engines += $e }
}
if ($engines.Count -eq 0) {
    $e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($e) { $engines += $e }
    if ($auto) {
        $en = Find-Engine 'en-US'
        if ($en -and (-not $e -or $en.RecognizerLanguage.LanguageTag -ne $e.RecognizerLanguage.LanguageTag)) { $engines += $en }
    }
}
if ($engines.Count -eq 0) {
    foreach ($l in [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages) {
        $e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($l)
        if ($e) { $engines += $e; break }
    }
}
if ($engines.Count -eq 0) {
    throw "OCR_NO_LANG: no OCR language installed"
}

# ---- load the image as Bgra8 / alpha ignored ---------------------------------
# Alpha is ignored on purpose: GDI screenshots carry alpha = 0, which would otherwise be read as a fully
# transparent (blank) image and OCR would find nothing.
try {
    $p = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    $storageFile = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
    $fileStream = Await $storageFile.OpenAsync([Windows.Storage.FileAccessMode]::Read) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($fileStream)) ([Windows.Graphics.Imaging.BitmapDecoder])
} catch {
    throw "OCR_IMAGE: cannot open or decode the image: $($_.Exception.Message)"
}

$maxDim = [int][Windows.Media.Ocr.OcrEngine]::MaxImageDimension
$scale = 1.0
$bmp = $null
try {
    $bigSide = [Math]::Max([int]$decoder.PixelWidth, [int]$decoder.PixelHeight)
    if ($maxDim -gt 0 -and $bigSide -gt $maxDim) {
        # Larger than the engine accepts: shrink to fit instead of failing.
        $scale = [double]$maxDim / [double]$bigSide
        $tf = New-Object Windows.Graphics.Imaging.BitmapTransform
        $tf.ScaledWidth = [uint32][Math]::Max(1, [Math]::Floor($decoder.PixelWidth * $scale))
        $tf.ScaledHeight = [uint32][Math]::Max(1, [Math]::Floor($decoder.PixelHeight * $scale))
        $bmp = Await ($decoder.GetSoftwareBitmapAsync(
            [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
            [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore,
            $tf,
            [Windows.Graphics.Imaging.ExifOrientationMode]::RespectExifOrientation,
            [Windows.Graphics.Imaging.ColorManagementMode]::DoNotColorManage)) ([Windows.Graphics.Imaging.SoftwareBitmap])
    } else {
        $bmp = Await ($decoder.GetSoftwareBitmapAsync(
            [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
            [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore)) ([Windows.Graphics.Imaging.SoftwareBitmap])
    }
} catch {
    # Fallback: plain decode + convert.
    try {
        $bmp = Await $decoder.GetSoftwareBitmapAsync() ([Windows.Graphics.Imaging.SoftwareBitmap])
        if ($bmp.BitmapPixelFormat -ne [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8 -or
            $bmp.BitmapAlphaMode -ne [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore) {
            $bmp = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert($bmp,
                [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
                [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore)
        }
        $scale = 1.0
    } catch {
        throw "OCR_IMAGE: cannot convert the image: $($_.Exception.Message)"
    }
}

# ---- recognize; with several engines keep the one that read the most ----------
$best = $null
$bestScore = -1
foreach ($eng in $engines) {
    try {
        $r = Await ($eng.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
    } catch { continue }
    $score = 0
    foreach ($ln in $r.Lines) { $score += ($ln.Text -replace '\s', '').Length }
    if ($score -gt $bestScore) { $best = $r; $bestScore = $score }
}
if ($null -eq $best) {
    throw "OCR_RECOGNIZE: recognition failed"
}

$inv = 1.0 / $scale
if ($Json) {
    $lines = @()
    foreach ($line in $best.Lines) {
        $words = @()
        foreach ($word in $line.Words) {
            $r = $word.BoundingRect
            $words += @{ text = $word.Text; x = [int]($r.X * $inv); y = [int]($r.Y * $inv); w = [int]($r.Width * $inv); h = [int]($r.Height * $inv) }
        }
        $lines += @{ text = $line.Text; words = $words }
    }
    @{ lines = $lines } | ConvertTo-Json -Depth 5 -Compress
} else {
    foreach ($line in $best.Lines) { $line.Text }
}

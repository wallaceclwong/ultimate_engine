$targets = @("hkjc", "weathernext_pro", "Options-Brain")
$exclude = "ultimate_engine"

$processes = Get-CimInstance Win32_Process
foreach ($p in $processes) {
    if ($null -ne $p.CommandLine) {
        $match = $false
        foreach ($t in $targets) {
            if ($p.CommandLine -like "*$t*") {
                $match = $true
                break
            }
        }
        if ($match -and ($p.CommandLine -notlike "*$exclude*")) {
            Write-Host "Killing Process ID: $($p.ProcessId) - $($p.CommandLine)"
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}
Write-Host "Service termination complete."

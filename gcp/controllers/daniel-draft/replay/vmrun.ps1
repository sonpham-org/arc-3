# vmrun.ps1 <vm> <zone> <local script>: copy a bash script to the VM and run it with sudo (avoids cmd.exe quoting)
param([string]$vm, [string]$zone, [string]$script)
$env:CLOUDSDK_PYTHON = 'C:\python312\python.exe'
$lf = "$script.lf"
[IO.File]::WriteAllText($lf, ([IO.File]::ReadAllText($script) -replace "`r", ""))
'y' | gcloud.cmd compute scp $lf "$($vm):/tmp/vmrun.sh" --zone $zone 2>&1 | Out-Null
'y' | gcloud.cmd compute ssh $vm --zone $zone --command "sudo bash /tmp/vmrun.sh" 2>&1

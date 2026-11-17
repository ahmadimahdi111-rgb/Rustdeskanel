param([switch]$InstallTask)
$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
[Net.ServicePointManager]::ServerCertificateValidationCallback={param($s,$c,$ch,$e) return ($c.Subject -eq 'CN=172.16.2.99')}
$dir=Join-Path $env:APPDATA 'HCU-Remote-Agent';$cfgPath=Join-Path $dir 'agent.json'
if(-not(Test-Path $cfgPath)){
 New-Item -ItemType Directory -Force $dir|Out-Null
 $key=Read-Host 'کلید Agent را از پنل مدیر وارد کن'
 if(-not $key){throw 'کلید لازم است'}
 @{server='https://172.16.2.99:8765';key=$key.Trim()}|ConvertTo-Json|Set-Content -Encoding UTF8 $cfgPath
}
if($InstallTask){
 $exe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
 $args='-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$PSCommandPath+'"'
 $action=New-ScheduledTaskAction -Execute $exe -Argument $args
 $trigger=New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
 $principal=New-ScheduledTaskPrincipal -UserId ($env:USERDOMAIN+'\'+$env:USERNAME) -LogonType Interactive -RunLevel Highest
 Register-ScheduledTask -TaskName 'HCU RustDesk Device Agent' -Action $action -Trigger $trigger -Principal $principal -Force|Out-Null
 Start-ScheduledTask -TaskName 'HCU RustDesk Device Agent'
 Write-Host 'Agent در ورودهای بعدی خودکار اجرا می‌شود.';exit
}
$cfg=Get-Content $cfgPath -Raw|ConvertFrom-Json
$rd=(Get-Command rustdesk.exe -ErrorAction SilentlyContinue).Source
if(-not $rd){foreach($p in @("$env:ProgramFiles\RustDesk\rustdesk.exe","${env:ProgramFiles(x86)}\RustDesk\rustdesk.exe","$env:LOCALAPPDATA\RustDesk\rustdesk.exe")){if(Test-Path $p){$rd=$p;break}}}
if(-not $rd){throw 'RustDesk نصب‌شده پیدا نشد'}
while($true){
 try{
  $id=(& $rd --get-id 2>&1|Out-String).Trim()
  $ipcfg=Get-NetIPConfiguration|Where-Object {$_.IPv4DefaultGateway -and $_.IPv4Address}|Select-Object -First 1
  if(-not $ipcfg){$ipcfg=Get-NetIPConfiguration|Where-Object {$_.IPv4Address}|Select-Object -First 1}
  $ip=if($ipcfg){$ipcfg.IPv4Address.IPAddress}else{'نامشخص'}
  $body=@{target_id=$id;name=$env:COMPUTERNAME;ip=$ip}|ConvertTo-Json -Compress
  Invoke-RestMethod -Uri ($cfg.server+'/api/agent/heartbeat') -Method Post -Headers @{Authorization="Bearer $($cfg.key)"} -ContentType 'application/json' -Body $body -TimeoutSec 15|Out-Null
 }catch{Write-Warning $_.Exception.Message}
 Start-Sleep -Seconds 300
}

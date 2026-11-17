# 用法: powershell -ExecutionPolicy Bypass -File get_last_reply.ps1 -Conversation "智能体自进化实验规模" -Out reply.md
# 读取 ChatGPT 桌面客户端当前打开对话的最后一条 assistant 回答（通过"复制"按钮取 Markdown，结束后恢复原剪贴板文本）
param([string]$Conversation='智能体自进化实验规模',[Parameter(Mandatory=$true)][string]$Out)
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Windows.Forms
$A=[System.Windows.Automation.AutomationElement]; $TS=[System.Windows.Automation.TreeScope]; $CT=[System.Windows.Automation.ControlType]
function PC($p,$v){ New-Object System.Windows.Automation.PropertyCondition($p,$v) }
$w=$A::RootElement.FindFirst($TS::Children,(PC $A::NameProperty 'ChatGPT'))
if(-not $w){ throw 'ChatGPT window not found' }
$doc=$w.FindFirst($TS::Descendants,(New-Object System.Windows.Automation.AndCondition((PC $A::ControlTypeProperty $CT::Document),(PC $A::AutomationIdProperty 'RootWebArea'))))
if(-not $doc){ throw 'WebView document not found (window minimized?)' }
if($doc.Current.Name -ne $Conversation){ throw ('Open conversation is "'+$doc.Current.Name+'", expected "'+$Conversation+'"') }
$stop=$doc.FindFirst($TS::Descendants,(PC $A::NameProperty '停止流式传输'))
if($stop){ Write-Output 'STATUS=GENERATING'; exit 2 }
$btns=$doc.FindAll($TS::Descendants,(New-Object System.Windows.Automation.AndCondition((PC $A::ControlTypeProperty $CT::Button),(PC $A::NameProperty '复制'))))
if($btns.Count -eq 0){ throw 'no 复制 button' }
$b=$btns[$btns.Count-1]
$old=$null; try{ if([System.Windows.Forms.Clipboard]::ContainsText()){ $old=[System.Windows.Forms.Clipboard]::GetText() } }catch{}
[System.Windows.Forms.Clipboard]::SetText('__GPT_BRIDGE_SENTINEL__')
$b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
$txt=$null; foreach($i in 1..20){ Start-Sleep -Milliseconds 300; $t=[System.Windows.Forms.Clipboard]::GetText(); if($t -and $t -ne '__GPT_BRIDGE_SENTINEL__'){ $txt=$t; break } }
if($old -ne $null){ [System.Windows.Forms.Clipboard]::SetText($old) } else { [System.Windows.Forms.Clipboard]::Clear() }
if(-not $txt){ throw 'clipboard copy failed' }
[System.IO.File]::WriteAllText($Out,$txt,(New-Object System.Text.UTF8Encoding($false)))
Write-Output ('STATUS=OK chars='+$txt.Length)
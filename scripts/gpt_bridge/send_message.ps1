# 用法: powershell -STA -ExecutionPolicy Bypass -File send_message.ps1 -Conversation "智能体自进化实验规模" -TextFile msg.md [-Project "Agent Self-Evolution"]
# 打开侧栏中指定对话 -> 确认输入框为空 -> 剪贴板粘贴 -> 点击发送（只发一次）-> 恢复原剪贴板文本。
# 发送后用 get_last_reply.ps1 轮询取回答（返回 exit 2 表示仍在生成）。
# 注意：截至 2026-11-10 此脚本尚未实际执行过发送（本轮用户已手动发送），首次使用请人工盯一下。
param([Parameter(Mandatory=$true)][string]$Conversation,[Parameter(Mandatory=$true)][string]$TextFile,[string]$Project='Agent Self-Evolution')
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W2 { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);}
"@
$A=[System.Windows.Automation.AutomationElement]; $TS=[System.Windows.Automation.TreeScope]; $CT=[System.Windows.Automation.ControlType]
function PC($p,$v){ New-Object System.Windows.Automation.PropertyCondition($p,$v) }
function AndC($a,$b){ New-Object System.Windows.Automation.AndCondition($a,$b) }
$text=[System.IO.File]::ReadAllText($TextFile,[System.Text.Encoding]::UTF8)
if([string]::IsNullOrWhiteSpace($text)){ throw 'empty text file' }
$proc=Get-Process ChatGPT | ? { $_.MainWindowTitle -eq 'ChatGPT' } | Select -First 1
if(-not $proc){ throw 'ChatGPT window not found' }
$h=$proc.MainWindowHandle; if([W2]::IsIconic($h)){ [W2]::ShowWindow($h,9)|Out-Null }; [W2]::SetForegroundWindow($h)|Out-Null; Start-Sleep 2
$w=$A::RootElement.FindFirst($TS::Children,(PC $A::NameProperty 'ChatGPT'))
function GetDoc { $w.FindFirst($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Document) (PC $A::AutomationIdProperty 'RootWebArea'))) }
$doc=$null; foreach($i in 1..10){ $doc=GetDoc; if($doc){break}; Start-Sleep 1 }
if(-not $doc){ throw 'WebView document not accessible' }
if($doc.Current.Name -ne $Conversation){
  $items=$doc.FindAll($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Button) (PC $A::NameProperty $Conversation)))
  if($items.Count -lt 1){ throw "sidebar item '$Conversation' not found (project '$Project' collapsed?)" }
  if($items.Count -gt 1){ Write-Output "WARN: $($items.Count) buttons named '$Conversation'; using first" }
  $items[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); Start-Sleep 3
  $doc=GetDoc; if($doc.Current.Name -ne $Conversation){ throw ('after click, open conversation is "'+$doc.Current.Name+'"') }
}
$edit=$doc.FindFirst($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Edit) (PC $A::ClassNameProperty 'ProseMirror')))
if(-not $edit){ throw 'composer not found' }
$ph=$edit.FindFirst($TS::Descendants,(PC $A::ClassNameProperty 'placeholder'))
if(-not $ph){ throw 'composer is NOT empty (user may be typing) - abort' }
$old=$null; try{ if([System.Windows.Forms.Clipboard]::ContainsText()){ $old=[System.Windows.Forms.Clipboard]::GetText() } }catch{}
[System.Windows.Forms.Clipboard]::SetText($text)
$edit.SetFocus(); Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait('^v'); Start-Sleep 3
$ph2=$edit.FindFirst($TS::Descendants,(PC $A::ClassNameProperty 'placeholder'))
if($old -ne $null){ [System.Windows.Forms.Clipboard]::SetText($old) }
if($ph2){ throw 'paste failed: composer still empty' }
$sendBtn=$doc.FindFirst($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Button) (PC $A::NameProperty '发送')))
if(-not $sendBtn){ throw 'send button not found (content pasted but NOT sent)' }
$sendBtn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
Write-Output ('STATUS=SENT chars='+$text.Length+' at '+(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
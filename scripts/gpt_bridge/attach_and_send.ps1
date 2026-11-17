# Attach files to ChatGPT composer, optionally send. STA required.
param(
  [string[]]$Files,
  [string]$Text = '',
  [switch]$Send,
  [string]$Conversation = '智能体自进化实验规模'
)
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W3 { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);}
"@
$A=[System.Windows.Automation.AutomationElement]; $TS=[System.Windows.Automation.TreeScope]; $CT=[System.Windows.Automation.ControlType]
function PC($p,$v){ New-Object System.Windows.Automation.PropertyCondition($p,$v) }
function AndC($a,$b){ New-Object System.Windows.Automation.AndCondition($a,$b) }
function Log($m){ Write-Output ((Get-Date -Format 'HH:mm:ss') + ' ' + $m) }

foreach($f in $Files){ if(-not (Test-Path -LiteralPath $f)){ throw "missing file: $f" } }

$proc=Get-Process ChatGPT | ? { $_.MainWindowTitle -eq 'ChatGPT' } | Select -First 1
if(-not $proc){ throw 'ChatGPT window not found' }
$h=$proc.MainWindowHandle
if([W3]::IsIconic($h)){ [W3]::ShowWindow($h,9)|Out-Null }
[W3]::SetForegroundWindow($h)|Out-Null
Start-Sleep 2
$w=$A::RootElement.FindFirst($TS::Children,(PC $A::NameProperty 'ChatGPT'))
if(-not $w){ throw 'window UIA not found' }
$doc=$w.FindFirst($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Document) (PC $A::AutomationIdProperty 'RootWebArea')))
if(-not $doc){ throw 'WebView document not accessible' }
Log ("doc=" + $doc.Current.Name)
if($doc.Current.Name.Trim() -ne $Conversation.Trim()){ Log ("WARN conversation name mismatch doc=[" + $doc.Current.Name + "] expect=[" + $Conversation + "] — continuing because window is ChatGPT") }

$edit=$null
foreach($e0 in $doc.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Edit))){
  if($e0.Current.ClassName -like 'ProseMirror*' -and $e0.Current.Name -eq '询问 ChatGPT'){ $edit=$e0; break }
}
if(-not $edit){
  foreach($e0 in $doc.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Edit))){
    if($e0.Current.ClassName -like 'ProseMirror*' -and $e0.Current.BoundingRectangle.Y -gt 0){ $edit=$e0; break }
  }
}
if(-not $edit){ throw 'composer not found' }
Log ("composer=[" + $edit.Current.Name + "] class=[" + $edit.Current.ClassName + "]")


function IsEmptyComposer($e){
  $ph=$e.FindFirst($TS::Descendants,(PC $A::ClassNameProperty 'placeholder'))
  if($ph){ return $true }
  try{ $v=$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value }catch{ return $false }
  $t=$v.Trim(); return ($t -eq '' -or $t -eq $e.Current.Name.Trim())
}
if(-not (IsEmptyComposer $edit)){ throw 'composer is NOT empty - abort' }

# Check not generating: look for 停止 button
$stop=$false
foreach($b in $doc.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Button))){
  $n=$b.Current.Name
  if($n -match '停止生成' -or $n -eq [char]0x505C+[char]0x6B62){ $stop=$true; Log ("generating? btn=[$n]") }
}
# garbled stop often appears as weird chars on composer-primary while generating
# We proceed only if 添加文件 is enabled
$add=$doc.FindFirst($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Button) (PC $A::NameProperty '添加文件等内容')))
if(-not $add){ throw 'add-file button not found' }
if(-not $add.Current.IsEnabled){ throw 'add-file button disabled (maybe still generating)' }
Log 'composer empty, add-file enabled'

# Try clipboard file drop first
$oldText=$null
try{ if([System.Windows.Forms.Clipboard]::ContainsText()){ $oldText=[System.Windows.Forms.Clipboard]::GetText() } }catch{}
$col = New-Object System.Collections.Specialized.StringCollection
foreach($f in $Files){ [void]$col.Add((Resolve-Path -LiteralPath $f).Path) }
[System.Windows.Forms.Clipboard]::SetFileDropList($col)
$edit.SetFocus(); Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait('^v')
Start-Sleep 3
Log 'pasted file drop'

# Inspect for attachment chips / names
function DumpHints($label){
  Log $label
  $btns=$doc.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Button))
  foreach($b in $btns){
    $n=$b.Current.Name
    if($n -match 'EXT_|REPORT|HANDOVER|移除|删除|文件|md|添加|发送|停止'){ Log ("  BTN=[$n] en=$($b.Current.IsEnabled)") }
  }
  # any element containing report filename
  $all=$doc.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Text))
  $hits=0
  foreach($el in $all){
    $n=$el.Current.Name
    if($n -match 'EXT_REPORT|EXT_HANDOVER|p0_ZH|\.md'){ Log ("  TEXT=[$n]"); $hits++ }
  }
  return $hits
}
$hits = DumpHints 'after file-drop paste'

if($hits -lt 2){
  Log 'file-drop may have failed; trying add-file button + Open dialog'
  $add.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
  Start-Sleep 2
  # dump menu
  foreach($b in $doc.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Button))){
    $n=$b.Current.Name
    if($n -match '照片|文件|上传|电脑|Drive|Google|OneDrive'){ Log ("  MENU BTN=[$n]") }
  }
  foreach($mi in $doc.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::MenuItem))){
    Log ("  MENUITEM=[$($mi.Current.Name)]")
  }
  # also search root for menus outside webview
  $rootMenus=$A::RootElement.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::MenuItem))
  foreach($mi in $rootMenus){
    $n=$mi.Current.Name
    if($n -match '照片|文件|上传|电脑|Drive|添加'){ Log ("  ROOT MENUITEM=[$n]") }
  }
  # click menu item if found
  $clicked=$false
  foreach($name in @('添加照片和文件','上传文件','从计算机添加','添加文件','照片和文件')){
    $mi=$doc.FindFirst($TS::Descendants,(PC $A::NameProperty $name))
    if(-not $mi){ $mi=$A::RootElement.FindFirst($TS::Descendants,(PC $A::NameProperty $name)) }
    if($mi){
      Log ("invoking [$name]")
      try{ $mi.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); $clicked=$true; break }catch{ Log $_.Exception.Message }
    }
  }
  if($clicked){ Start-Sleep 2 }
  # Look for Open file dialog
  $dlg=$null
  foreach($i in 1..8){
    foreach($title in @('打开','Open','打开文件')){
      $dlg=$A::RootElement.FindFirst($TS::Children,(PC $A::NameProperty $title))
      if($dlg){ break }
    }
    if($dlg){ break }
    Start-Sleep 1
  }
  if($dlg){
    Log ("dialog=[" + $dlg.Current.Name + "]")
    # filename edit: typically class Edit, name "文件名:" or File name
    $fn=$null
    foreach($e in $dlg.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Edit))){
      Log ("  DLG EDIT=[$($e.Current.Name)] class=$($e.Current.ClassName)")
      if(-not $fn){ $fn=$e }
    }
    $quoted = ($Files | ForEach-Object { '"' + (Resolve-Path -LiteralPath $_).Path + '"' }) -join ' '
    if($fn){
      $fn.SetFocus()
      try{
        $vp=$fn.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        $vp.SetValue($quoted)
      } catch {
        [System.Windows.Forms.SendKeys]::SendWait('^a')
        Start-Sleep -Milliseconds 200
        [System.Windows.Forms.Clipboard]::SetText($quoted)
        [System.Windows.Forms.SendKeys]::SendWait('^v')
      }
      Start-Sleep 1
      # click 打开 button
      $openBtn=$dlg.FindFirst($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Button) (PC $A::NameProperty '打开(O)')))
      if(-not $openBtn){ $openBtn=$dlg.FindFirst($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Button) (PC $A::NameProperty '打开'))) }
      if(-not $openBtn){ $openBtn=$dlg.FindFirst($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Button) (PC $A::NameProperty 'Open'))) }
      if($openBtn){
        Log 'clicking Open'
        $openBtn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
      } else {
        Log 'Open button not found, sending Enter'
        [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
      }
      Start-Sleep 4
    } else { Log 'filename edit not found in dialog' }
  } else {
    Log 'no Open dialog appeared'
  }
  $hits = DumpHints 'after dialog'
}

# Restore clipboard text later
# Paste accompanying text if composer allows
if($Text){
  Start-Sleep 1
  $edit.SetFocus(); Start-Sleep -Milliseconds 300
  [System.Windows.Forms.Clipboard]::SetText($Text)
  [System.Windows.Forms.SendKeys]::SendWait('^v')
  Start-Sleep 2
  Log 'pasted caption text'
}

$hits2 = DumpHints 'pre-send'
if($hits -lt 1 -and $hits2 -lt 1){
  if($oldText -ne $null){ try{ [System.Windows.Forms.Clipboard]::SetText($oldText) }catch{} }
  throw 'files do not appear attached - abort without sending'
}

if($Send){
  $sendBtn=$doc.FindFirst($TS::Descendants,(AndC (PC $A::ControlTypeProperty $CT::Button) (PC $A::NameProperty '发送')))
  if(-not $sendBtn){
    # maybe icon-only
    foreach($b in $doc.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Button))){
      if($b.Current.ClassName -match 'bg-composer-primary' -and $b.Current.Name -match '发送'){ $sendBtn=$b }
    }
  }
  if(-not $sendBtn){ throw 'send button not found (files may be in composer, NOT sent)' }
  $sendBtn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
  Log ('STATUS=SENT files=' + $Files.Count + ' at ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
} else {
  Log 'STATUS=ATTACHED_NOT_SENT'
}

if($oldText -ne $null){ try{ [System.Windows.Forms.Clipboard]::SetText($oldText) }catch{} }
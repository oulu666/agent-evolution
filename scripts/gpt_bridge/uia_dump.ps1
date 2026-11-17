param([int]$MaxDepth=40,[string]$Out)
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$A=[System.Windows.Automation.AutomationElement]
$root=$A::RootElement
$cond=New-Object System.Windows.Automation.PropertyCondition($A::NameProperty,'ChatGPT')
$wins=$root.FindAll([System.Windows.Automation.TreeScope]::Children,$cond)
$sb=New-Object System.Text.StringBuilder
$walker=[System.Windows.Automation.TreeWalker]::RawViewWalker
function Walk($e,$d){ if($d -gt $MaxDepth){return}
  try{$c=$e.Current; $n=$c.Name; if($n.Length -gt 120){$n=$n.Substring(0,120)+'...'}
  [void]$sb.AppendLine((' '*$d)+$c.ControlType.ProgrammaticName+' | '+$n+' | '+$c.AutomationId+' | '+$c.ClassName)}catch{}
  $ch=$walker.GetFirstChild($e); while($ch -ne $null){ Walk $ch ($d+1); $ch=$walker.GetNextSibling($ch)} }
foreach($w in $wins){ [void]$sb.AppendLine('WINDOW pid='+$w.Current.ProcessId); Walk $w 0 }
[System.IO.File]::WriteAllText($Out,$sb.ToString(),(New-Object System.Text.UTF8Encoding($true)))
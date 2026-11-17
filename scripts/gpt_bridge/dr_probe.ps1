Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$A=[System.Windows.Automation.AutomationElement]; $TS=[System.Windows.Automation.TreeScope]; $CT=[System.Windows.Automation.ControlType]
function PC($p,$v){ New-Object System.Windows.Automation.PropertyCondition($p,$v) }
$w=$A::RootElement.FindFirst($TS::Children,(PC $A::NameProperty 'ChatGPT'))
$doc=$w.FindFirst($TS::Descendants,(New-Object System.Windows.Automation.AndCondition((PC $A::ControlTypeProperty $CT::Document),(PC $A::AutomationIdProperty 'RootWebArea'))))
"conv=" + $doc.Current.Name
$all=$doc.FindAll($TS::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
$names=@(); foreach($x in $all){ $n=$x.Current.Name; if($n){ $names += ($x.Current.ControlType.ProgrammaticName.Replace('ControlType.','')+': '+$n) } }
$idx=0; for($i=0;$i -lt $names.Count;$i++){ if($names[$i] -like '*粘贴的文本 (1)(20261111*'){ $idx=$i } }
$names[$idx..($names.Count-1)] | % { if($_.Length -gt 160){ $_.Substring(0,160) } else { $_ } }
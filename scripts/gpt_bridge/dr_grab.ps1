Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$A=[System.Windows.Automation.AutomationElement]; $TS=[System.Windows.Automation.TreeScope]; $CT=[System.Windows.Automation.ControlType]
function PC($p,$v){ New-Object System.Windows.Automation.PropertyCondition($p,$v) }
$w=$A::RootElement.FindFirst($TS::Children,(PC $A::NameProperty 'ChatGPT'))
$doc=$w.FindFirst($TS::Descendants,(New-Object System.Windows.Automation.AndCondition((PC $A::ControlTypeProperty $CT::Document),(PC $A::AutomationIdProperty 'RootWebArea'))))
$btns=$doc.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Button))
$best=''; foreach($b in $btns){ $n=$b.Current.Name; if($n -like 'Target Fraction 扫描与 Monitor v2*' -and $n.Length -gt $best.Length){ $best=$n } }
[IO.File]::WriteAllText($args[0],$best,(New-Object Text.UTF8Encoding($false)))
"len=$($best.Length)"
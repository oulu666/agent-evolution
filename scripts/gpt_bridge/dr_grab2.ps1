Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$A=[System.Windows.Automation.AutomationElement]; $TS=[System.Windows.Automation.TreeScope]; $CT=[System.Windows.Automation.ControlType]
function PC($p,$v){ New-Object System.Windows.Automation.PropertyCondition($p,$v) }
$w=$A::RootElement.FindFirst($TS::Children,(PC $A::NameProperty 'ChatGPT'))
$docs=$w.FindAll($TS::Descendants,(PC $A::ControlTypeProperty $CT::Document))
foreach($d in $docs){ "DOC name=[$($d.Current.Name)]" }
$sb=$null; foreach($d in $docs){ if($d.Current.Name -eq 'sandbox'){ $sb=$d } }
$all=$sb.FindAll($TS::Descendants,[System.Windows.Automation.Condition]::TrueCondition); "sandbox nodes=$($all.Count)"
try{ $tp=$sb.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern); $t=$tp.DocumentRange.GetText(-1); [IO.File]::WriteAllText($args[0],$t,(New-Object Text.UTF8Encoding($false))); "textpattern len=$($t.Length)" }catch{ "no textpattern: $_" }
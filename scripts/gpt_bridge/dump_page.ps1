Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$A=[System.Windows.Automation.AutomationElement]; $TS=[System.Windows.Automation.TreeScope]; $CT=[System.Windows.Automation.ControlType]
$w=$A::RootElement.FindFirst($TS::Children,(New-Object System.Windows.Automation.PropertyCondition($A::NameProperty,'ChatGPT')))
$c=New-Object System.Windows.Automation.AndCondition((New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty,$CT::Document)),(New-Object System.Windows.Automation.PropertyCondition($A::AutomationIdProperty,'RootWebArea')))
$d=$w.FindFirst($TS::Descendants,$c)
$t=$d.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern).DocumentRange.GetText(-1)
[System.IO.File]::WriteAllText($args[0],$t,[System.Text.Encoding]::UTF8)

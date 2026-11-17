Add-Type @"
using System; using System.Runtime.InteropServices;
public class W { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
[DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);}
"@
$h=(Get-Process ChatGPT | ? {$_.MainWindowTitle -eq 'ChatGPT'} | Select -First 1).MainWindowHandle
"iconic="+[W]::IsIconic($h)+" zoomed="+[W]::IsZoomed($h)
if([W]::IsIconic($h)){[W]::ShowWindow($h,9)|Out-Null}
[W]::SetForegroundWindow($h)|Out-Null
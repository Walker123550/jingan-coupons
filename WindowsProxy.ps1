if (-not ('JinganProxySettings' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class JinganProxySettings {
    [StructLayout(LayoutKind.Sequential)]
    struct IEProxy { [MarshalAs(UnmanagedType.Bool)] public bool AutoDetect; public IntPtr AutoConfig; public IntPtr Proxy; public IntPtr Bypass; }
    [DllImport("winhttp.dll", SetLastError=true)]
    static extern bool WinHttpGetIEProxyConfigForCurrentUser(out IEProxy config);
    [DllImport("kernel32.dll")] static extern IntPtr GlobalFree(IntPtr value);
    public static string Read() {
        IEProxy config;
        if(!WinHttpGetIEProxyConfigForCurrentUser(out config)) throw new Win32Exception(Marshal.GetLastWin32Error());
        try { return Marshal.PtrToStringUni(config.Proxy) ?? "<direct>"; }
        finally { GlobalFree(config.AutoConfig); GlobalFree(config.Proxy); GlobalFree(config.Bypass); }
    }
    [StructLayout(LayoutKind.Explicit, Size=16)]
    struct Option { [FieldOffset(0)] public uint Kind; [FieldOffset(8)] public IntPtr Value; }
    [StructLayout(LayoutKind.Sequential)]
    struct Options { public uint Size; public IntPtr Connection; public uint Count; public uint Error; public IntPtr Data; }
    [DllImport("wininet.dll", EntryPoint="InternetSetOptionW", SetLastError=true)]
    static extern bool SetOption(IntPtr h, int option, IntPtr data, int length);
    public static void Notify() {
        SetOption(IntPtr.Zero, 95, IntPtr.Zero, 0);
        SetOption(IntPtr.Zero, 37, IntPtr.Zero, 0);
    }
    public static void Apply(string server, string bypass) {
        if (IntPtr.Size != 8) throw new NotSupportedException("64-bit PowerShell required");
        IntPtr s=Marshal.StringToHGlobalUni(server), b=Marshal.StringToHGlobalUni(bypass ?? "");
        IntPtr data=Marshal.AllocHGlobal(48), list=IntPtr.Zero;
        try {
            Marshal.StructureToPtr(new Option {Kind=1, Value=new IntPtr(3)}, data, false);
            Marshal.StructureToPtr(new Option {Kind=2, Value=s}, IntPtr.Add(data,16), false);
            Marshal.StructureToPtr(new Option {Kind=3, Value=b}, IntPtr.Add(data,32), false);
            Options options=new Options {Size=(uint)Marshal.SizeOf(typeof(Options)), Count=3, Data=data};
            list=Marshal.AllocHGlobal((int)options.Size);
            Marshal.StructureToPtr(options,list,false);
            if (!SetOption(IntPtr.Zero,75,list,(int)options.Size)) throw new Win32Exception(Marshal.GetLastWin32Error());
            Notify();
        } finally {
            if(list!=IntPtr.Zero) Marshal.FreeHGlobal(list);
            Marshal.FreeHGlobal(data); Marshal.FreeHGlobal(s); Marshal.FreeHGlobal(b);
        }
    }
}
'@
}

function Get-JinganConnectionSnapshot {
    $snapshot=@{}
    $key='HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings\Connections'
    $values=Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
    foreach($name in @('DefaultConnectionSettings','SavedLegacySettings')) {
        $value=$values.PSObject.Properties[$name]
        if($null -ne $value) { $snapshot[$name]=[Convert]::ToBase64String($value.Value) }
    }
    return $snapshot
}

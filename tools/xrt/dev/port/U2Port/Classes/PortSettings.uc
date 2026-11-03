//=============================================================================
// PortSettings - settings added by the Windows port, shown in the game's own
// Options menu (UIScripts/U2Menus.ui: Game > Walking Speed; Video > Frame Rate
// Limit, Field of View, VSync, UI Scale; the menu edits are
// applied by tools/xrt/dev/port.py).
//
// The values are config(User), so they persist in User.ini [U2Port.PortSettings]
// like every other player preference. They are global, not part of a saved game.
// The runtime reads the same section at startup (out/dev-init/runtime/
// port_settings.c) and receives changes through the console command
// "PORTSET <Key> <Value>", so a change applies immediately.
//=============================================================================
class PortSettings extends UIHelper
	config(User);

// Percent of the original walking/running speed, 75..200 in steps of 5.
var config int WalkingSpeed;
// 0 = Auto, otherwise 100, 125, 150 or 200 percent.
var config int UIScale;
// Field of view in horizontal degrees at 4:3 (wider screens see more at the sides, Hor+), 75..120; default 85, the
// game's own class default (the shipped User.ini's DefaultFOV=100 compensated the original Vert- widescreen view).
// 0 = the game's own PlayerController.DefaultFOV (User.ini [Engine.PlayerController]).
var config int FieldOfView;
// Subtitle Size (100, 112, 125: the subtitle font SubTFonts.EE16/18/20). NOT in the menu and not applied at start: in the
// enhanced batch every size above 100% drew no subtitles at all (launches 11a-13b); kept for the follow-up investigation.
var config int SubtitleSize;
// Frame rate limit in frames per second; 0 = unlimited.
var config int FrameRateLimit;
// VSync for the port's windowed and borderless presentation (the game's own UseVSync only acts in exclusive
// full screen, which the port does not use).
var config bool VSync;

function int ValidWalkingSpeed(int P)
{
	if (P < 75 || P > 200)
		return 100;
	return P - P % 5;
}

// Slider (U2Slider Range=75,200 Step=5): Get/Set<Variable>.
function float GetWalkingSpeed()
{
	return ValidWalkingSpeed(WalkingSpeed);
}

function SetWalkingSpeed(float F)
{
	local int P;

	P = Clamp(int((F + 2.5) / 5.0) * 5, 75, 200);
	if (P == WalkingSpeed)
		return;
	WalkingSpeed = P;
	SaveConfig();
	ConsoleCommand("PORTSET WalkingSpeed" @ P);
}

// Selector (U2Selector): one function per list item, CurrentAccess returns the index.
function int GetUIScaleIndex()
{
	switch (UIScale)
	{
		case 0:   return 0;
		case 125: return 2;
		case 150: return 3;
		case 200: return 4;
	}
	return 1;
}

function SetUIScale(int P)
{
	if (P == UIScale)
		return;
	UIScale = P;
	SaveConfig();
	ConsoleCommand("PORTSET UIScale" @ P);
}

// Options > Video > Resolution (replaces CodeMonkey's GetRes/SetRes in the port's menu), for the current mode:
//  - full screen (borderless in the port): the resolution the game renders at, scaled to the screen; stored as
//    FullscreenViewportX/Y and applied at once (SETRES);
//  - window: the window's client size; the runtime resizes the window to it (PORTSET WindowSize), leaving the
//    maximized state, and the game re-renders at that size. The game keeps the current size as WindowedViewportX/Y.
// The original GetRes showed the UI root size (wrong with UI scaling); its SetRes moved a maximized window while it
// stayed maximized.
function string IniGet(string Key)
{
	return GetPlayerOwner().ConsoleCommand("get ini:Engine.Engine.ViewportManager" @ Key);
}

function bool InFullscreen()
{
	return bool(IniGet("StartupFullscreen"));
}

function string GetResolution()
{
	if (InFullscreen())
		return IniGet("FullscreenViewportX") $ "x" $ IniGet("FullscreenViewportY");
	return IniGet("WindowedViewportX") $ "x" $ IniGet("WindowedViewportY");
}

// The Resolution selector can only show an entry of its list: the display modes, plus - in a window - the window's
// current size when that is not a display mode (a maximized window is 2560x1369 on a 2560x1440 screen; without it the
// selector showed its first entry, 640x480). It is appended: the selector keeps an index into the list, and an entry
// inserted in front shifted every display mode by one between window and full screen (2560x1440 became 1920x1440).
function array<string> GetDisplayModes()
{
	local array<string> Modes;
	local string Current;
	local int i;

	StrArray(GetConsole().ConsoleCommandEx("DISPLAYMODES"), " ", Modes, true);
	Current = GetResolution();
	for (i = 0; i < Modes.Length; i++)
		if (Modes[i] == Current)
			return Modes;
	Modes[Modes.Length] = Current;
	return Modes;
}

function SetResolution(string S)
{
	local int i, W, H;

	i = InStr(S, "x");
	if (i <= 0)
		return;
	W = int(Left(S, i));
	S = Mid(S, i + 1);
	i = InStr(S, "x");
	if (i > 0)
		S = Left(S, i);
	H = int(S);
	if (W < 320 || H < 200)
		return;
	if (InFullscreen())
	{
		GetPlayerOwner().ConsoleCommand("set ini:Engine.Engine.ViewportManager FullscreenViewportX" @ W);
		GetPlayerOwner().ConsoleCommand("set ini:Engine.Engine.ViewportManager FullscreenViewportY" @ H);
		GetPlayerOwner().ConsoleCommand("SETRES" @ W $ "x" $ H);
	}
	else
		ConsoleCommand("PORTSET WindowSize" @ W @ H);
}

// Options > Video > Field of View (U2Slider Range=75,120 Step=5). Shows the game's own FOV until the player sets one.
function float GetFieldOfView()
{
	if (FieldOfView >= 75 && FieldOfView <= 120)
		return FieldOfView;
	return int(GetPlayerOwner().DefaultFOV + 0.5);
}

function SetFieldOfView(float F)
{
	local int P;

	P = Clamp(int((F + 2.5) / 5.0) * 5, 75, 120);
	if (P == FieldOfView)
		return;
	FieldOfView = P;
	SaveConfig();
	ConsoleCommand("PORTSET FieldOfView" @ P);
}

// Options > Video > Frame Rate Limit (U2Selector with Accessor/Modifier/CurrentText, like Resolution): the common
// display rates, Unlimited, and a value set in User.ini that is not one of them ("Custom N").
function string FrameRateLimitText(int N)
{
	switch (N)
	{
		case 0:
			return "Unlimited";
		case 30: case 60: case 90: case 120: case 144: case 165: case 240:
			return string(N);
	}
	return "Custom" @ N;
}

function array<string> GetFrameRateLimits()
{
	local array<string> L;

	L[0] = "30"; L[1] = "60"; L[2] = "90"; L[3] = "120"; L[4] = "144"; L[5] = "165"; L[6] = "240"; L[7] = "Unlimited";
	if (Left(FrameRateLimitText(FrameRateLimit), 6) == "Custom")
		L[8] = FrameRateLimitText(FrameRateLimit);
	return L;
}

function string GetFrameRateLimitText()
{
	return FrameRateLimitText(FrameRateLimit);
}

function SetFrameRateLimitText(string S)
{
	local int N;

	if (S == "Unlimited")
		N = 0;
	else if (Left(S, 7) == "Custom ")
		N = int(Mid(S, 7));
	else
		N = int(S);
	if (N != 0 && (N < 20 || N > 1000))
		return;
	if (N == FrameRateLimit)
		return;
	FrameRateLimit = N;
	SaveConfig();
	ConsoleCommand("PORTSET FrameRateLimit" @ N);
}

// Options > Video > VSync (U2CheckBox Variable=VSyncEnabled). The runtime resets the device once to apply it.
function bool GetVSyncEnabled()
{
	return VSync;
}

function SetVSyncEnabled(bool B)
{
	if (B == VSync)
		return;
	VSync = B;
	SaveConfig();
	if (B)
		ConsoleCommand("PORTSET VSync 1");
	else
		ConsoleCommand("PORTSET VSync 0");
}

// Options > HUD > Subtitle Size (U2Selector): one function per list item, CurrentAccess returns the index.
function int GetSubtitleSizeIndex()
{
	if (SubtitleSize > 118)
		return 2;
	if (SubtitleSize > 106)
		return 1;
	return 0;
}

function string SubtitleFontName(int P)
{
	if (P > 118)
		return "SubTFonts.EE20";
	if (P > 106)
		return "SubTFonts.EE18";
	return "SubTFonts.EE16";
}

// Applies at once: every live DialogEngine gets the font (SubtitleFont, which the dialogue code measures and draws
// with) and its SubtitleFontStr; that string also becomes the class default, so the DialogEngine of a later level
// loads the same font in PostBeginPlay.
function ApplySubtitleFont(int P)
{
	local Actor A;
	local string F;
	local bool bDefault;

	F = SubtitleFontName(P);
	foreach GetPlayerOwner().AllActors(class'Actor', A)
	{
		if (!A.IsA('DialogEngine'))
			continue;
		A.SetPropertyText("SubtitleFontStr", F);
		A.SetPropertyText("SubtitleFont", "Font'" $ F $ "'");
		if (!bDefault)
		{
			A.SetPropertyTextDefault("SubtitleFontStr");
			bDefault = true;
		}
	}
	if (!bDefault)
		GetPlayerOwner().ConsoleCommand("set U2Dialog.DialogEngine SubtitleFontStr" @ F);
}

function SetSubtitleSize(int P)
{
	if (P == SubtitleSize)
		return;
	SubtitleSize = P;
	SaveConfig();
	ApplySubtitleFont(P);
	ConsoleCommand("PORTSET SubtitleSize" @ P);
}

function SetSubtitleSize100() { SetSubtitleSize(100); }
function SetSubtitleSize112() { SetSubtitleSize(112); }
function SetSubtitleSize125() { SetSubtitleSize(125); }

function SetUIScaleAuto() { SetUIScale(0); }
function SetUIScale100() { SetUIScale(100); }
function SetUIScale125() { SetUIScale(125); }
function SetUIScale150() { SetUIScale(150); }
function SetUIScale200() { SetUIScale(200); }

defaultproperties
{
	WalkingSpeed=100
	UIScale=100
	FieldOfView=85
	SubtitleSize=100
	FrameRateLimit=0
	VSync=false
}

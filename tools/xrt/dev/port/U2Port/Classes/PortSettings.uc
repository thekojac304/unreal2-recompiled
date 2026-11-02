//=============================================================================
// PortSettings - settings added by the Windows port, shown in the game's own
// Options menu (UIScripts/U2Menus.ui: Game > Walking Speed, Video > UI Scale;
// the menu edits are applied by tools/xrt/dev/port.py).
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

// Options > Video > Resolution (replaces CodeMonkey's GetRes/SetRes in the port's menu): the FULLSCREEN resolution.
// Fullscreen is borderless in the port and renders at this size, scaled to the screen. A window always renders at
// its own size, so in a window the choice is only stored and used the next time fullscreen is entered. The original
// GetRes showed the UI root size (wrong with UI scaling) and SetRes resized the window.
function string IniGet(string Key)
{
	return GetPlayerOwner().ConsoleCommand("get ini:Engine.Engine.ViewportManager" @ Key);
}

function string GetFullscreenRes()
{
	return IniGet("FullscreenViewportX") $ "x" $ IniGet("FullscreenViewportY");
}

function SetFullscreenRes(string S)
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
	GetPlayerOwner().ConsoleCommand("set ini:Engine.Engine.ViewportManager FullscreenViewportX" @ W);
	GetPlayerOwner().ConsoleCommand("set ini:Engine.Engine.ViewportManager FullscreenViewportY" @ H);
	if (bool(IniGet("StartupFullscreen")))
		GetPlayerOwner().ConsoleCommand("SETRES" @ W $ "x" $ H);
}

function SetUIScaleAuto() { SetUIScale(0); }
function SetUIScale100() { SetUIScale(100); }
function SetUIScale125() { SetUIScale(125); }
function SetUIScale150() { SetUIScale(150); }
function SetUIScale200() { SetUIScale(200); }

defaultproperties
{
	WalkingSpeed=100
	UIScale=100
}

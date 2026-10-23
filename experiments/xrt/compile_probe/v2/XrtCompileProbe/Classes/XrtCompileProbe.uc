//=============================================================================
// XrtCompileProbe - project-owned compile probe (not game code).
// Compiled by the original and by the translated UnrealScript compiler
// (ucc make), then run in the original and in the translated engine. Its
// output depends on the source: ProbeTag and the default Greeting.
//=============================================================================
class XrtCompileProbe extends Commandlet;

const ProbeTag = "bravo-2";

var string Greeting;

event int Main(string Parms)
{
	Log("XCP tag=" $ ProbeTag $ " greeting=" $ Greeting);
	Log("XCP done");
	return 0;
}

defaultproperties
{
	Greeting="changed-default"
	HelpCmd="XrtCompileProbe"
	HelpOneLiner="Compile probe"
	HelpUsage="XrtCompileProbe"
	LogToStdout=true
}

//=============================================================================
// XrtCompileProbe (invalid variant) - deliberately does not compile: Main uses
// an identifier that is declared nowhere. The original and the translated
// compiler must report the same diagnostic and leave the same files behind.
//=============================================================================
class XrtCompileProbe extends Commandlet;

const ProbeTag = "alpha-1";

var string Greeting;

event int Main(string Parms)
{
	Log("XCP tag=" $ ProbeTag $ " greeting=" $ Greeting $ UndeclaredProbeValue);
	Log("XCP done");
	return 0;
}

defaultproperties
{
	Greeting="from-defaults"
	HelpCmd="XrtCompileProbe"
	HelpOneLiner="Compile probe"
	HelpUsage="XrtCompileProbe"
	LogToStdout=true
}

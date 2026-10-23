//=============================================================================
// XrtCompileProbe (extended variant) - project-owned compile probe: objects of
// project classes (inheritance, overrides, super, defaults, static calls),
// dynamic and static arrays, out parameters and the control-flow statements.
// Every output line depends on the source.
//=============================================================================
class XrtCompileProbe extends Commandlet;

const ProbeTag = "charlie-3";

var string Greeting;
var int Fixed[3];

function int SumTo(int n)
{
	local int i, s;

	for (i = 1; i <= n; i++)
		s += i;
	return s;
}

function string Grade(int v)
{
	switch (v / 10)
	{
	case 10:
	case 9:
		return "A";
	case 8:
		return "B";
	default:
		return "C";
	}
}

function Accumulate(XrtProbeShape S, out int Total)
{
	Total += S.Area();
	S.History[S.History.Length] = Total;
}

event int Main(string Parms)
{
	local XrtProbeShape Shapes[2];
	local array<string> Names;
	local int i, Total, n;
	local string Line;

	Log("XCP tag=" $ ProbeTag $ " greeting=" $ Greeting);
	Shapes[0] = new class'XrtProbeSquare';
	Shapes[1] = new class'XrtProbeTriangle';
	for (i = 0; i < 2; i++)
	{
		Accumulate(Shapes[i], Total);
		Names[Names.Length] = Shapes[i].Describe();
	}
	Log("XCP shapes=" $ Names[0] $ "," $ Names[1] $ " total=" $ Total);
	Log("XCP history=" $ Shapes[1].History.Length $ " last=" $ Shapes[1].History[0]);
	Log("XCP sum10=" $ SumTo(10) $ " twice=" $ class'XrtProbeShape'.static.Twice(21));
	for (i = 0; i < 3; i++)
		Fixed[i] = (i + 1) * 7;
	Line = "";
	n = 0;
	while (n < 3)
	{
		Line = Line $ Fixed[n] $ ":" $ Grade(Fixed[n] * 5) $ " ";
		n++;
	}
	Log("XCP grades=" $ Line);
	i = 0;
	do
	{
		i += 3;
	} until (i > 10);
	Log("XCP do=" $ i $ " default=" $ class'XrtProbeSquare'.default.Edge $ " isa=" $ Shapes[0].IsA('XrtProbeShape'));
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

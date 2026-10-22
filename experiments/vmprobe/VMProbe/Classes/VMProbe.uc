//=============================================================================
// VMProbe - deterministic UnrealScript VM probe for differential testing.
// Written for this investigation (not game code). Compiled with the original
// Unreal II UCC; run in the original engine and in the independent VM, and
// the T<n>= lines are compared byte for byte.
//=============================================================================
class VMProbe extends Commandlet;

struct ProbeStruct
{
	var int A;
	var float B;
	var string S;
	var vector V;
};

var int Counter;
var array<int> Arr;
var int StaticArr[4];
var ProbeStruct PS, PS2;
var string Str;
var name NameVar;
var byte ByteVar;
var bool bFlag;
var float FVar;

function int SideEffect(int v)
{
	Counter += 1;
	return v;
}

static function int Fib(int n)
{
	if (n < 2)
		return n;
	return Fib(n - 1) + Fib(n - 2);
}

function AddOut(int a, int b, out int c)
{
	c = a + b;
}

function int Opt(int a, optional int b)
{
	return a * 10 + b;
}

function string Classify(int x)
{
	local string r;
	switch (x)
	{
	case 0:
		r = "zero";
		break;
	case 1:
	case 2:
		r = "small";
		break;
	case 3:
		r = "three";
	case 4:
		r = r $ "-four";
		break;
	default:
		r = "big";
	}
	return r;
}

function string NameSwitch(name n)
{
	switch (n)
	{
	case 'Alpha':
		return "A";
	case 'Beta':
		return "B";
	}
	return "?";
}

function L(int n, string s)
{
	Log("T" $ n $ "=" $ s);
}

event int Main(string Parms)
{
	local int i, j, k;
	local float f, g;
	local string s, a, b;
	local vector v, w;
	local rotator r;
	local name nm;
	local byte bt;
	local bool bb;
	local Object o;

	// --- integer arithmetic
	L(1, string(7 / 2));
	L(2, string(-7 / 2));
	L(3, string(2147483647 + 1));
	L(4, string(1 << 31));
	L(5, string(-8 >> 1));
	L(6, string(-8 >>> 1));
	L(7, string(~5));
	L(8, string(12 & 10) @ string(12 | 10) @ string(12 ^ 10));
	i = 7;
	i *= 1.5;
	L(9, string(i));
	i = 7;
	i /= 2.0;
	L(10, string(i));
	i = 5;
	j = i++;
	k = ++i;
	L(11, j @ k @ i);
	L(12, string(Clamp(15, 0, 10)) @ string(Min(3, -4)) @ string(Max(3, -4)));

	// --- float arithmetic and formatting
	L(13, string(1.5));
	L(14, string(7.5 % 2.0));
	L(15, string(2.0 ** 10.0));
	L(16, string(int(3.7)) @ string(int(-3.7)));
	L(17, string(1.0 / 3.0));
	L(18, string(FClamp(2.5, 0.0, 1.0)) @ string(Lerp(0.25, 10.0, 20.0)) @ string(Square(1.5)));
	L(19, string(Sqrt(2.0)) @ string(Abs(-0.5)));
	f = 0.1;
	g = 0.2;
	L(20, string(f + g == 0.3) @ string(f + g ~= 0.3));
	L(21, string(Sin(0.5)) @ string(Cos(0.5)) @ string(Atan(1.0)));
	L(22, string(123456789.0) @ string(-0.000001));

	// --- byte and bool
	bt = 250;
	bt += 10;
	L(23, string(bt));
	ByteVar = 3;
	ByteVar -= 5;
	L(24, string(ByteVar));
	bb = true;
	L(25, string(bb) @ string(!bb) @ string(bb ^^ true));

	// --- strings
	s = "Hello World";
	L(26, Caps(s) @ Len(s) @ InStr(s, "World") @ InStr(s, "xyz"));
	L(27, Left(s, 5) $ "|" $ Right(s, 5) $ "|" $ Mid(s, 3, 4) $ "|" $ Mid(s, 6));
	L(28, Chr(65) $ Asc("a") $ "|" $ Locs("MiXeD"));
	L(29, string("abc" < "abd") @ string("ABC" == "abc") @ string("ABC" ~= "abc") @ string("b" > "abc"));
	L(30, string(int("42abc")) @ string(int("abc")) @ string(float("3.25")) @ string(int(" -17")));
	L(31, string(bool("True")) @ string(bool("0")) @ string(bool("1")));
	a = "";
	if (Split("key=value=x", "=", a, b))
		L(32, a $ "|" $ b);
	else
		L(32, "nosplit");

	// --- names
	nm = 'SomeName';
	L(33, string(nm) @ string(nm == 'somename') @ NameSwitch('Beta') @ NameSwitch('Gamma'));

	// --- control flow
	k = 0;
	for (i = 0; i < 10; i++)
	{
		if (i == 3)
			continue;
		if (i == 8)
			break;
		k += i;
	}
	L(34, string(k));
	i = 0;
	k = 1;
	while (k < 1000)
	{
		k *= 3;
		i++;
	}
	L(35, i @ k);
	i = 0;
	do
	{
		i += 5;
	} until (i > 12);
	L(36, string(i));
	L(37, Classify(0) @ Classify(2) @ Classify(3) @ Classify(4) @ Classify(9));

	// --- calls
	L(38, string(Fib(15)));
	AddOut(20, 22, k);
	L(39, string(k));
	L(40, Opt(4) @ Opt(4, 2));
	Counter = 0;
	bb = false && SideEffect(1) == 1;
	bb = true || SideEffect(1) == 1;
	bb = true && SideEffect(1) == 1;
	L(41, Counter @ string(bb));

	// --- vectors / rotators
	v = vect(1, 2, 3);
	w = vect(4, -5, 6);
	L(42, string(v dot w) @ string(v cross w));
	L(43, string(VSize(vect(3, 4, 0))) @ string(Normal(vect(0, 0, 5))));
	L(44, string(v + w) @ string(v * 2.0) @ string(v == vect(1, 2, 3)));
	r.Pitch = 16384;
	r.Yaw = -100;
	r.Roll = 70000;
	L(45, string(r) @ string(r + r));

	// --- arrays and structs
	Arr.Length = 3;
	Arr[0] = 10;
	Arr[1] = 20;
	Arr[2] = 30;
	Arr[5] = 60;
	L(46, Arr.Length @ Arr[3] @ Arr[5]);
	Arr.Insert(1, 2);
	Arr[1] = 11;
	Arr.Remove(4, 1);
	s = "";
	for (i = 0; i < Arr.Length; i++)
		s = s $ Arr[i] $ ",";
	L(47, s);
	StaticArr[0] = 1;
	StaticArr[3] = 4;
	L(48, StaticArr[0] + StaticArr[1] + StaticArr[3] @ ArrayCount(StaticArr));
	PS.A = 5;
	PS.B = 2.5;
	PS.S = "st";
	PS.V = vect(1, 1, 1);
	PS2 = PS;
	L(49, string(PS == PS2) @ PS2.S @ PS2.V.Z);
	PS2.V.Y = 9;
	L(50, string(PS == PS2) @ string(PS != PS2) @ PS.V.Y);

	// --- defaults, classes, objects
	L(51, Str @ default.Str @ default.FVar @ string(default.NameVar));
	L(52, string(ClassIsChildOf(class'VMProbe', class'Commandlet')) @ string(IsA('Commandlet')) @ string(IsA('Actor')));
	o = self;
	L(53, string(Commandlet(o) != None) @ string(Actor(o) == None) @ string(Class.Name) @ string(self.Name != ''));
	L(54, "done");
	return 0;
}

defaultproperties
{
	Str="hello"
	FVar=2.25
	NameVar=Commandlet
	HelpCmd="VMProbe"
	HelpOneLiner="Deterministic VM probe"
	HelpUsage="VMProbe"
	LogToStdout=true
}

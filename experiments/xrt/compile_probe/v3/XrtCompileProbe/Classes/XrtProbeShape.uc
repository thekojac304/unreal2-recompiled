//=============================================================================
// XrtProbeShape - abstract base class of the compile probe (project-owned
// test code): defaults, a virtual function, a static function, an array.
//=============================================================================
class XrtProbeShape extends Object
	abstract;

var string ShapeName;
var int Sides;
var array<int> History;

function int Area()
{
	return 0;
}

function string Describe()
{
	return ShapeName $ "/" $ Sides $ "/" $ Area();
}

static function int Twice(int v)
{
	return v * 2;
}

defaultproperties
{
	ShapeName="shape"
	Sides=0
}

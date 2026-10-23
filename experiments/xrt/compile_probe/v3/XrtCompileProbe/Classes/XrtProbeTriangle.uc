//=============================================================================
// XrtProbeTriangle - overrides Area only; inherits Describe.
//=============================================================================
class XrtProbeTriangle extends XrtProbeShape;

var int Base, Height;

function int Area()
{
	return Base * Height / 2;
}

defaultproperties
{
	ShapeName="triangle"
	Sides=3
	Base=4
	Height=5
}

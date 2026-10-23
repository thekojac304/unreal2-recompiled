//=============================================================================
// XrtProbeSquare - overrides Area and Describe (calls the super version).
//=============================================================================
class XrtProbeSquare extends XrtProbeShape;

var int Edge;

function int Area()
{
	return Edge * Edge;
}

function string Describe()
{
	return "square:" $ super.Describe();
}

defaultproperties
{
	ShapeName="square"
	Sides=4
	Edge=3
}

"""Mini parser vs. Verilator JSON as oracle."""

import pytest

from dlv import verilator
from dlv.parser import parse_text
from tests.conftest import requires_verilator

CASES = {
    "ansi": "module t(input clk, input [7:0] a, b, output reg [15:0] q, output z); endmodule",
    "non_ansi": "module t(clk, a, q); input clk; input [3:0] a; output [31:0] q; assign q = {28'b0, a}; endmodule",
    "params": """module t #(parameter W = 12, parameter N = W/4)
        (input [W-1:0] a, output [N*2:0] q, output [$clog2(W)-1:0] r);
        assign q = 0; assign r = 0; endmodule""",
    "wide": "module t(input [63:0] a, output [40:0] q); assign q = a[40:0]; endmodule",
}


@requires_verilator
@pytest.mark.parametrize("name", CASES)
def test_parser_matches_verilator(name, tmp_path):
    f = tmp_path / "t.v"
    f.write_text(CASES[name])
    (mod,) = parse_text(CASES[name])
    ref = [(p.name, p.direction, p.width) for p in verilator.ports(f, "t")]
    assert [(p.name, p.direction, p.width) for p in mod.ports] == ref


@requires_verilator
def test_verilator_error(tmp_path):
    f = tmp_path / "t.v"
    f.write_text("module t(input a; endmodule")
    with pytest.raises(verilator.DlvError):
        verilator.ports(f, "t")

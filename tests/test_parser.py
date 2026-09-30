from dlv.parser import parse_file, parse_text


def ports(m):
    return [(p.name, p.direction, p.width) for p in m.ports]


def test_ansi():
    (m,) = parse_text("module m(input clk, input [7:0] a, b, output reg [3:0] q, inout z);endmodule")
    assert ports(m) == [
        ("clk", "input", 1), ("a", "input", 8), ("b", "input", 8), ("q", "output", 4), ("z", "inout", 1)
    ]


def test_non_ansi():
    (m,) = parse_text("""
    module m(clk, a, q);
      input clk;
      input [15:0] a;
      output reg [1:0] q;
      wire x;
    endmodule""")
    assert ports(m) == [("clk", "input", 1), ("a", "input", 16), ("q", "output", 2)]


def test_comments_and_strings():
    (m,) = parse_text("""
    // module fake(input x);
    /* module fake2(input y); */
    module real_m(
      input a, // input [9:0] nope
      /* output c, */
      output b
    );
      initial $display("module evil(input z);");
    endmodule""")
    assert m.name == "real_m"
    assert ports(m) == [("a", "input", 1), ("b", "output", 1)]


def test_parameter_widths():
    (m,) = parse_text("""
    module m #(parameter W = 8, parameter [3:0] N = W/2 + 1, parameter integer L = $clog2(W))
      (input [W-1:0] a, output [N*2-1:0] b, output [L:0] c, input [UNKNOWN:0] d);
    endmodule""")
    assert m.params == {"W": 8, "N": 5, "L": 3}
    assert ports(m) == [("a", "input", 8), ("b", "output", 10), ("c", "output", 4), ("d", "input", None)]
    assert m.ports[0].range == "W-1:0"


def test_body_parameter_non_ansi():
    (m,) = parse_text("module m(a); parameter W = 4; input [W-1:0] a; endmodule")
    assert ports(m) == [("a", "input", 4)]


def test_multiple_modules_and_ifdef():
    a, b = parse_text("""
    module a(input x);
    endmodule
    `ifdef FOO
    module b(input [1:0] y, output z);
    `else
    `endif
    endmodule""")
    assert (a.name, b.name) == ("a", "b")
    assert ports(b) == [("y", "input", 2), ("z", "output", 1)]


def test_no_ports():
    (m,) = parse_text("module top; endmodule")
    assert m.ports == []


def test_cache(tmp_path):
    f = tmp_path / "m.v"
    f.write_text("module m(input a); endmodule")
    cache = tmp_path / "c"
    assert ports(parse_file(f, cache)[0]) == [("a", "input", 1)]
    assert (cache / "parser.json").exists()
    assert ports(parse_file(f, cache)[0]) == [("a", "input", 1)]  # from cache
    f.write_text("module m(input a, output b); endmodule")
    assert len(parse_file(f, cache)[0].ports) == 2  # invalidated by size

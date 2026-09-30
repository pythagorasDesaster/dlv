module counter #(parameter WIDTH = 8) (
    input  wire             clk,
    input  wire             rst,
    input  wire             en,
    output reg  [WIDTH-1:0] q
);
    always @(posedge clk) begin
        if (rst)      q <= 0;
        else if (en)  q <= q + 1;
    end
endmodule

#!/usr/bin/env bash
# Compile and run all three testbenches. Run from the repo root:
#   bash run.sh
set -e

RTL="rtl/ntt_butterfly.v rtl/ntt_twiddle_rom.v rtl/ntt_addr_gen.v rtl/ntt_top.v"

echo "$ vvp sim_butterfly"
iverilog -o sim_butterfly rtl/ntt_butterfly.v tb/tb_butterfly.v
vvp sim_butterfly

echo
echo "$ vvp sim_addr"
iverilog -o sim_addr rtl/ntt_addr_gen.v tb/tb_addr_gen.v
vvp sim_addr

echo
echo "$ vvp sim_top"
iverilog -o sim_top $RTL tb/tb_ntt_top.v
vvp sim_top

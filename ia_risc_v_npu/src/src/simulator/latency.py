LATENCY_TABLE = {
    # ALU instructions
    "ADD": 1,
    "SUB": 1,
    "AND": 1,
    "OR": 1,
    "XOR": 1,

    # Memory access instructions
    "LD": 2,
    "SD": 2,
    "LW": 2,
    "SW": 2,

    # Branch instructions
    "BEQ": 1,
    "BNE": 1,
    "JAL": 1,
    "JALR": 1,

    # Multiplication/Division instructions
    "MUL": 3,
    "DIV": 10,
}

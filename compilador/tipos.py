"""
OxigenScript — Tipos del lenguaje.
"""


class Tipo:
    I32 = 'i32'
    F64 = 'f64'
    BOOL = 'bool'
    CHAR = 'char'
    STRING = 'String'

    # Compuestos 
    ARREGLO = 'arreglo'
    STRUCT = 'struct'

    # Tipo del resultado de una operaciopn que nada que cer
    NULO = 'None'


# Valores por defecto de las variables declaradas sin inicializar
VALOR_POR_DEFECTO = {
    Tipo.I32: 0,
    Tipo.F64: 0.0,
    Tipo.BOOL: False,
    Tipo.STRING: '',
    # acordarme que char no tiene valor por defecto
}

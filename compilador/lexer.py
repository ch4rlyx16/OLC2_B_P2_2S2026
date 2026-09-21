"""
OxigenScript — Analizador léxico

"""

import ply.lex as lex

from .errores import errores


# ---------------------------------------------------------------------------
# Palabras reservadas
# ---------------------------------------------------------------------------
reservadas = {
    # estructura
    'fn': 'FN',
    'struct': 'STRUCT',
    'let': 'LET',
    'mut': 'MUT',
    # control de flujo
    'if': 'IF',
    'else': 'ELSE',
    'while': 'WHILE',
    'loop': 'LOOP',
    'for': 'FOR',
    'in': 'IN',
    'match': 'MATCH',
    # transferencia
    'break': 'BREAK',
    'continue': 'CONTINUE',
    'return': 'RETURN',
    # literales booleanos
    'true': 'TRUE',
    'false': 'FALSE',
    # tipos primitivos
    'i32': 'TIPO_I32',
    'f64': 'TIPO_F64',
    'bool': 'TIPO_BOOL',
    'char': 'TIPO_CHAR',
    'String': 'TIPO_STRING',
}

tokens = [
    # literales e identificadores
    'IDENTIFICADOR',
    'MACRO',          
    'ETIQUETA',      
    'ENTERO',
    'DECIMAL',
    'CADENA',
    'CARACTER',
    'GUION_BAJO',     

    # aritméticos
    'MAS', 'MENOS', 'POR', 'DIV', 'MOD',

    # asignación
    'IGUAL',
    'MAS_IGUAL', 'MENOS_IGUAL', 'POR_IGUAL', 'DIV_IGUAL', 'MOD_IGUAL',

    # relacionales
    'IGUAL_IGUAL', 'DIFERENTE', 'MENOR', 'MENOR_IGUAL', 'MAYOR', 'MAYOR_IGUAL',

    # lógicos
    'AND', 'OR', 'NOT',

    # agrupación
    'PAR_IZQ', 'PAR_DER', 'LLAVE_IZQ', 'LLAVE_DER', 'COR_IZQ', 'COR_DER',

    # puntuación
    'PUNTO_COMA', 'COMA', 'DOS_PUNTOS', 'DOBLE_DOS_PUNTOS',
    'PUNTO', 'RANGO', 'FLECHA', 'FLECHA_GORDA', 'AMPERSAND',
] + list(reservadas.values())


# ---------------------------------------------------------------------------
# Reglas simples 
# ---------------------------------------------------------------------------

# aritméticos y asignación compuesta
t_MAS_IGUAL = r'\+='
t_MENOS_IGUAL = r'-='
t_POR_IGUAL = r'\*='
t_DIV_IGUAL = r'/='
t_MOD_IGUAL = r'%='
t_MAS = r'\+'
t_MENOS = r'-'
t_POR = r'\*'
t_DIV = r'/'
t_MOD = r'%'

# relacionales y asignación simple
t_IGUAL_IGUAL = r'=='
t_DIFERENTE = r'!='
t_MENOR_IGUAL = r'<='
t_MAYOR_IGUAL = r'>='
t_FLECHA_GORDA = r'=>'
t_MENOR = r'<'
t_MAYOR = r'>'
t_IGUAL = r'='

# lógicos
t_AND = r'&&'
t_OR = r'\|\|'
t_NOT = r'!'
t_AMPERSAND = r'&'          # préstamo en los slices

# agrupación
t_PAR_IZQ = r'\('
t_PAR_DER = r'\)'
t_LLAVE_IZQ = r'\{'
t_LLAVE_DER = r'\}'
t_COR_IZQ = r'\['
t_COR_DER = r'\]'

# puntuación
t_DOBLE_DOS_PUNTOS = r'::'   
t_RANGO = r'\.\.'          
t_FLECHA = r'->'             # fn f() -> i32
t_PUNTO_COMA = r';'
t_COMA = r','
t_DOS_PUNTOS = r':'
t_PUNTO = r'\.'

t_ignore = ' \t\r'


# ---------------------------------------------------------------------------
# Utilidad de columnas
# ---------------------------------------------------------------------------

def encontrar_columna(entrada, lexpos):
    """Convierte una posición absoluta del texto en número de columnas"""
    inicio_de_linea = entrada.rfind('\n', 0, lexpos)
    return lexpos - inicio_de_linea


# ---------------------------------------------------------------------------
# Escapes
# ---------------------------------------------------------------------------

_ESCAPES = {
    'n': '\n',
    't': '\t',
    'r': '\r',
    '0': '\0',
    '\\': '\\',
    '"': '"',
    "'": "'",
}


def _procesar_escapes(texto, linea, columna_base):
    """Traduce \\n, \\t, \\", \\\\ ... a los caracteres reales.
    """
    resultado = []
    i = 0
    while i < len(texto):
        if texto[i] == '\\' and i + 1 < len(texto):
            simbolo = texto[i + 1]
            if simbolo in _ESCAPES:
                resultado.append(_ESCAPES[simbolo])
            else:
                errores.lexico(
                    f"Secuencia de escape desconocida: '\\{simbolo}'.",
                    linea, columna_base + i, f"\\{simbolo}")
                resultado.append(simbolo)   # y ercuperamos
            i += 2
        else:
            resultado.append(texto[i])
            i += 1
    return ''.join(resultado)


# ---------------------------------------------------------------------------
# Reglas de función 
# ---------------------------------------------------------------------------

def t_comentario_bloque(t):
    r'/\*'
    datos = t.lexer.lexdata
    pos = t.lexer.lexpos          # justo después del /*
    profundidad = 1

    while pos < len(datos) and profundidad > 0:
        if datos.startswith('/*', pos):
            profundidad += 1
            pos += 2
        elif datos.startswith('*/', pos):
            profundidad -= 1
            pos += 2
        else:
            pos += 1

    if profundidad > 0:
        # Nunca cerró: error léxico 
        columna = encontrar_columna(datos, t.lexpos)
        errores.lexico("Comentario de bloque sin cerrar: falta '*/'.",
                       t.lineno, columna, '/*')
        t.lexer.lexpos = len(datos)
        return

    t.lexer.lineno += datos.count('\n', t.lexpos, pos)
    t.lexer.lexpos = pos


def t_comentario_linea(t):
    r'//[^\n]*'
    pass


def t_RAW_CADENA(t):
    r'r\#*"'
    numeral = t.value.count('#')
    cierre = '"' + '#' * numeral
    datos = t.lexer.lexdata
    inicio = t.lexer.lexpos            # justo después de la comilla de apertura
    fin = datos.find(cierre, inicio)

    if fin == -1:
        columna = encontrar_columna(datos, t.lexpos)
        errores.lexico(f"Raw string sin cerrar: falta {cierre!r}.",
                       t.lineno, columna, t.value)
        t.lexer.lexpos = len(datos)
        return None

    t.value = datos[inicio:fin]        
    t.type = 'CADENA'
    t.lexer.lineno += t.value.count('\n')
    t.lexer.lexpos = fin + len(cierre)
    return t


def t_CADENA(t):
    r'"([^"\\\n]|\\.)*"'
    # `\\.` permite que un \" quede adentro sin cerrar la cadena.
    columna = encontrar_columna(t.lexer.lexdata, t.lexpos)
    t.value = _procesar_escapes(t.value[1:-1], t.lineno, columna + 1)
    return t


def t_cadena_sin_cerrar(t):
    r'"'
    # Llegó una comilla que la regla anterior no pudo cerrar
    columna = encontrar_columna(t.lexer.lexdata, t.lexpos)
    errores.lexico('Cadena sin cerrar: falta la comilla doble de cierre.',
                   t.lineno, columna, '"')
    # Se descarta hasta el fin de línea y se sigue analizando
    fin_linea = t.lexer.lexdata.find('\n', t.lexer.lexpos)
    t.lexer.lexpos = len(t.lexer.lexdata) if fin_linea == -1 else fin_linea


def t_CARACTER(t):
    r"'([^'\\\n]|\\.)'"
    columna = encontrar_columna(t.lexer.lexdata, t.lexpos)
    t.value = _procesar_escapes(t.value[1:-1], t.lineno, columna + 1)
    return t


def t_ETIQUETA(t):
    r"'[a-zA-Z_][a-zA-Z_0-9]*"
    # Etiquetas de loop
    datos = t.lexer.lexdata
    if t.lexer.lexpos < len(datos) and datos[t.lexer.lexpos] == "'":
        columna = encontrar_columna(datos, t.lexpos)
        errores.lexico(
            "Un literal char tiene q tener un caracter",
            t.lineno, columna, t.value + "'")
        t.lexer.lexpos += 1            # se consume la comilla de cierre
        return None
    t.value = t.value[1:]              # se guarda sin la comilla
    return t


def t_caracter_invalido(t):
    r"'"
    datos = t.lexer.lexdata
    columna = encontrar_columna(datos, t.lexpos)
    fin_linea = datos.find('\n', t.lexer.lexpos)
    if fin_linea == -1:
        fin_linea = len(datos)
    cierre = datos.find("'", t.lexer.lexpos, fin_linea)

    if cierre == -1:
        errores.lexico('Literal de carácter sin cerrar.',
                       t.lineno, columna, "'")
        t.lexer.lexpos = fin_linea
    else:
        contenido = datos[t.lexer.lexpos:cierre]
        errores.lexico(
            "Un literal char tiene q tener un caracter",
            t.lineno, columna, f"'{contenido}'")
        t.lexer.lexpos = cierre + 1


def t_DECIMAL(t):
    r'\d+\.\d+'

    t.value = float(t.value)
    return t


def t_ENTERO(t):
    r'\d+'
    t.value = int(t.value)
    return t


def t_MACRO(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*!(?=[\(\[\{])'
    t.value = t.value[:-1]             
    return t


def t_IDENTIFICADOR(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    if t.value == '_':
        # `_`
        t.type = 'GUION_BAJO'
        return t
    #case sensitive
    t.type = reservadas.get(t.value, 'IDENTIFICADOR')
    return t


def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)


def t_error(t):
    columna = encontrar_columna(t.lexer.lexdata, t.lexpos)
    errores.lexico(f"Carácter no reconocido: '{t.value[0]}'.",
                   t.lineno, columna, t.value[0])

    t.lexer.skip(1)


lexer = lex.lex()


# ---------------------------------------------------------------------------
# API del módulo
# ---------------------------------------------------------------------------

def analizar(codigo, limpiar_errores=True):
    """Tokeniza `codigo` y devuelve la lista de tokens
    """
    if limpiar_errores:
        errores.limpiar()

    lexer.lineno = 1
    lexer.input(codigo)

    resultado = []
    for tok in lexer:
        tok.columna = encontrar_columna(codigo, tok.lexpos)
        resultado.append(tok)
    return resultado


if __name__ == '__main__':
    # solo para leer el interprete.lexer
    codigo = r'''fn main() {
    let mut saludo = String::from("Hola\nMundo");
    let ruta = r"C:\Users\Diego";
    let texto = r
    let letra: char = 'a';
    let numeros: [i32; 5] = [10, 20, 30, 40, 50];
    let parte = &numeros[1..4];

    'outer: loop {
        if x != y && z <= 3.14 {
            break 'outer;
        }
    }

    println!("{}", saludo);   // comentario de línea
    /* comentario
       de bloque */
    let total = @100;
}
'''
    tokens_encontrados = analizar(codigo)

    print(f"{'TOKEN':<20} {'VALOR':<24} {'LÍNEA':>6} {'COLUMNA':>8}")
    print("-" * 62)
    for tok in tokens_encontrados:
        print(f"{tok.type:<20} {str(tok.value)[:24]:<24} "
              f"{tok.lineno:>6} {tok.columna:>8}")

    print(f"\nErrores encontrados: {len(errores)}")
    for e in errores:
        print(e)

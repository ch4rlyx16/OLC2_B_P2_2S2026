"""
OxigenScript — Analizador sintáctico 
"""

import ply.yacc as yacc

from .lexer import tokens, lexer, encontrar_columna   # tokens pa el analizador
from .errores import errores
from .nodos import (Expresion, Literal, Identificador, Binaria, Unaria,
                    Operador, Llamada, LlamadaString, Programa, Parametro,
                    Funcion, Bloque, DeclaracionVariable, Asignacion,
                    AsignacionIndice,
                    LlamadaMacro, Retorno, ExpresionInstruccion,
                    Rango, Si, Mientras, Bucle, Para, Match, BrazoMatch,
                    Romper, Continuar, Arreglo, Indice,
                    LlamadaMetodo, Prestamo, Campo,
                    DeclaracionStruct, InstanciaStruct, AccesoCampo)
from .tipos import Tipo


# ---------------------------------------------------------------------------
# Precedencia
# Se lee de menor a mayor precedencia
# ---------------------------------------------------------------------------

precedence = (
  
    ('nonassoc', 'RANGO'),
    ('left', 'OR'),
    ('left', 'AND'),
    ('nonassoc', 'IGUAL_IGUAL', 'DIFERENTE',
                 'MENOR', 'MENOR_IGUAL', 'MAYOR', 'MAYOR_IGUAL'),
    ('left', 'MAS', 'MENOS'),
    ('left', 'POR', 'DIV', 'MOD'),
    ('right', 'NOT', 'UMENOS', 'AMPERSAND'),
    
    ('left', 'PUNTO', 'COR_IZQ'),
)


# ---------------------------------------------------------------------------
# Posiciones
# ---------------------------------------------------------------------------

def _pos(p, n):
    """Línea y columna del símbolo `n` de la produccion"""
    return p.lineno(n), encontrar_columna(p.lexer.lexdata, p.lexpos(n))


# ---------------------------------------------------------------------------
# Gramática de expresiones
# ---------------------------------------------------------------------------

def p_programa(p):
    'programa : declaraciones_globales'
    p[0] = Programa(p[1])


def p_declaraciones_globales(p):
    '''declaraciones_globales : declaraciones_globales declaracion_global
                              | declaracion_global'''
    if len(p) == 3:
        p[0] = p[1] + ([p[2]] if p[2] is not None else [])
    else:
        p[0] = [p[1]] if p[1] is not None else []


def p_declaracion_global(p):
    '''declaracion_global : funcion
                          | struct'''
    p[0] = p[1]


def p_struct(p):
    'struct : STRUCT IDENTIFICADOR LLAVE_IZQ campos LLAVE_DER'
    linea, columna = _pos(p, 1)
    p[0] = DeclaracionStruct(p[2], p[4], linea, columna)


def p_campos(p):
    '''campos : lista_campos
              | lista_campos COMA
              | '''
    
    p[0] = p[1] if len(p) > 1 else []


def p_lista_campos(p):
    '''lista_campos : lista_campos COMA campo
                    | campo'''
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_campo(p):
    'campo : IDENTIFICADOR DOS_PUNTOS tipo'
    linea, columna = _pos(p, 1)
    p[0] = Campo(p[1], p[3], linea, columna)


def p_funcion(p):
    '''funcion : FN IDENTIFICADOR PAR_IZQ parametros PAR_DER FLECHA tipo bloque
               | FN IDENTIFICADOR PAR_IZQ parametros PAR_DER bloque'''
    linea, columna = _pos(p, 1)
    if len(p) == 9:
        p[0] = Funcion(p[2], p[4], p[7], p[8], linea, columna)
    else:
        # Sin `-> tipo` no devolvemos nada
        p[0] = Funcion(p[2], p[4], None, p[6], linea, columna)


def p_parametros(p):
    '''parametros : lista_parametros
                  | '''
    p[0] = p[1] if len(p) == 2 else []


def p_lista_parametros(p):
    '''lista_parametros : lista_parametros COMA parametro
                        | parametro'''
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_parametro(p):
    'parametro : IDENTIFICADOR DOS_PUNTOS tipo'
    linea, columna = _pos(p, 1)
    p[0] = Parametro(p[1], p[3], linea, columna)


def p_tipo(p):
    '''tipo : TIPO_I32
            | TIPO_F64
            | TIPO_BOOL
            | TIPO_CHAR
            | TIPO_STRING
            | COR_IZQ tipo PUNTO_COMA ENTERO COR_DER
            | IDENTIFICADOR'''
    
    p[0] = f'[{p[2]}; {p[4]}]' if len(p) == 6 else p[1]


def p_bloque(p):
    'bloque : LLAVE_IZQ instrucciones LLAVE_DER'
    linea, columna = _pos(p, 1)
    p[0] = Bloque(p[2], linea, columna)


def p_instrucciones(p):
    '''instrucciones : instrucciones instruccion
                     | '''
    if len(p) == 3:
        # p[2] viene en None cuando la instrucción fue descartada por la regla de recuperación de errores
        p[0] = p[1] + ([p[2]] if p[2] is not None else [])
    else:
        p[0] = []


# ---------------------------------------------------------------------------
# Instrucciones
# ---------------------------------------------------------------------------

def p_instruccion(p):
    '''instruccion : declaracion_variable
                   | asignacion
                   | bloque
                   | retorno
                   | macro_instruccion
                   | expresion_instruccion
                   | si
                   | ciclo
                   | match_stmt
                   | romper
                   | continuar'''
    p[0] = p[1]


def p_instruccion_error(p):
    'instruccion : error PUNTO_COMA'
    # modo panik
    p[0] = None


def p_declaracion_variable(p):
    '''declaracion_variable : LET mutabilidad IDENTIFICADOR DOS_PUNTOS tipo IGUAL expresion_valor PUNTO_COMA
                            | LET mutabilidad IDENTIFICADOR IGUAL expresion_valor PUNTO_COMA
                            | LET mutabilidad IDENTIFICADOR DOS_PUNTOS tipo PUNTO_COMA
                            | LET mutabilidad IDENTIFICADOR PUNTO_COMA'''
    linea, columna = _pos(p, 1)

    if len(p) == 9:                             # let [mut] id : tipo = expr;
        p[0] = DeclaracionVariable(p[3], p[5], p[7], p[2], linea, columna)
    elif len(p) == 7 and p.slice[4].type == 'IGUAL':
        p[0] = DeclaracionVariable(p[3], None, p[5], p[2], linea, columna)
    elif len(p) == 7:                           # let [mut] id : tipo;
        p[0] = DeclaracionVariable(p[3], p[5], None, p[2], linea, columna)
    else:                                       # let [mut] id;
        p[0] = DeclaracionVariable(p[3], None, None, p[2], linea, columna)


def p_mutabilidad(p):
    '''mutabilidad : MUT
                   | '''
    p[0] = len(p) == 2


def p_asignacion(p):
    '''asignacion : IDENTIFICADOR IGUAL expresion_valor PUNTO_COMA
                  | IDENTIFICADOR MAS_IGUAL expresion PUNTO_COMA
                  | IDENTIFICADOR MENOS_IGUAL expresion PUNTO_COMA
                  | IDENTIFICADOR POR_IGUAL expresion PUNTO_COMA
                  | IDENTIFICADOR DIV_IGUAL expresion PUNTO_COMA
                  | IDENTIFICADOR MOD_IGUAL expresion PUNTO_COMA'''
    linea, columna = _pos(p, 1)
    p[0] = Asignacion(p[1], p[2], p[3], linea, columna)


def p_asignacion_indice(p):
    '''asignacion : expresion COR_IZQ expresion COR_DER IGUAL expresion_valor PUNTO_COMA'''
    # La posicion se toma del '[' porque p[1] es un no terminal y PLY no les
    # guarda linea ni columna.
    linea, columna = _pos(p, 2)
    p[0] = AsignacionIndice(p[1], p[3], p[6], linea, columna)


def p_retorno(p):
    '''retorno : RETURN expresion_valor PUNTO_COMA
               | RETURN PUNTO_COMA'''
    linea, columna = _pos(p, 1)
    p[0] = Retorno(p[2] if len(p) == 4 else None, linea, columna)


def p_macro_llamada(p):
    'macro_llamada : MACRO PAR_IZQ argumentos PAR_DER'
    linea, columna = _pos(p, 1)
    p[0] = LlamadaMacro(p[1], p[3], linea, columna)


def p_macro_instruccion(p):
    'macro_instruccion : macro_llamada PUNTO_COMA'
    p[0] = p[1]


# ---------------------------------------------------------------------------
# Control de flujo
# ---------------------------------------------------------------------------

def p_si(p):
    '''si : IF expresion bloque
          | IF expresion bloque ELSE bloque
          | IF expresion bloque ELSE si'''
    linea, columna = _pos(p, 1)
    sino = p[5] if len(p) == 6 else None
    p[0] = Si(p[2], p[3], sino, linea, columna)


def p_ciclo(p):
    '''ciclo : etiqueta_opcional WHILE expresion bloque
             | etiqueta_opcional LOOP bloque
             | etiqueta_opcional FOR IDENTIFICADOR IN expresion bloque'''

    etiqueta = p[1]
    tipo = p.slice[2].type
    linea, columna = _pos(p, 2)

    if tipo == 'WHILE':
        p[0] = Mientras(p[3], p[4], etiqueta, linea, columna)
    elif tipo == 'LOOP':
        p[0] = Bucle(p[3], etiqueta, linea, columna)
    else:
        p[0] = Para(p[3], p[5], p[6], etiqueta, linea, columna)

def p_etiqueta_opcional(p):
    '''etiqueta_opcional : ETIQUETA DOS_PUNTOS
                         | '''
    p[0] = p[1] if len(p) == 3 else None


def p_romper(p):
    '''romper : BREAK PUNTO_COMA
              | BREAK ETIQUETA PUNTO_COMA'''
    linea, columna = _pos(p, 1)
    p[0] = Romper(p[2] if len(p) == 4 else None, linea, columna)


def p_continuar(p):
    '''continuar : CONTINUE PUNTO_COMA
                 | CONTINUE ETIQUETA PUNTO_COMA'''
    linea, columna = _pos(p, 1)
    p[0] = Continuar(p[2] if len(p) == 4 else None, linea, columna)


def p_match(p):
    'match_stmt : MATCH expresion LLAVE_IZQ brazos LLAVE_DER'
    linea, columna = _pos(p, 1)
    p[0] = Match(p[2], p[4], linea, columna)


def p_brazos(p):
    '''brazos : brazos brazo
              | '''
    p[0] = p[1] + [p[2]] if len(p) == 3 else []


def p_brazo(p):
    '''brazo : patron FLECHA_GORDA bloque
             | patron FLECHA_GORDA bloque COMA
             | patron FLECHA_GORDA macro_llamada COMA
             | patron FLECHA_GORDA expresion COMA'''
    p[0] = BrazoMatch(p[1], p[3], p[1].linea if p[1] else 0,
                      p[1].columna if p[1] else 0)


def p_patron(p):
    '''patron : expresion
              | GUION_BAJO'''
    p[0] = None if p.slice[1].type == 'GUION_BAJO' else p[1]




def p_expresion_instruccion(p):
    'expresion_instruccion : expresion PUNTO_COMA'
    p[0] = ExpresionInstruccion(p[1], p[1].linea, p[1].columna)


# ---------------------------------------------------------------------------
# Expresiones
# ---------------------------------------------------------------------------

def p_expresion_binaria(p):
    '''expresion : expresion MAS expresion
                 | expresion MENOS expresion
                 | expresion POR expresion
                 | expresion DIV expresion
                 | expresion MOD expresion
                 | expresion IGUAL_IGUAL expresion
                 | expresion DIFERENTE expresion
                 | expresion MENOR expresion
                 | expresion MENOR_IGUAL expresion
                 | expresion MAYOR expresion
                 | expresion MAYOR_IGUAL expresion
                 | expresion AND expresion
                 | expresion OR expresion'''

    linea, columna = _pos(p, 2)
    p[0] = Binaria(p[1], p[2], p[3], linea, columna)


def p_expresion_negativo(p):
    'expresion : MENOS expresion %prec UMENOS'
    linea, columna = _pos(p, 1)
    p[0] = Unaria(Operador.NEGATIVO, p[2], linea, columna)


def p_expresion_not(p):
    'expresion : NOT expresion'
    linea, columna = _pos(p, 1)
    p[0] = Unaria(Operador.NOT, p[2], linea, columna)


def p_expresion_arreglo(p):
    '''expresion : COR_IZQ argumentos COR_DER
                 | COR_IZQ expresion PUNTO_COMA expresion COR_DER'''

    linea, columna = _pos(p, 1)
    if len(p) == 4:
        p[0] = Arreglo(p[2], None, linea, columna)
    else:
        p[0] = Arreglo([p[2]], p[4], linea, columna)


def p_expresion_indice(p):
    'expresion : expresion COR_IZQ expresion COR_DER'
  
    linea, columna = _pos(p, 2)
    p[0] = Indice(p[1], p[3], linea, columna)


def p_expresion_metodo(p):
    'expresion : expresion PUNTO IDENTIFICADOR PAR_IZQ argumentos PAR_DER'
    linea, columna = _pos(p, 2)
    p[0] = LlamadaMetodo(p[1], p[3], p[5], linea, columna)


def p_expresion_campo(p):
    'expresion : expresion PUNTO IDENTIFICADOR'
   
    linea, columna = _pos(p, 2)
    p[0] = AccesoCampo(p[1], p[3], linea, columna)


def p_instancia(p):
    'instancia : IDENTIFICADOR LLAVE_IZQ valores_campo LLAVE_DER'
    
    linea, columna = _pos(p, 1)
    p[0] = InstanciaStruct(p[1], p[3], linea, columna)


def p_expresion_valor(p):
    '''expresion_valor : expresion
                       | instancia'''
    p[0] = p[1]


def p_valores_campo(p):
    '''valores_campo : lista_valores_campo
                     | lista_valores_campo COMA
                     | '''
    p[0] = p[1] if len(p) > 1 else []


def p_lista_valores_campo(p):
    '''lista_valores_campo : lista_valores_campo COMA valor_campo
                           | valor_campo'''
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_valor_campo(p):
    'valor_campo : IDENTIFICADOR DOS_PUNTOS expresion_valor'
    p[0] = (p[1], p[3])


def p_expresion_prestamo(p):
    'expresion : AMPERSAND expresion'
    linea, columna = _pos(p, 1)
    p[0] = Prestamo(p[2], linea, columna)


def p_expresion_rango(p):
    'expresion : expresion RANGO expresion'
    linea, columna = _pos(p, 2)
    p[0] = Rango(p[1], p[3], linea, columna)


def p_expresion_agrupacion(p):
    'expresion : PAR_IZQ expresion PAR_DER'

    p[0] = p[2]


def p_expresion_identificador(p):
    'expresion : IDENTIFICADOR'
    linea, columna = _pos(p, 1)
    p[0] = Identificador(p[1], linea, columna)


def p_expresion_llamada(p):
    'expresion : IDENTIFICADOR PAR_IZQ argumentos PAR_DER'
    linea, columna = _pos(p, 1)
    p[0] = Llamada(p[1], p[3], linea, columna)


def p_expresion_string(p):
    '''expresion : TIPO_STRING DOBLE_DOS_PUNTOS IDENTIFICADOR PAR_IZQ argumentos PAR_DER'''

    linea, columna = _pos(p, 1)
    p[0] = LlamadaString(p[3], p[5], linea, columna)


def p_argumentos(p):
    '''argumentos : lista_argumentos
                  | '''
    p[0] = p[1] if len(p) == 2 else []


def p_lista_argumentos(p):
    '''lista_argumentos : lista_argumentos COMA expresion_valor
                        | expresion_valor'''
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_expresion_literal(p):
    '''expresion : ENTERO
                 | DECIMAL
                 | CADENA
                 | CARACTER'''

    tipos = {
        'ENTERO': Tipo.I32,
        'DECIMAL': Tipo.F64,
        'CADENA': Tipo.STRING,
        'CARACTER': Tipo.CHAR,
    }
    linea, columna = _pos(p, 1)
    p[0] = Literal(p[1], tipos[p.slice[1].type], linea, columna)


def p_expresion_booleano(p):
    '''expresion : TRUE
                 | FALSE'''
 
    linea, columna = _pos(p, 1)
    p[0] = Literal(p[1] == 'true', Tipo.BOOL, linea, columna)


# ---------------------------------------------------------------------------
# Errores sintácticos
# ---------------------------------------------------------------------------

def p_error(p):
    if p is None:
        errores.sintactico(
            'Fin de archivo inesperado: falta cerrar alguna llave o instrucción.',
            lexer.lineno, 1)
        return

    columna = encontrar_columna(p.lexer.lexdata, p.lexpos)
    errores.sintactico(
        f"No se esperaba '{p.value}' en esta posición.",
        p.lineno, columna, str(p.value))

# ---------------------------------------------------------------------------
# Construcción
# ---------------------------------------------------------------------------

parser = yacc.yacc(start='programa')


def analizar(codigo):
    """Parsea un programa completo y devuelve la raíz del AST 
    """
    errores.limpiar()
    lexer.lineno = 1
    return parser.parse(codigo, lexer=lexer)


def analizar_expresion(codigo):
    """Parsea UNA expresión suelta para pruebas"""
    errores.limpiar()
    lexer.lineno = 1
    arbol = parser_expresion.parse(codigo, lexer=lexer)
    return None if errores.hay_errores() else arbol

parser_expresion = yacc.yacc(start='expresion', tabmodule='parsetab_expresion',
                             debugfile='parser_expresion.out',
                             errorlog=yacc.NullLogger())


if __name__ == '__main__':
    from .nodos import imprimir_arbol, validar_arbol

    print('#' * 64)
    print('  EXPRESIONES (tabla de precedencia)')
    print('#' * 64)
    for fuente in ['2 + 3 * 4', '10 - 3 - 2', '-x * 2',
                   'a + 1 > b * 2 && !activo || c == 3']:
        print(f'\n  {fuente}')
        arbol = analizar_expresion(fuente)
        if arbol:
            print(imprimir_arbol(arbol))
        for e in errores:
            print(e)

    print('\n' + '#' * 64)
    print('  PROGRAMA COMPLETO')
    print('#' * 64)
    programa = '''
fn sumar(a: i32, b: i32) -> i32 {
    return a + b;
}

fn main() {
    let entero: i32 = 10;
    let mut acumulador = 0;
    let nombre = String::from("Ana");
    let contador: i32;

    acumulador += sumar(10, 5);
    println!("{}", acumulador);
    saludar(nombre);
}
'''
    arbol = analizar(programa)
    print(imprimir_arbol(arbol))
    print(f'\nErrores: {len(errores)}')
    sospechosos = validar_arbol(arbol)
    print('Nodos mal construidos:', sospechosos if sospechosos else 'ninguno')

    print('\n' + '#' * 64)
    print('  RECUPERACIÓN DE ERRORES')
    print('#' * 64)
    roto = '''
fn main() {
    let x = 10
    let y: i32 = 20;
    let z = ;
    println!("{}", y);
    let w = 5 +;
}
'''
    arbol = analizar(roto)
    print(imprimir_arbol(arbol))
    print(f'\nErrores: {len(errores)}')
    for e in errores:
        print(e)

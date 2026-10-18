from .tipos import Tipo
from .errores import errores
from .entorno import Entorno

class Nodo: 
    def __init__ (self, linea = 0, columna = 0):
        self.linea = linea 
        self.columna = columna

    def generar(self, gen):
        raise NotImplementedError(f"{type(self).__name__} todavia no implementa generar()")

    def etiqueta(self):
        return type(self).__name__ 

    def hijos(self):
        return[]

class Expresion(Nodo):
    """deja su resultado en w0"""
    tipo = Tipo.I32

class Instruccion(Nodo):
    """el efecto"""


class Literal(Expresion):
    def __init__(self, valor, tipo, linea=0, columna=0):
        super().__init__(linea, columna)
        self.valor = valor
        self.tipo = tipo

    def etiqueta(self):
        return f'Literal\n{self.valor}'

    def generar(self, gen):
        if self.tipo == Tipo.I32:
            gen.emitir(f'mov w0, #{self.valor}', f'literal {self.valor}')
        elif self.tipo == Tipo.BOOL:
            numero = 1 if self.valor else 0
            gen.emitir(f'mov w0, #{numero}', f'literal {self.valor}')
        elif self.tipo == Tipo.CHAR:
            gen.emitir(f'mov w0, #{ord(self.valor)}', f"literal '{self.valor}'")
        elif self.tipo == Tipo.STRING:
            nombre = gen.cadena(self.valor)
            gen.emitir(f'ldr x0, ={nombre}', 'direccion del texto')

class Binaria(Expresion):
    def __init__(self, izquierda, operador, derecha, linea=0, columna=0):
        super().__init__(linea, columna)
        if operador in ('==', '!=', '<', '<=', '>', '>=', '&&', '||'):
            self.tipo = Tipo.BOOL
        else:
            self.tipo = Tipo.I32
        self.izquierda = izquierda
        self.operador = operador
        self.derecha = derecha

    def etiqueta(self):
        return f'Binaria\n{self.operador}'

    def hijos(self):
        return [self.izquierda, self.derecha]

    def generar(self, gen):
        if self.operador in ('&&', '||'):
            self._logico(gen)
            return

        gen.comentario(f'inicio operacion {self.operador}')
        self.izquierda.generar(gen)
        gen.emitir('str w0, [sp, #-16]!', 'guardar lado izquierdo')
        self.derecha.generar(gen)
        gen.emitir('ldr w1, [sp], #16', 'recuperar lado izquierdo')

        if self.operador == '+':
            gen.emitir('add w0, w1, w0')
        elif self.operador == '-':
            gen.emitir('sub w0, w1, w0')
        elif self.operador == '*':
            gen.emitir('mul w0, w1, w0')
        elif self.operador == '/':
            gen.emitir('sdiv w0, w1, w0')
        elif self.operador == '%':
            gen.emitir('sdiv w2, w1, w0', 'cociente')
            gen.emitir('msub w0, w2, w0, w1', 'resto')
        else:
            condiciones = {'==': 'eq', '!=': 'ne', '<': 'lt',
                           '<=': 'le', '>': 'gt', '>=': 'ge'}
            gen.emitir('cmp w1, w0', f'comparar izquierda {self.operador} derecha')
            gen.emitir(f'cset w0, {condiciones[self.operador]}',
                       'w0 = 1 si se cumple, 0 si no')

    def _logico(self, gen):
        gen.comentario(f'inicio operacion {self.operador} (corto circuito)')
        salida = gen.nueva_etiqueta('Llog')
        corto = gen.nueva_etiqueta('Lcorto')

        atajo = 'eq' if self.operador == '&&' else 'ne'

        self.izquierda.generar(gen)
        gen.emitir('cmp w0, #0')
        gen.emitir(f'b.{atajo} {corto}', 'ya se sabe el resultado')

        self.derecha.generar(gen)
        gen.emitir('cmp w0, #0')
        gen.emitir('cset w0, ne', 'normalizar a 0 o 1')
        gen.emitir(f'b {salida}')

        gen.etiqueta(corto)
        gen.emitir(f'mov w0, #{0 if self.operador == "&&" else 1}',
                   'resultado del corto circuito')

        gen.etiqueta(salida)

class LlamadaMacro(Instruccion):
    def __init__(self, nombre, argumentos, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.argumentos = argumentos

    def etiqueta(self):
        return f'Macro\n{self.nombre}!'

    def hijos(self):
        return list(self.argumentos)

    def generar(self, gen):
        gen.comentario(f'{self.nombre}!')

        for argumento in self.argumentos:
            argumento.generar(gen)

            if argumento.tipo == Tipo.STRING:
                gen.emitir('mov x1, x0', 'print_cstr recibe la direccion en x1')
                gen.emitir('bl print_cstr')
            else:
                gen.emitir('bl print_num')

        gen.emitir('bl print_nl', 'salto de linea')


class Bloque(Instruccion):
    def __init__(self, instrucciones, linea=0, columna=0):
        super().__init__(linea, columna)
        self.instrucciones = instrucciones

    def etiqueta(self):
        return 'Bloque'

    def hijos(self):
        return list(self.instrucciones)

    def generar(self, gen):
        gen.entorno.abrir()
        for instruccion in self.instrucciones:
            instruccion.generar(gen)
        gen.entorno.cerrar()

class Funcion(Nodo):
    def __init__(self, nombre, parametros, tipo_retorno, cuerpo,
                 linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.parametros = parametros
        self.tipo_retorno = tipo_retorno
        self.cuerpo = cuerpo

    def etiqueta(self):
        return f'Funcion\n{self.nombre}'

    def hijos(self):
        return [self.cuerpo]

    def generar(self, gen):
        if self.nombre != 'main':
            return                      

        gen.entorno = Entorno()

        gen.comentario('=== funcion main (punto de entrada) ===')
        gen.etiqueta('_start')
        gen.emitir('mov x29, sp', 'x29 queda fijo: base del marco')
        hueco = gen.marcador('espacio para variables')

        self.cuerpo.generar(gen)

        gen.parchar(hueco, f'sub sp, sp, #{gen.entorno.espacio()}',
                    f'{gen.entorno.maximo} bytes usados, alineado a 16')

        gen.comentario('salir del programa')
        gen.emitir('mov x0, #0', 'codigo de salida 0')
        gen.emitir('mov x8, #93', 'syscall exit')
        gen.emitir('svc #0', 'llamar al kernel')

class Programa(Nodo):
    def __init__(self, declaraciones):
        super().__init__(1, 1)
        self.declaraciones = declaraciones

    def etiqueta(self):
        return 'Programa'

    def hijos(self):
        return list(self.declaraciones)

    def generar(self, gen):
        for declaracion in self.declaraciones:
            declaracion.generar(gen)

class Operador:
    SUMA = '+'
    RESTA = '-'
    MULTIPLICACION = '*'
    DIVISION = '/'
    MODULO = '%'
    IGUAL_IGUAL = '=='
    DIFERENTE = '!='
    MENOR = '<'
    MENOR_IGUAL = '<='
    MAYOR = '>'
    MAYOR_IGUAL = '>='
    AND = '&&'
    OR = '||'
    NOT = '!'
    NEGATIVO = '-'

class Identificador(Expresion):
    def __init__(self, nombre, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre

    def etiqueta(self):
        return f'Identificador\n{self.nombre}'
    
    def generar(self, gen):
        variable = gen.entorno.buscar(self.nombre)

        if variable is None:
            errores.semantico(
                f"La variable '{self.nombre}' no esta declarada.",
                self.linea, self.columna, self.nombre)
            gen.emitir('mov w0, #0', 'valor de recuperacion')
            return

        self.tipo = variable.tipo
        gen.emitir(f'ldr x0, {variable.direccion()}',
                   f'leer {self.nombre}')


class Unaria(Expresion):
    def __init__(self, operador, operando, linea=0, columna=0):
        super().__init__(linea, columna)
        self.operador = operador
        self.operando = operando

    def etiqueta(self):
        return f'Unaria\n{self.operador}'

    def hijos(self):
        return [self.operando]
    
    def generar(self, gen):
        self.operando.generar(gen)

        if self.operador == '-':
            self.tipo = Tipo.I32
            gen.emitir('neg w0, w0', 'cambiar de signo')
        elif self.operador == '!':
            self.tipo = Tipo.BOOL
            gen.emitir('cmp w0, #0')
            gen.emitir('cset w0, eq', 'invertir: 0 pasa a 1 y al reves')


class Llamada(Expresion):
    def __init__(self, nombre, argumentos, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.argumentos = argumentos

    def etiqueta(self):
        return f'Llamada\n{self.nombre}'

    def hijos(self):
        return list(self.argumentos)


class LlamadaString(Expresion):
    tipo = Tipo.STRING

    def __init__(self, metodo, argumentos, linea=0, columna=0):
        super().__init__(linea, columna)
        self.metodo = metodo
        self.argumentos = argumentos

    def etiqueta(self):
        return f'String::{self.metodo}'

    def hijos(self):
        return list(self.argumentos)


class Parametro(Nodo):
    def __init__(self, nombre, tipo, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.tipo = tipo

    def etiqueta(self):
        return f'Parametro\n{self.nombre}: {self.tipo}'


class DeclaracionVariable(Instruccion):
    def __init__(self, nombre, tipo, expresion, mutable, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.tipo = tipo
        self.expresion = expresion
        self.mutable = mutable

    def etiqueta(self):
        mut = 'mut ' if self.mutable else ''
        tipo = f': {self.tipo}' if self.tipo else ''
        return f'Declaracion\nlet {mut}{self.nombre}{tipo}'

    def hijos(self):
        return [self.expresion] if self.expresion else []

    def generar(self, gen):
        entorno = gen.entorno

        if entorno.declarada_aqui(self.nombre):
            errores.semantico(
                f"La variable '{self.nombre}' ya fue declarada en este ambito.",
                self.linea, self.columna, self.nombre)
            return

        if self.expresion:
            self.expresion.generar(gen)
            tipo = self.tipo or self.expresion.tipo
        else:
            gen.emitir('mov w0, #0', 'sin valor inicial')
            tipo = self.tipo or Tipo.I32

        variable = entorno.declarar(self.nombre, tipo, self.mutable)
        gen.emitir(f'str x0, {variable.direccion()}',
                   f'let {self.nombre} = ...')


class Asignacion(Instruccion):
    def __init__(self, nombre, operador, expresion, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.operador = operador
        self.expresion = expresion

    def etiqueta(self):
        return f'Asignacion\n{self.nombre} {self.operador}'

    def hijos(self):
        return [self.expresion]

    def generar(self, gen):
        variable = gen.entorno.buscar(self.nombre)

        if variable is None:
            errores.semantico(
                f"La variable '{self.nombre}' no esta declarada.",
                self.linea, self.columna, self.nombre)
            return

        if not variable.mutable:
            errores.semantico(
                f"'{self.nombre}' no es mutable: declarala con 'let mut'.",
                self.linea, self.columna, self.nombre)
            return

        self.expresion.generar(gen)

        if self.operador != '=':
            gen.emitir('mov w1, w0', 'el lado derecho pasa a w1')
            gen.emitir(f'ldr x0, {variable.direccion()}',
                       f'valor actual de {self.nombre}')
            simbolo = self.operador[0]
            if simbolo == '+':
                gen.emitir('add w0, w0, w1')
            elif simbolo == '-':
                gen.emitir('sub w0, w0, w1')
            elif simbolo == '*':
                gen.emitir('mul w0, w0, w1')
            elif simbolo == '/':
                gen.emitir('sdiv w0, w0, w1')
            elif simbolo == '%':
                gen.emitir('sdiv w2, w0, w1', 'cociente')
                gen.emitir('msub w0, w2, w1, w0', 'resto = x - cociente*y')

        gen.emitir(f'str x0, {variable.direccion()}',
                   f'{self.nombre} {self.operador} ...')


class Retorno(Instruccion):
    def __init__(self, expresion, linea=0, columna=0):
        super().__init__(linea, columna)
        self.expresion = expresion

    def etiqueta(self):
        return 'Retorno'

    def hijos(self):
        return [self.expresion] if self.expresion else []


class ExpresionInstruccion(Instruccion):
    def __init__(self, expresion, linea=0, columna=0):
        super().__init__(linea, columna)
        self.expresion = expresion

    def etiqueta(self):
        return 'ExpresionInstruccion'

    def hijos(self):
        return [self.expresion]


class Rango(Expresion):
    def __init__(self, inicio, fin, linea=0, columna=0):
        super().__init__(linea, columna)
        self.inicio = inicio
        self.fin = fin

    def etiqueta(self):
        return 'Rango\n..'

    def hijos(self):
        return [self.inicio, self.fin]


class Si(Instruccion):
    def __init__(self, condicion, entonces, sino=None, linea=0, columna=0):
        super().__init__(linea, columna)
        self.condicion = condicion
        self.entonces = entonces
        self.sino = sino

    def etiqueta(self):
        return 'Si'

    def hijos(self):
        return [self.condicion, self.entonces] + ([self.sino] if self.sino else [])


class Mientras(Instruccion):
    def __init__(self, condicion, cuerpo, etiqueta=None, linea=0, columna=0):
        super().__init__(linea, columna)
        self.condicion = condicion
        self.cuerpo = cuerpo
        self.nombre_etiqueta = etiqueta

    def etiqueta(self):
        marca = f"\n'{self.nombre_etiqueta}" if self.nombre_etiqueta else ''
        return f'Mientras{marca}'

    def hijos(self):
        return [self.condicion, self.cuerpo]


class Bucle(Instruccion):
    def __init__(self, cuerpo, etiqueta=None, linea=0, columna=0):
        super().__init__(linea, columna)
        self.cuerpo = cuerpo
        self.nombre_etiqueta = etiqueta

    def etiqueta(self):
        marca = f"\n'{self.nombre_etiqueta}" if self.nombre_etiqueta else ''
        return f'Bucle{marca}'

    def hijos(self):
        return [self.cuerpo]


class Para(Instruccion):
    def __init__(self, variable, iterable, cuerpo, etiqueta=None,
                 linea=0, columna=0):
        super().__init__(linea, columna)
        self.variable = variable
        self.iterable = iterable
        self.cuerpo = cuerpo
        self.nombre_etiqueta = etiqueta

    def etiqueta(self):
        marca = f"\n'{self.nombre_etiqueta}" if self.nombre_etiqueta else ''
        return f'Para\n{self.variable}{marca}'

    def hijos(self):
        return [self.iterable, self.cuerpo]


class Match(Instruccion):
    def __init__(self, expresion, brazos, linea=0, columna=0):
        super().__init__(linea, columna)
        self.expresion = expresion
        self.brazos = brazos

    def etiqueta(self):
        return 'Match'

    def hijos(self):
        return [self.expresion] + list(self.brazos)


class BrazoMatch(Nodo):
    def __init__(self, patron, cuerpo, linea=0, columna=0):
        super().__init__(linea, columna)
        self.patron = patron
        self.cuerpo = cuerpo

    def etiqueta(self):
        return 'Brazo\n_ =>' if self.patron is None else 'Brazo\n=>'

    def hijos(self):
        return ([self.patron] if self.patron else []) + [self.cuerpo]


class Romper(Instruccion):
    def __init__(self, etiqueta=None, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre_etiqueta = etiqueta

    def etiqueta(self):
        marca = f"\n'{self.nombre_etiqueta}" if self.nombre_etiqueta else ''
        return f'Romper{marca}'


class Continuar(Instruccion):
    def __init__(self, etiqueta=None, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre_etiqueta = etiqueta

    def etiqueta(self):
        marca = f"\n'{self.nombre_etiqueta}" if self.nombre_etiqueta else ''
        return f'Continuar{marca}'


class Arreglo(Expresion):
    tipo = Tipo.ARREGLO

    def __init__(self, elementos, repeticiones=None, linea=0, columna=0):
        super().__init__(linea, columna)
        self.elementos = elementos
        self.repeticiones = repeticiones

    def etiqueta(self):
        return 'Arreglo\n[ ; ]' if self.repeticiones else 'Arreglo\n[ ]'

    def hijos(self):
        return list(self.elementos) + ([self.repeticiones]
                                       if self.repeticiones else [])


class Indice(Expresion):
    def __init__(self, arreglo, indice, linea=0, columna=0):
        super().__init__(linea, columna)
        self.arreglo = arreglo
        self.indice = indice

    def etiqueta(self):
        return 'Indice\n[ ]'

    def hijos(self):
        return [self.arreglo, self.indice]


class LlamadaMetodo(Expresion):
    def __init__(self, receptor, metodo, argumentos, linea=0, columna=0):
        super().__init__(linea, columna)
        self.receptor = receptor
        self.metodo = metodo
        self.argumentos = argumentos

    def etiqueta(self):
        return f'Metodo\n.{self.metodo}()'

    def hijos(self):
        return [self.receptor] + list(self.argumentos)


class Prestamo(Expresion):
    def __init__(self, expresion, linea=0, columna=0):
        super().__init__(linea, columna)
        self.expresion = expresion

    def etiqueta(self):
        return 'Prestamo\n&'

    def hijos(self):
        return [self.expresion]


class Campo(Nodo):
    def __init__(self, nombre, tipo, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.tipo = tipo

    def etiqueta(self):
        return f'Campo\n{self.nombre}: {self.tipo}'


class DeclaracionStruct(Nodo):
    def __init__(self, nombre, campos, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.campos = campos

    def etiqueta(self):
        return f'Struct\n{self.nombre}'

    def hijos(self):
        return list(self.campos)


class InstanciaStruct(Expresion):
    tipo = Tipo.STRUCT

    def __init__(self, nombre, valores, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.valores = valores

    def etiqueta(self):
        return f'Instancia\n{self.nombre}'

    def hijos(self):
        return [expresion for _, expresion in self.valores]


class AccesoCampo(Expresion):
    def __init__(self, objeto, campo, linea=0, columna=0):
        super().__init__(linea, columna)
        self.objeto = objeto
        self.campo = campo

    def etiqueta(self):
        return f'Campo\n.{self.campo}'

    def hijos(self):
        return [self.objeto]
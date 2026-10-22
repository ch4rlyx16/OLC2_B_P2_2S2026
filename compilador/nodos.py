from .tipos import Tipo
from .errores import errores
from .entorno import Entorno, TAMANO

NO_SOPORTADO = {
    'Rango': 'los rangos fuera de un for',
    'DeclaracionStruct': 'los structs',
    'InstanciaStruct': 'los structs',
    'AccesoCampo': 'el acceso a campos de struct',
    'LlamadaString': 'String::from',
    'Prestamo': 'los prestamos y slices (&)',
}


def _tipo_estatico(gen, expresion):
    """Averigua el tipo de una expresion SIN generar codigo para ella."""
    if isinstance(expresion, Identificador):
        variable = gen.entorno.buscar(expresion.nombre)
        if variable is not None:
            return variable.tipo
    return expresion.tipo

class Nodo: 
    def __init__ (self, linea = 0, columna = 0):
        self.linea = linea 
        self.columna = columna

    def generar(self, gen):
        nombre = type(self).__name__
        que = NO_SOPORTADO.get(nombre, nombre)
        errores.semantico(
            f'{que}: todavia no esta soportado por el compilador.',
            self.linea, self.columna, nombre)
        if isinstance(self, Expresion):
            gen.emitir('mov w0, #0', 'valor de recuperacion')


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
        else:
            errores.semantico(
                f'Los literales de tipo {self.tipo} todavia no estan '
                f'soportados (f64).',
                self.linea, self.columna, str(self.valor))
            gen.emitir('mov w0, #0', 'valor de recuperacion')

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
        if self.nombre not in ('println', 'print'):
            errores.semantico(
                f"La macro '{self.nombre}!' no existe.",
                self.linea, self.columna, self.nombre)
            return

        gen.comentario(f'{self.nombre}!')

        if self.argumentos:
            primero = self.argumentos[0]
            es_plantilla = (isinstance(primero, Literal)
                            and primero.tipo == Tipo.STRING
                            and '{}' in primero.valor)

            if es_plantilla:
                self._plantilla(gen, primero.valor, self.argumentos[1:])
            else:
                for argumento in self.argumentos:
                    self._valor(gen, argumento)

        if self.nombre == 'println':
            gen.emitir('bl print_nl', 'salto de linea')

    # ------------------------------------------------------------------

    def _plantilla(self, gen, plantilla, valores):
        """Intercala los trozos de texto con los valores."""
        trozos = plantilla.split('{}')
        huecos = len(trozos) - 1

        if huecos != len(valores):
            errores.semantico(
                f"La plantilla tiene {huecos} hueco(s) y se pasaron "
                f"{len(valores)} valor(es).",
                self.linea, self.columna, plantilla)

        for posicion, trozo in enumerate(trozos):
            self._texto(gen, trozo)
            if posicion < len(valores):
                self._valor(gen, valores[posicion])

    def _texto(self, gen, texto):
        """Imprime un literal de texto fijo."""
        if not texto:
            return
        nombre = gen.cadena(texto)
        gen.emitir(f'ldr x1, ={nombre}', 'trozo de la plantilla')
        gen.emitir('bl print_cstr')

    def _valor(self, gen, expresion):
        """Imprime una expresion segun su tipo."""
        expresion.generar(gen)

        if expresion.tipo == Tipo.STRING:
            gen.emitir('mov x1, x0', 'print_cstr recibe la direccion en x1')
            gen.emitir('bl print_cstr')

        elif expresion.tipo == Tipo.BOOL:
            verdadero = gen.cadena('true')
            falso = gen.cadena('false')
            caso_falso = gen.nueva_etiqueta('Lbool')
            fin = gen.nueva_etiqueta('Lbool')
            gen.emitir('cmp w0, #0')
            gen.emitir(f'b.eq {caso_falso}')
            gen.emitir(f'ldr x1, ={verdadero}')
            gen.emitir(f'b {fin}')
            gen.etiqueta(caso_falso)
            gen.emitir(f'ldr x1, ={falso}')
            gen.etiqueta(fin)
            gen.emitir('bl print_cstr')

        elif expresion.tipo == Tipo.CHAR:
            gen.emitir('strb w0, [sp, #-16]!', 'el caracter a la pila')
            gen.emitir('strb wzr, [sp, #1]', 'terminador nulo')
            gen.emitir('mov x1, sp', 'apuntar al caracter')
            gen.emitir('bl print_cstr')
            gen.emitir('add sp, sp, #16', 'devolver la pila')

        else:
            gen.emitir('bl print_num')


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
        gen.entorno = Entorno(gen.simbolos, self.nombre)
        salida = gen.nueva_etiqueta('Lret')
        gen.retorno = salida

        if self.nombre == 'main':
            gen.comentario('=== funcion main ===')
            gen.etiqueta('_start')
            gen.emitir('mov x29, sp', 'x29 queda fijo: base del marco')
            hueco = gen.marcador('espacio para variables')

            self._guardar_parametros(gen)
            self.cuerpo.generar(gen)

            gen.etiqueta(salida)
            gen.comentario('salir del programa')
            gen.emitir('mov x0, #0', 'codigo de salida 0')
            gen.emitir('mov x8, #93', 'syscall exit')
            gen.emitir('svc #0', 'llamar al kernel')
        else:
            gen.comentario(f'=== funcion {self.nombre} ===')
            gen.etiqueta('fn_' + self.nombre)
            gen.emitir('stp x29, x30, [sp, #-16]!',
                       'guardar marco anterior y direccion de retorno')
            gen.emitir('mov x29, sp', 'base de mi marco')
            hueco = gen.marcador('espacio para variables')

            self._guardar_parametros(gen)
            self.cuerpo.generar(gen)

            gen.etiqueta(salida)
            gen.emitir('mov sp, x29', 'soltar mis variables')
            gen.emitir('ldp x29, x30, [sp], #16',
                       'recuperar marco y direccion de retorno')
            gen.emitir('ret', 'volver a quien me llamo')

        gen.parchar(hueco, f'sub sp, sp, #{gen.entorno.espacio()}',
                    f'{gen.entorno.maximo} bytes usados, alineado a 16')

    def _guardar_parametros(self, gen):
        if len(self.parametros) > 8:
            errores.semantico(
                f"'{self.nombre}' tiene mas de 8 parametros.",
                self.linea, self.columna, self.nombre)
            return
        for indice, parametro in enumerate(self.parametros):
            # Los parametros se declaran mutables: en el cuerpo son una copia
            # local, y los arreglos llegan como puntero, asi que funciones como
            # sort_array() necesitan poder escribir sobre ellos.
            variable = gen.entorno.declarar(
                parametro.nombre, parametro.tipo, True,
                linea=parametro.linea, categoria='Parámetro')
            gen.acceso('str', f'x{indice}', variable.offset,
                       f'guardar parametro {parametro.nombre}')

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
            if isinstance(declaracion, Funcion):
                if declaracion.nombre in gen.funciones:
                    errores.semantico(
                        f"La funcion '{declaracion.nombre}' ya fue declarada.",
                        declaracion.linea, declaracion.columna,
                        declaracion.nombre)
                    continue
                gen.funciones[declaracion.nombre] = declaracion
                gen.simbolos.append({
                    'identificador': declaracion.nombre,
                    'categoria': 'Función',
                    'tipo': str(declaracion.tipo_retorno or '-'),
                    'ambito': 'global',
                    'linea': declaracion.linea,
                    'direccion': ('_start' if declaracion.nombre == 'main'
                                  else 'fn_' + declaracion.nombre),
                })


        if 'main' not in gen.funciones:
            errores.semantico('Falta la funcion main().', 1, 1)
            return

        gen.funciones['main'].generar(gen)

        for declaracion in self.declaraciones:
            if isinstance(declaracion, Funcion) and declaracion.nombre != 'main':
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
        gen.acceso('ldr', 'x0', variable.offset,
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

    def generar(self, gen):
        if self.nombre == 'typeof':
            self.tipo = Tipo.STRING
            if len(self.argumentos) != 1:
                errores.semantico(
                    "'typeof' espera 1 argumento.",
                    self.linea, self.columna, 'typeof')
                gen.emitir('mov w0, #0', 'valor de recuperacion')
                return
            tipo = _tipo_estatico(gen, self.argumentos[0])
            nombre = gen.cadena(str(tipo))
            gen.emitir(f'ldr x0, ={nombre}', f'typeof -> {tipo}')
            return

        funcion = gen.funciones.get(self.nombre)

        if funcion is None:
            errores.semantico(
                f"La funcion '{self.nombre}' no esta declarada.",
                self.linea, self.columna, self.nombre)
            gen.emitir('mov w0, #0', 'valor de recuperacion')
            return

        if len(self.argumentos) != len(funcion.parametros):
            errores.semantico(
                f"'{self.nombre}' espera {len(funcion.parametros)} "
                f"argumento(s), recibio {len(self.argumentos)}.",
                self.linea, self.columna, self.nombre)
            gen.emitir('mov w0, #0', 'valor de recuperacion')
            return

        self.tipo = funcion.tipo_retorno or Tipo.I32

        gen.comentario(f'llamada a {self.nombre}')
        for argumento in self.argumentos:
            argumento.generar(gen)
            gen.emitir('str x0, [sp, #-16]!', 'apilar argumento')

        for indice in range(len(self.argumentos) - 1, -1, -1):
            gen.emitir(f'ldr x{indice}, [sp], #16',
                       f'argumento {indice} a su registro')

        gen.emitir(f'bl fn_{self.nombre}', 'saltar guardando el retorno')



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

        variable = entorno.declarar(self.nombre, tipo, self.mutable,
                                    linea=self.linea)
        gen.acceso('str', 'x0', variable.offset,
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
            gen.acceso('ldr', 'x0', variable.offset,
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

        gen.acceso('str', 'x0', variable.offset,
                   f'{self.nombre} {self.operador} ...')

class AsignacionIndice(Instruccion):
    """a[i] = valor;  — tambien sirve para m[0][1] = valor;"""

    def __init__(self, arreglo, indice, expresion, linea=0, columna=0):
        super().__init__(linea, columna)
        self.arreglo = arreglo
        self.indice = indice
        self.expresion = expresion

    def etiqueta(self):
        return 'Asignacion\n[i] ='

    def hijos(self):
        return [self.arreglo, self.indice, self.expresion]

    def generar(self, gen):
        if isinstance(self.arreglo, Identificador):
            variable = gen.entorno.buscar(self.arreglo.nombre)
            if variable is not None and not variable.mutable:
                errores.semantico(
                    f"'{self.arreglo.nombre}' no es mutable: "
                    f"declarala con 'let mut'.",
                    self.linea, self.columna, self.arreglo.nombre)
                return

        gen.comentario('a[i] = ...')
        self.arreglo.generar(gen)
        gen.emitir('str x0, [sp, #-16]!', 'guardar el puntero')
        self.indice.generar(gen)
        gen.emitir('ldr x1, [sp], #16', 'recuperar el puntero')
        gen.emitir('add x1, x1, w0, sxtw #3', 'puntero + indice * 8')
        gen.emitir('str x1, [sp, #-16]!', 'guardar la direccion destino')
        self.expresion.generar(gen)
        gen.emitir('ldr x1, [sp], #16', 'recuperar la direccion destino')
        gen.emitir('str x0, [x1]', 'escribir el elemento')
        
class Retorno(Instruccion):
    def __init__(self, expresion, linea=0, columna=0):
        super().__init__(linea, columna)
        self.expresion = expresion

    def etiqueta(self):
        return 'Retorno'

    def hijos(self):
        return [self.expresion] if self.expresion else []

    def generar(self, gen):
        if gen.retorno is None:
            errores.semantico("'return' fuera de una funcion.",
                              self.linea, self.columna, 'return')
            return
        if self.expresion:
            self.expresion.generar(gen)
        gen.emitir(f'b {gen.retorno}', 'return')


class ExpresionInstruccion(Instruccion):
    def __init__(self, expresion, linea=0, columna=0):
        super().__init__(linea, columna)
        self.expresion = expresion

    def etiqueta(self):
        return 'ExpresionInstruccion'

    def hijos(self):
        return [self.expresion]
    
    def generar(self, gen):
        self.expresion.generar(gen)


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

    def generar(self, gen):
        gen.comentario('if')
        fin = gen.nueva_etiqueta('Lfin')

        self.condicion.generar(gen)
        gen.emitir('cmp w0, #0')

        if self.sino:
            caso_sino = gen.nueva_etiqueta('Lelse')
            gen.emitir(f'b.eq {caso_sino}', 'condicion falsa')
            self.entonces.generar(gen)
            gen.emitir(f'b {fin}', 'saltar el else')
            gen.etiqueta(caso_sino)
            self.sino.generar(gen)
        else:
            gen.emitir(f'b.eq {fin}', 'condicion falsa')
            self.entonces.generar(gen)

        gen.etiqueta(fin)


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

    def generar(self, gen):
        gen.comentario('while')
        inicio = gen.nueva_etiqueta('Lwhile')
        fin = gen.nueva_etiqueta('Lfin')

        gen.etiqueta(inicio)
        self.condicion.generar(gen)
        gen.emitir('cmp w0, #0')
        gen.emitir(f'b.eq {fin}', 'condicion falsa: salir')

        gen.bucles.append({'nombre': self.nombre_etiqueta,
                           'inicio': inicio, 'fin': fin})
        self.cuerpo.generar(gen)
        gen.bucles.pop()

        gen.emitir(f'b {inicio}', 'volver a evaluar la condicion')
        gen.etiqueta(fin)


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

    def generar(self, gen):
        gen.comentario('loop')
        inicio = gen.nueva_etiqueta('Lloop')
        fin = gen.nueva_etiqueta('Lfin')

        gen.etiqueta(inicio)

        gen.bucles.append({'nombre': self.nombre_etiqueta,
                           'inicio': inicio, 'fin': fin})
        self.cuerpo.generar(gen)
        gen.bucles.pop()

        gen.emitir(f'b {inicio}', 'repetir siempre')
        gen.etiqueta(fin)


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

    def generar(self, gen):
        if not isinstance(self.iterable, Rango):
            errores.semantico(
                "'for' solo soporta rangos de la forma a..b por ahora.",
                self.linea, self.columna, self.variable)
            return

        gen.comentario(f'for {self.variable} in rango')
        gen.entorno.abrir()

        self.iterable.inicio.generar(gen)
        contador = gen.entorno.declarar(self.variable, Tipo.I32, True,
                                        linea=self.linea)
        gen.acceso('str', 'x0', contador.offset,
                   f'{self.variable} = inicio del rango')

        self.iterable.fin.generar(gen)
        limite = gen.entorno.declarar(f'$fin_{self.variable}', Tipo.I32)
        gen.acceso('str', 'x0', limite.offset, 'limite del rango')

        inicio = gen.nueva_etiqueta('Lfor')
        paso = gen.nueva_etiqueta('Lpaso')
        fin = gen.nueva_etiqueta('Lfin')

        gen.etiqueta(inicio)
        gen.acceso('ldr', 'x0', contador.offset, f'leer {self.variable}')
        gen.acceso('ldr', 'x1', limite.offset, 'leer el limite')
        gen.emitir('cmp w0, w1')
        gen.emitir(f'b.ge {fin}', 'rango exclusivo: corta antes del limite')

        gen.bucles.append({'nombre': self.nombre_etiqueta,
                           'inicio': paso, 'fin': fin})
        self.cuerpo.generar(gen)
        gen.bucles.pop()

        gen.etiqueta(paso)
        gen.acceso('ldr', 'x0', contador.offset)
        gen.emitir('add w0, w0, #1', 'siguiente valor')
        gen.acceso('str', 'x0', contador.offset)
        gen.emitir(f'b {inicio}', 'volver a comprobar')

        gen.etiqueta(fin)
        gen.entorno.cerrar()


class Match(Instruccion):
    def __init__(self, expresion, brazos, linea=0, columna=0):
        super().__init__(linea, columna)
        self.expresion = expresion
        self.brazos = brazos

    def etiqueta(self):
        return 'Match'

    def hijos(self):
        return [self.expresion] + list(self.brazos)

    def generar(self, gen):
        gen.comentario('match')
        fin = gen.nueva_etiqueta('Lfinmatch')

        gen.entorno.abrir()
        self.expresion.generar(gen)
        oculto = gen.nueva_etiqueta('$match')
        guardado = gen.entorno.declarar(oculto, self.expresion.tipo)
        gen.acceso('str', 'x0', guardado.offset,
                   'guardar el valor evaluado del match')

        for brazo in self.brazos:
            if brazo.patron is None:
                gen.comentario('brazo _  (por defecto)')
                brazo.cuerpo.generar(gen)
                gen.emitir(f'b {fin}')
                continue

            siguiente = gen.nueva_etiqueta('Lbrazo')

            if isinstance(brazo.patron, Rango):
                gen.comentario('brazo con rango')
                brazo.patron.inicio.generar(gen)
                gen.emitir('mov w1, w0', 'inicio del rango')
                gen.acceso('ldr', 'x0', guardado.offset)
                gen.emitir('cmp w0, w1')
                gen.emitir(f'b.lt {siguiente}', 'por debajo del inicio')

                brazo.patron.fin.generar(gen)
                gen.emitir('mov w1, w0', 'fin del rango')
                gen.acceso('ldr', 'x0', guardado.offset)
                gen.emitir('cmp w0, w1')
                gen.emitir(f'b.gt {siguiente}', 'por encima del fin (inclusivo)')
            else:
                gen.comentario('brazo con valor')
                brazo.patron.generar(gen)
                gen.emitir('mov w1, w0', 'valor del patron')
                gen.acceso('ldr', 'x0', guardado.offset)
                gen.emitir('cmp w0, w1')
                gen.emitir(f'b.ne {siguiente}', 'no coincide')

            brazo.cuerpo.generar(gen)
            gen.emitir(f'b {fin}', 'brazo ejecutado: salir del match')
            gen.etiqueta(siguiente)

        gen.etiqueta(fin)
        gen.entorno.cerrar()


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

    def generar(self, gen):
        bucle = gen.bucle(self.nombre_etiqueta)
        if bucle is None:
            donde = (f"'{self.nombre_etiqueta}" if self.nombre_etiqueta
                     else 'ningun bucle')
            errores.semantico(
                f"'break' no esta dentro de {donde}.",
                self.linea, self.columna, 'break')
            return
        gen.emitir(f"b {bucle['fin']}", 'break')


class Continuar(Instruccion):
    def __init__(self, etiqueta=None, linea=0, columna=0):
        super().__init__(linea, columna)
        self.nombre_etiqueta = etiqueta

    def etiqueta(self):
        marca = f"\n'{self.nombre_etiqueta}" if self.nombre_etiqueta else ''
        return f'Continuar{marca}'

    def generar(self, gen):
        bucle = gen.bucle(self.nombre_etiqueta)
        if bucle is None:
            donde = (f"'{self.nombre_etiqueta}" if self.nombre_etiqueta
                     else 'ningun bucle')
            errores.semantico(
                f"'continue' no esta dentro de {donde}.",
                self.linea, self.columna, 'continue')
            return
        gen.emitir(f"b {bucle['inicio']}", 'continue')


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
    def generar(self, gen):
        self.tipo = Tipo.ARREGLO

        if self.repeticiones is not None:
            if (not isinstance(self.repeticiones, Literal)
                    or self.repeticiones.tipo != Tipo.I32):
                errores.semantico(
                    'El tamano de [valor; n] tiene que ser un entero literal.',
                    self.linea, self.columna, 'n')
                gen.emitir('mov x0, #0', 'valor de recuperacion')
                return
            cantidad = int(self.repeticiones.valor)
            valores = [self.elementos[0]] * cantidad
        else:
            valores = self.elementos
            cantidad = len(valores)

        gen.comentario(f'arreglo de {cantidad} elemento(s)')
        base = gen.entorno.reservar(cantidad + 1)

        gen.emitir(f'mov w0, #{cantidad}')
        gen.acceso('str', 'x0', base, 'cabecera: longitud')

        for indice, elemento in enumerate(valores):
            elemento.generar(gen)
            gen.acceso('str', 'x0', base + (indice + 1) * TAMANO,
                       f'elemento {indice}')

        gen.emitir(f'sub x0, x29, #{-(base + TAMANO)}',
                   'dejar en x0 la direccion del elemento 0')


class Indice(Expresion):
    def __init__(self, arreglo, indice, linea=0, columna=0):
        super().__init__(linea, columna)
        self.arreglo = arreglo
        self.indice = indice

    def etiqueta(self):
        return 'Indice\n[ ]'

    def hijos(self):
        return [self.arreglo, self.indice]

    def generar(self, gen):
        gen.comentario('acceso a[i]')
        self.arreglo.generar(gen)
        gen.emitir('str x0, [sp, #-16]!', 'guardar el puntero del arreglo')
        self.indice.generar(gen)
        gen.emitir('ldr x1, [sp], #16', 'recuperar el puntero')
        gen.emitir('add x1, x1, w0, sxtw #3', 'puntero + indice * 8')
        gen.emitir('ldr x0, [x1]', 'leer el elemento')


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

    def generar(self, gen):
        self.receptor.generar(gen)
        tipo = self.receptor.tipo

        if self.argumentos and self.metodo in ('len', 'to_uppercase',
                                               'to_lowercase', 'reverse'):
            errores.semantico(
                f"'.{self.metodo}()' no lleva argumentos.",
                self.linea, self.columna, self.metodo)

        if self.metodo == 'len':
            self.tipo = Tipo.I32
            if tipo == Tipo.ARREGLO:
                gen.emitir('ldr x0, [x0, #-8]', 'longitud en la cabecera')
            else:
                gen.emitir('mov x1, x0')
                gen.emitir('bl strlen', 'deja la longitud en x2')
                gen.emitir('mov w0, w2')
            return

        if self.metodo in ('to_uppercase', 'to_lowercase'):
            self.tipo = Tipo.STRING
            rutina = 'to_upper' if self.metodo == 'to_uppercase' else 'to_lower'
            gen.emitir('mov x1, x0', 'la cadena va en x1')
            gen.emitir(f'bl {rutina}')
            return

        if self.metodo == 'reverse':
            self.tipo = Tipo.ARREGLO
            gen.emitir('mov x1, x0', 'el puntero va en x1')
            gen.emitir('bl array_reverse')
            return

        errores.semantico(
            f"El metodo '.{self.metodo}()' todavia no esta soportado.",
            self.linea, self.columna, self.metodo)
        gen.emitir('mov w0, #0', 'valor de recuperacion')


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
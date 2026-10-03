from .tipos import Tipo

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
        self.tipo = Tipo.I32
        self.izquierda = izquierda
        self.operador = operador
        self.derecha = derecha

    def etiqueta(self):
        return f'Binaria\n{self.operador}'

    def hijos(self):
        return [self.izquierda, self.derecha]

    def generar(self, gen):
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
        for instruccion in self.instrucciones:
            instruccion.generar(gen)

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
        if self.nombre == 'main':
            gen.comentario('=== funcion main (punto de entrada) ===')
            gen.etiqueta('_start')
            self.cuerpo.generar(gen)
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

if __name__ == '__main__':
    from .generador import Generador

    # fn main() {
    #     println!("El resultado es:");
    #     println!(2 + 3 * 4);
    # }
    programa = Programa([
        Funcion('main', [], None, Bloque([
            LlamadaMacro('println', [
                Literal("El resultado es:", Tipo.STRING)
            ]),
            LlamadaMacro('println', [
                Binaria(
                    Literal(2, Tipo.I32),
                    '+',
                    Binaria(Literal(3, Tipo.I32), '*', Literal(4, Tipo.I32))
                )
            ]),
        ]))
    ])

    gen = Generador()
    programa.generar(gen)
    print(gen.codigo())
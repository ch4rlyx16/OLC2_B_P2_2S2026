"""
OxigenNative — Entorno de compilación

"""


TAMANO = 8


class Variable:
    """Lo que el compilador necesita recordar de una variable."""

    def __init__(self, nombre, tipo, offset, mutable=False):
        self.nombre = nombre
        self.tipo = tipo
        self.offset = offset        
        self.mutable = mutable

    def direccion(self):
        return '[x29, #' + str(self.offset) + ']'

    def __repr__(self):
        return f'Variable({self.nombre}, {self.tipo}, {self.offset})'


class Entorno:
    """Lleva la cuenta de qué variable vive en qué offset.

    Se crea uno nuevo por cada función, porque cada función tiene
    su propio marco de pila y su propio x29.
    """

    def __init__(self, registro=None, ambito='global'):
        self.ambitos = [{}]
        self.desplazamiento = 0
        self.maximo = 0
        self.registro = registro if registro is not None else []
        self.ambito = ambito

    # ------------------------------------------------------------------
    # Bloques
    # ------------------------------------------------------------------

    def abrir(self):
        """Entra a un bloque: apila un ámbito vacío."""
        self.ambitos.append({})

    def cerrar(self):
        """Sale del bloque: bota el ámbito y recicla su espacio."""
        muertas = self.ambitos.pop()
        self.desplazamiento -= TAMANO * len(muertas)

    def reservar(self, cantidad):
        """Aparta `cantidad` casillas contiguas. Devuelve el offset de la primera."""
        self.desplazamiento += TAMANO * cantidad
        if self.desplazamiento > self.maximo:
            self.maximo = self.desplazamiento
        return -self.desplazamiento

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------

    def declarar(self, nombre, tipo, mutable=False, linea=0,
                 categoria='Variable'):
        """Le asigna un offset a `nombre` y devuelve la Variable."""
        self.desplazamiento += TAMANO
        if self.desplazamiento > self.maximo:
            self.maximo = self.desplazamiento

        variable = Variable(nombre, tipo, -self.desplazamiento, mutable)
        self.ambitos[-1][nombre] = variable

        if not nombre.startswith('$'):
            self.registro.append({
                'identificador': nombre,
                'categoria': categoria,
                'tipo': str(tipo) if tipo else '-',
                'ambito': self.ambito,
                'linea': linea,
                'direccion': variable.direccion(),
            })

        return variable

    def buscar(self, nombre):
        """Devuelve la Variable, o None si no está declarada."""
        for ambito in reversed(self.ambitos):
            if nombre in ambito:
                return ambito[nombre]
        return None

    def declarada_aqui(self, nombre):
        """True si ya existe en el ámbito actual """
        return nombre in self.ambitos[-1]

    # ------------------------------------------------------------------
    # Marco de pila
    # ------------------------------------------------------------------

    def espacio(self):
        """Bytes a reservar con `sub sp, sp, #N`, alineado a 16."""
        return ((self.maximo + 15) // 16) * 16


if __name__ == '__main__':
    e = Entorno()

    a = e.declarar('a', 'i32')
    print('a ->', a.offset, a.direccion(), '| desp:', e.desplazamiento,
          '| max:', e.maximo)

    e.abrir()
    b = e.declarar('b', 'i32')
    c = e.declarar('c', 'bool')
    print('c ->', c.offset, c.direccion(), '| desp:', e.desplazamiento,
          '| max:', e.maximo)

    sombra = e.declarar('a', 'String')      # shadowing
    print('busca a (adentro) ->', e.buscar('a').offset)

    e.cerrar()
    print('busca a (afuera)  ->', e.buscar('a').offset)
    print('busca b (afuera)  ->', e.buscar('b'))
    print('desp tras cerrar:', e.desplazamiento, '| max:', e.maximo)

    d = e.declarar('d', 'i32')
    print('d reusa el hueco ->', d.offset)

    print('espacio a reservar:', e.espacio())

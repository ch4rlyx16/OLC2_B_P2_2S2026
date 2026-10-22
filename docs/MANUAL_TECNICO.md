# Manual Técnico — OxigenNative

**Compilador de OxigenScript a ensamblador ARM64 (AArch64)**

Universidad de San Carlos de Guatemala — Facultad de Ingeniería
Organización de Lenguajes y Compiladores 2 — Segundo Semestre 2026
Proyecto 2, Sección B

---

## 1. Qué es esto

OxigenNative toma código fuente de un lenguaje inspirado en Rust y **genera
ensamblador ARM64**. No lo interpreta: produce un archivo `.s` que después se
ensambla, se enlaza y se ejecuta en QEMU.

Esa es la diferencia central con el Proyecto 1. Un intérprete recorre el árbol
y *hace* las cosas; un compilador recorre el árbol y *escribe instrucciones que
harán las cosas más tarde*. El compilador nunca ve un valor: solo decide dónde
van a vivir los valores cuando el programa corra.

```
fuente .oxs
    ↓  lexer.py 
tokens
    ↓  parser.py 
AST  
    ↓  generar()
ensamblador ARM64  
    ↓  aarch64-linux-gnu-as
programa.o  +  io.o  +  runtime.o
    ↓  aarch64-linux-gnu-ld
ejecutable
    ↓  qemu-aarch64
salida en consola
```

### Entorno verificado

| Herramienta | Versión |
|---|---|
| Python | 3.14.4 |
| PLY | 3.11 |
| Django | 5.2.5 |
| GNU Binutils (as, ld) | 2.46 |
| QEMU user mode | 10.2.1 |
| Graphviz | 14.1.2 |

Dependencias del sistema:

```bash
sudo apt install binutils-aarch64-linux-gnu qemu-user graphviz
```

---

## 2. Estructura del proyecto

```
OLC2_B_P2_2S2026/
├── compilador/
│   ├── lexer.py       394 líneas — análisis léxico (PLY lex)
│   ├── parser.py      594 líneas — análisis sintáctico 
│   ├── nodos.py      1143 líneas — AST + generación de código
│   ├── generador.py    99 líneas — acumula el texto del ensamblador
│   ├── entorno.py     130 líneas — nombres → direcciones de pila
│   ├── tipos.py        28 líneas — los tipos del lenguaje
│   ├── errores.py      71 líneas — lista única de errores
│   ├── reportes.py    179 líneas — AST en Graphviz, tabla de símbolos
│   └── pipeline.py    167 líneas — orquesta as → ld → qemu
├── io.s               239 líneas — rutinas del laboratorio 
├── runtime.s          123 líneas — rutinas propias
├── web/                         — GUI 
├── servidor/                    — configuración de Django
├── entradas/                    — programas de prueba
└── docs/
```

**`io.s` es del laboratorio y no se toca.** Todo lo nuestro en ensamblador vive
en `runtime.s`.

---

## 3. Análisis léxico — `lexer.py`

PLY construye el lexer a partir de los nombres de las variables y funciones del
módulo. **La docstring de una función `t_*` ES la expresión regular**, no un
comentario.

- **64 tokens**, de los cuales **21 son palabras reservadas**.
- Las reglas en forma de **string** (`t_MAS = r'\+'`) se ordenan solas de
  regex más larga a más corta, por eso `+=` gana sobre `+`.
- Las reglas en forma de **función** se prueban en **orden de definición**, por
  eso `t_DECIMAL` va antes que `t_ENTERO` y `t_CADENA` antes que
  `t_cadena_sin_cerrar`.

### Lo que no es trivial

| Regla | Por qué existe |
|---|---|
| `t_comentario_bloque` | Cuenta anidamiento de `/* /* */ */` a mano, porque una regex no puede balancear |
| `t_RAW_CADENA` | `r#"..."#` — busca el cierre con el mismo número de `#` |
| `t_ETIQUETA` vs `t_CARACTER` | `'outer` (etiqueta de loop) y `'a'` (char) empiezan igual; se desambigua por lo que sigue |
| `t_MACRO` | `println!` solo es macro si viene seguido de `(`, `[` o `{` — usa un *lookahead* `(?=[\(\[\{])` |
| `encontrar_columna` | PLY da la posición absoluta; la columna se calcula buscando el `\n` anterior |

Los errores léxicos **no detienen el análisis**: se reportan y se salta el
carácter, para poder mostrar varios errores de una pasada.

---

## 4. Análisis sintáctico — `parser.py`

**56 reglas de producción**, LALR, con tabla de precedencia explícita.

Igual que en el lexer, **la docstring de una función `p_*` ES la producción**.
Ojo: yacc exige **espacio antes de los dos puntos** (`'expresion : ...'`).

### Recuperación de errores

```python
instruccion : error PUNTO_COMA
```

Es *modo pánico*: ante un error de sintaxis, se descartan tokens hasta encontrar
un `;` y se sigue. Permite reportar varios errores en un archivo, pero deja el
AST con huecos — por eso **el generador no corre si hubo errores de sintaxis**.

### Tablas en caché

PLY guarda la tabla LALR en `parsetab.py`. **Si se modifica la gramática hay que
borrarla**, o el parser seguirá usando la versión vieja sin avisar:

```bash
rm -f parsetab*.py parser*.out
```

---

## 5. El AST — `nodos.py`

**37 clases**, **25 con `generar()` implementado**.

Tres clases base:

```python
class Nodo:          # línea, columna, generar(), etiqueta(), hijos()
class Expresion:     # deja su resultado en w0
class Instruccion:   # produce un efecto, no deja valor
```

`etiqueta()` y `hijos()` existen para los reportes: con esos dos métodos,
`reportes.py` dibuja el AST sin saber nada de cada nodo en particular.

### El contrato que sostiene todo

> **Toda expresión deja su resultado en `w0` / `x0`.**

Sin excepciones. Un `Literal` hace `mov w0, #5`. Una `Binaria` deja la suma en
`w0`. Una `Llamada` deja el valor de retorno en `w0`. Incluso los caminos de
error emiten `mov w0, #0` antes de salir, porque el nodo de arriba va a leer
`w0` sin preguntar.

### `Nodo.generar()` de la clase base

Las funciones del lenguaje sin implementar **no lanzan excepción**: reportan un
error semántico y siguen. Así la GUI nunca devuelve un error 500 y los reportes
(AST, tabla de símbolos) se generan igual.

---

## 6. Generación de código

### 6.1 El problema del registro único

Todas las expresiones dejan su resultado en `w0`. Entonces en `2 + 3 * 4`, al
evaluar el lado derecho se pisa el izquierdo.

**Solución: la pila.**

```asm
   ...lado izquierdo...
   str w0, [sp, #-16]!      // apilar el izquierdo
   ...lado derecho...
   ldr w1, [sp], #16        // desapilar el izquierdo en w1
   add w0, w1, w0
```

`[sp, #-16]!` es *pre-decremento con escritura*: baja `sp` y escribe. `[sp], #16`
es *post-incremento*: lee y sube `sp`. Se usan 16 bytes y no 8 porque ARM64
exige que `sp` quede siempre alineado a 16.

### 6.2 El marco de pila

```asm
mi_funcion:
    stp x29, x30, [sp, #-16]!   // guardar marco anterior y dirección de retorno
    mov x29, sp                 // x29 queda FIJO durante toda la función
    sub sp, sp, #N              // espacio para las variables (backpatch)
    str x0, [x29, #-8]          // guardar parámetro
    ...cuerpo...
Lret0:
    mov sp, x29                 // soltar todas las variables de un golpe
    ldp x29, x30, [sp], #16     // recuperar marco y dirección de retorno
    ret                         // volver a quien llamó
```

**Las variables se direccionan desde `x29`, no desde `sp`.** `sp` se mueve
constantemente con los push/pop de las expresiones; `x29` no se mueve nunca. Si
se usara `sp`, el offset de una variable cambiaría en medio de una expresión.

**`x30` es el *link register*.** La instrucción `bl` guarda ahí la dirección de
retorno, y `ret` salta a esa dirección. Como un `bl` anidado lo sobreescribe,
cada función lo guarda al entrar y lo recupera al salir — eso es lo que hace
posible la recursión.

`main` es un caso aparte: se emite como `_start`, no guarda `x30` (nadie la
llamó) y termina con el syscall `exit` (`x8 = 93`) en vez de `ret`.

### 6.3 Backpatching

El `sub sp, sp, #N` va **antes** del cuerpo, pero `N` solo se conoce **después**
de recorrerlo. Y no se puede recorrer dos veces porque los contadores del
entorno se duplicarían.

La solución es escribir en sucio y corregir:

```python
hueco = gen.marcador('espacio para variables')   # renglón vacío, guarda el índice
self.cuerpo.generar(gen)                          # ahora sí se sabe cuánto
gen.parchar(hueco, f'sub sp, sp, #{gen.entorno.espacio()}')
```

### 6.4 Desplazamientos grandes

ARM64 solo admite desplazamientos de **−256 a +255** en `ldr`/`str` con offset
negativo. Un arreglo hace crecer el marco más allá de eso enseguida, así que
todo acceso pasa por `Generador.acceso()`, que elige la forma:

```asm
str x0, [x29, #-24]        // offset chico

sub x9, x29, #400          // offset grande: calcular la dirección aparte
str x0, [x9]
```

### 6.5 Saltos y etiquetas

Todo el control de flujo son etiquetas únicas (`gen.nueva_etiqueta()`) y saltos.

**La condición del salto es siempre la negación de la condición del código
fuente**: el caso verdadero cae derecho al cuerpo, y el salto solo existe para
*esquivarlo*.

```asm
   cmp w0, #0
   b.eq Lelse1        // falso: irse al else
   ...entonces...
   b Lfin0            // verdadero ya terminó: esquivar el else
Lelse1:
   ...sino...
Lfin0:
```

El `b Lfin0` es imprescindible: el ensamblador no sabe dónde "termina" un
bloque, y sin un salto explícito el flujo cae en lo que sigue.

| Estructura | Etiquetas | Particularidad |
|---|---|---|
| `if` / `else` | 1 o 2 | el `else if` sale gratis: es un `Si` dentro de `self.sino` |
| `while` | 2 | la etiqueta de inicio va **arriba de la condición** |
| `loop` | 2 | `while` sin condición; solo sale con `break` |
| `for` | **3** | necesita una etiqueta extra para el incremento |
| `match` | 1 + 1 por brazo | cadena de `if`; el valor se guarda en una variable oculta |

### 6.6 `break` y `continue`

Un `break` enterrado en el árbol no sabe a qué etiqueta saltar: ese dato lo tiene
el bucle, varios niveles más arriba. Se resuelve con una **pila de bucles
abiertos** (`gen.bucles`): cada bucle se apila antes de generar su cuerpo y se
desapila después.

```python
gen.bucles.append({'nombre': etiqueta, 'inicio': inicio, 'fin': fin})
self.cuerpo.generar(gen)
gen.bucles.pop()
```

`break` salta a `fin`, `continue` salta a `inicio`. Con etiqueta (`break 'outer`)
se busca por nombre recorriendo la pila al revés, igual que los ámbitos.

**En el `for`, `continue` apunta al incremento, no a la comprobación.** Si
apuntara a la comprobación, el contador nunca avanzaría y sería un bucle
infinito.

---

## 7. Entorno de compilación — `entorno.py`

Donde el intérprete guardaba `nombre → valor`, el compilador guarda
`nombre → dirección`.

```python
class Variable:
    nombre, tipo, offset, mutable
    def direccion(self):  return '[x29, #-8]'
```

Se crea **un `Entorno` por función**, porque cada función tiene su propio `x29`.

### Ámbitos: una pila de diccionarios

```python
self.ambitos = [{}]     # uno por bloque anidado
```

- `abrir()` apila un diccionario; `cerrar()` lo bota.
- `buscar()` recorre **del último al primero**, así el shadowing funciona solo:
  la variable más interna se encuentra primero.
- `declarada_aqui()` mira solo el ámbito actual, para distinguir una
  redeclaración ilegal de un shadowing legal.

### Los dos contadores

| | Qué es | Para qué |
|---|---|---|
| `desplazamiento` | espacio en uso **ahora** | decidir el offset de la próxima variable |
| `maximo` | el pico histórico | el número del `sub sp, sp, #N` |

`cerrar()` **le resta a `desplazamiento`** el espacio del bloque que murió (se
recicla), pero **no toca `maximo`**. Por eso una función con veinte bloques
pequeños reserva solo lo del peor momento.

`espacio()` redondea `maximo` hacia arriba al múltiplo de 16:
`((maximo + 15) // 16) * 16`.

### Variables internas

Las que empiezan con `$` (`$fin_i` del `for`, `$match7`) son del compilador. El
lexer no permite `$` en identificadores, así que **es imposible que choquen con
un nombre del usuario**, y se filtran de la tabla de símbolos.

---

## 8. Arreglos

```
[x29 - 40]   longitud = 3
[x29 - 32]   elemento 0      ← la VARIABLE guarda esta dirección
[x29 - 24]   elemento 1
[x29 - 16]   elemento 2
```

Dos decisiones de diseño:

**La variable guarda un puntero, no el arreglo.** Por eso los arreglos se pueden
pasar a funciones (viaja un puntero en `w0`, como cualquier valor) y por eso
`[[1,2],[3,4]]` funciona sin código especial: cada subarreglo deja su puntero
en `x0` y ese puntero se guarda como elemento del arreglo de afuera.

**La longitud va en una cabecera, en `[puntero, #-8]`.** Así `len()` es una sola
instrucción y funciona **también cuando el arreglo llega como parámetro**, donde
el compilador ya no sabe de dónde vino.

El acceso usa direccionamiento con registro extendido:

```asm
add x1, x1, w0, sxtw #3    // puntero + índice*8, en una instrucción
ldr x0, [x1]
```

`sxtw` extiende el índice de 32 a 64 bits con signo; `#3` desplaza 3 bits a la
izquierda, que es multiplicar por 8 (el tamaño de cada casilla).

### El tipo de los elementos

`tipo` dice que algo es un arreglo, pero no **de qué**. Sin ese dato,
`println!(partes[0])` sobre el resultado de un `split` imprimiría la dirección
en vez del texto.

Por eso las expresiones llevan un segundo campo, `tipo_elemento`, que viaja en
paralelo: lo fija `Arreglo` (del primer elemento) o `split` (siempre `String`),
lo guarda la `Variable` al declararse, lo recupera `Identificador`, y finalmente
`Indice` lo usa como **su propio** `tipo`. `Prestamo` lo propaga en los dos
casos, el slice y el préstamo simple.

Es un análisis de tipos mínimo, de un solo nivel: en `[[1,2],[3,4]]` el elemento
es `arreglo` y ahí se corta, lo cual alcanza porque `m[0][1]` vuelve a ser `i32`.

### Slices

`&a[1..4]` **copia** el rango a un bloque nuevo con su propia cabecera de
longitud, para que `len()` devuelva 3 y no 5. Un slice de verdad sería un par
*(puntero, longitud)* sin copiar; copiar es más simple y el resultado observable
es el mismo.

`&a` a secas no genera nada: en este compilador los arreglos y las cadenas ya
**son** punteros, así que tomar una referencia deja la misma dirección. El `&`
de Rust es información para el verificador de préstamos, que aquí no existe.

`AsignacionIndice` es lo mismo al revés (`str` en vez de `ldr`), con **dos**
push/pop porque hay tres cosas en vuelo: puntero, índice y valor.

**Tamaño fijo en tiempo de compilación.** `[0; n]` exige que `n` sea un literal,
porque el bloque se reserva en la pila y el número va escrito en el `sub sp`.
Arreglos dinámicos necesitarían montón y `malloc`.

---

## 9. Biblioteca de ejecución

### `io.s` — del laboratorio, no se modifica

| Rutina | Contrato |
|---|---|
| `print_str` | x1 = dirección, x2 = bytes |
| `print_cstr` | x1 = cadena terminada en 0 |
| `print_nl` | salto de línea |
| `print_num` | w0 = número con signo |
| `strlen` | x1 = cadena → **x2** = longitud |
| `read_line` | x1 = buffer, x2 = tamaño → x0 = leídos |
| `atoi` | x1 = buffer → w0 = número |
| `itoa` | w0 = número → x1 = inicio, x2 = longitud |

Garantiza que **no modifica `x19`–`x28`**.

### `runtime.s` — propio

| Rutina | Contrato |
|---|---|
| `alloc` | x0 = bytes → x0 = dirección |
| `to_upper` | x1 = cadena → x0 = cadena nueva en mayúsculas |
| `to_lower` | x1 = cadena → x0 = cadena nueva en minúsculas |
| `array_reverse` | x1 = puntero → x0 = el mismo, invertido |
| `random` | w0 = min, w1 = max → w0 en [min, max] |
| `str_contains` | x1 = cadena, x2 = aguja → w0 = 1 / 0 |
| `array_contains` | x1 = puntero, w2 = valor → w0 = 1 / 0 |
| `str_replace` | x1 = cadena, x2 = viejo, x3 = nuevo → x0 = cadena nueva |
| `array_slice` | x1 = puntero, w2 = inicio, w3 = fin → x0 = arreglo nuevo |
| `str_split` | x1 = cadena, x2 = separador → x0 = arreglo de cadenas |
| `print_f64` | d0 = número → lo imprime con hasta 6 decimales |

`str_replace` hace **dos pasadas**: la primera cuenta ocurrencias para reservar
exactamente `len + n*(len_nuevo - len_viejo) + 1` bytes; la segunda copia
reemplazando. Si la aguja está vacía o no aparece, devuelve la cadena original.

`str_split` también hace dos pasadas: cuenta los separadores para saber cuántos
trozos reservar, y después corta y copia cada uno con su propio `alloc`. El
arreglo que devuelve usa **el mismo formato que los del lenguaje**, así que
`.len()` y `partes[0]` le funcionan sin código extra.

`random` usa un generador congruencial lineal sembrado con el reloj
(`clock_gettime`, syscall 113) la primera vez que se llama, para que la
secuencia cambie entre ejecuciones.

**`alloc` es un *bump allocator*:** 64 KB en `.bss` y un puntero al primer byte
libre que solo avanza. **Nunca libera.** Para programas que corren un segundo,
sobra; un `malloc` real necesitaría listas de bloques libres.

Las rutinas que llaman a otras guardan la cadena original en **`x19`**, que es
*callee-saved* y por lo tanto sobrevive a un `bl`. `x0`–`x18` son
*caller-saved*: cualquier llamada los puede destruir.

---

## 10. Convención de llamadas

Versión simplificada de AAPCS:

- Argumentos en **`w0`–`w7`** (máximo 8).
- Valor de retorno en **`w0`**.
- `x30` = dirección de retorno, `x29` = puntero de marco.
- `x19`–`x28` sobreviven a las llamadas; `x0`–`x18` no.

### Argumentos: el mismo problema del registro único

`suma(a + 1, b * 2)` — ambos argumentos se calculan en `w0`. Se resuelve
apilando todos y desapilándolos **al revés**:

```python
for argumento in self.argumentos:
    argumento.generar(gen)
    gen.emitir('str x0, [sp, #-16]!')

for indice in range(len(self.argumentos) - 1, -1, -1):
    gen.emitir(f'ldr x{indice}, [sp], #16')
```

La pila es LIFO: el último apilado sale primero, y ese es el **último**
argumento. Recorrer hacia adelante invertiría los argumentos — un bug silencioso
(`resta(10,3)` daría `-7`).

### Dos pasadas sobre el programa

```rust
fn main() { println!(doble(5)); }   // doble se define más abajo
fn doble(x: i32) -> i32 { ... }
```

`Programa.generar()` recorre las declaraciones **dos veces**: la primera solo
registra nombres y firmas en `gen.funciones` sin emitir nada; la segunda genera
el código. Así el orden en el archivo deja de importar (*hoisting*).

Las etiquetas llevan el prefijo **`fn_`** para que una función del usuario
llamada `strlen` no choque con la de `io.s`.

---

## 11. Pipeline — `pipeline.py`

```python
compilar(codigo, entrada='', ejecutar=True) -> dict
```

1. `analizar()` — léxico + sintáctico.
2. Si no hubo errores, `arbol.generar(generador)` → ensamblador.
3. Si sigue sin errores, ensamblar / enlazar / ejecutar.
4. Generar reportes (**siempre**, aunque haya errores: sirven para entenderlos).

### Robustez

| Riesgo | Protección |
|---|---|
| Toolchain ausente | `FileNotFoundError` → mensaje con el `apt install` |
| Bucle infinito del usuario | `timeout=5` en QEMU |
| `as` / `ld` lentos | `timeout=20` |
| Bug no previsto del compilador | `except Exception` → error semántico, nunca un 500 |
| Colisión de archivos | `TemporaryDirectory` con nombre único, se borra sola |

`subprocess.run` recibe una **lista**, no un string, para que el shell no
interprete nada (inyección de comandos).

**Dos límites distintos a propósito**: 5 s para el programa del usuario (que
puede colgarse), 20 s para las herramientas (que no).

### Contrato con el front

```python
{'salida', 'ensamblador', 'errores', 'simbolos', 'ast', 'ast_svg',
 'archivos', 'tiempo'}
```

Las llaves de lo no implementado se devuelven **vacías pero presentes**, para que
`editor.js` no se rompa.

---

## 12. Reportes — `reportes.py`

Se escriben en `reportes/` (ignorada por git) y se devuelven en el JSON.

| Reporte | Cómo |
|---|---|
| Errores | lista única en `errores.py`, ordenada por línea y columna |
| Tabla de símbolos | `simbolos.html` |
| AST | `ast.dot` → Graphviz → `ast.svg`, con respaldo en texto |

### La columna que cambió respecto al Proyecto 1

| Intérprete | Compilador |
|---|---|
| **Valor**: `15` | **Dirección**: `[x29, #-8]` |

El compilador no conoce valores. Lo único que decide es dónde vivirá cada cosa,
y eso es lo que muestra la tabla. Para funciones, la "dirección" es su etiqueta
(`fn_doble`, `_start`).

> La tabla de símbolos está escrita **dos veces**: en `reportes.py` para el
> archivo HTML y en `editor.js` para el panel de la GUI. Agregar una columna
> exige tocar los dos.

Si Graphviz no está instalado, `arbol_a_texto()` dibuja el árbol con caracteres
de caja y la GUI cae a ese respaldo sola.

---

## 13. Limitaciones conocidas

No implementado, reportado como error semántico claro (nunca una excepción):

| | Motivo |
|---|---|
| `structs` | requiere disposición de campos y tabla de tipos |
| `String::from` | — |

Además, por diseño:

- Máximo **8 parámetros** por función (los que caben en `w0`–`w7`).
- Arreglos de **tamaño fijo en tiempo de compilación**.
- `alloc` **no libera memoria**.
- **Sin verificación de límites** en el acceso a arreglos.



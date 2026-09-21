// ============================================================================
//  io.s --  Rutinas de entrada/salida para la calculadora
//nadie tiene que imprimir ni leer nada, por que se va a calificar que no hagamos trabajo de más, entonces solo llaman estas rutnas
//
//  uds llaman estas rutinas 
//
//    print_str    x1 = direccion,  x2 = cuantos bytes   -> imprime
//    print_cstr   x1 = direccion de cadena terminada en 0 -> imprime
//    print_nl                                            -> salto de linea
//    print_num    w0 = numero con signo                  -> lo imprime
//    read_line    x1 = buffer, x2 = tamaño   -> x0 = bytes leidos
//    atoi         x1 = buffer   -> w0 = numero, w1 = 0 ok / 1 error
//    itoa         w0 = numero   -> x1 = inicio del texto, x2 = longitud
//
//  Ninguna de estas rutinas modifica x19-x28.
// ============================================================================


.data

// Un solo byte con el salto de linea 
nl:         .byte 10


.bss

// Buffer de trabajo de itoa 24 bytes que hasta muy grande es
num_buf:    .skip 24


.text

.global print_str
.global print_cstr
.global print_nl
.global print_num
.global read_line
.global atoi
.global itoa
.global strlen


// ============================================================================
//  print_str(x1 = direccion, x2 = cantidad de bytes)
//  No llama a nadie y no necesitamos guardar el sp y fp
// ============================================================================
print_str:
    mov     x0, #1              // fd 1 = stdout (la pantalla)
    mov     x8, #64             // syscall 64 = write
    svc     #0                  // write(1, x1, x2)
    ret


// ============================================================================
//  strlen - x1 = cadena terminada en 0 ->  x2 = longitud
// ============================================================================
strlen:
    mov     x2, #0

strlen_loop:
    ldrb    w9, [x1, x2]        // byte en la direccion x1 + x2
    cbz     w9, strlen_fin      // si es 0, se acabo la cadena
    add     x2, x2, #1
    b       strlen_loop

strlen_fin:
    ret


// ============================================================================
//  print_cstr
//  SI llama a otras rutinas sí necesitan guardar el sp y fp
//  strlen deja el largo en x2 y no toca x1: encaja exacto con print_str
// ============================================================================
print_cstr:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp

    bl      strlen
    bl      print_str

    ldp     x29, x30, [sp], #16
    ret


// ============================================================================
//  print_nl()  -  imprime un salto de linea
// ============================================================================
print_nl:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp

    ldr     x1, =nl
    mov     x2, #1
    bl      print_str

    ldp     x29, x30, [sp], #16
    ret


// ============================================================================
//  read_line(x1 = buffer, x2 = tamaño)  ->  x0 = bytes leidos
//
// ============================================================================
read_line:
    mov     x0, #0              // fd 0 = stdin que es el teclado
    mov     x8, #63             // syscall 63 que es read
    svc     #0
    ret


// ============================================================================
//  atoi(x1 = buffer de texto)  ->  w0 = numero,  w1 = 0 ok / 1 error
//
//  read() entrega bytes ascii, no numeros. Si el usuario escribe 25, en
//  memoria hay 0x32 0x35 0x0A, o sea los caracteres '2','5','\n'.
//
//  la idea esque:  resultado = resultado * 10 + digito, una vez por caracter.
//    "254" -> 0*10+2 = 2 -> 2*10+5 = 25 -> 25*10+4 = 254
//  Y para pasar de caracter a valor:  digito = caracter - '0'
//    ('7' es el byte 55, '0' es el 48, y 55 - 48 = 7)
//
//  Devuelve error si no encontro ni un solo digito 
// ============================================================================
atoi:
    mov     w0, #0              // resultado acumulado
    mov     w10, #10            // el 10 en un registro 
    mov     w11, #0             // bandera de negativo
    mov     w12, #0             // cuantos digitos vimos

    // ---- empieza con menos? ----
    ldrb    w9, [x1]            // miramos el primer byte sin avanzar
    cmp     w9, #'-'
    b.ne    atoi_loop
    mov     w11, #1
    add     x1, x1, #1          // saltamos el -

atoi_loop:
    // Post-index cargamos el byte de [x1] y luego haceos x1 = x1 + 1
    ldrb    w9, [x1], #1

    // Cualquier cosa que no sea digito ('\n', letra, espacio) corta el numero.
    cmp     w9, #'0'
    b.lt    atoi_fin
    cmp     w9, #'9'
    b.gt    atoi_fin

    sub     w9, w9, #'0'        // caracter -> valor 0..9
    mul     w0, w0, w10         // correr el resultado un lugar decimal
    add     w0, w0, w9          // pegarle el digito nuevo

    add     w12, w12, #1
    b       atoi_loop

atoi_fin:
    cmp     w12, #0
    b.eq    atoi_error          // ni un digito -> entrada invalida

    cmp     w11, #0
    b.eq    atoi_ok
    neg     w0, w0              // aplicar el signo

atoi_ok:
    mov     w1, #0
    ret

atoi_error:
    mov     w0, #0
    mov     w1, #1
    ret


// ============================================================================
//  itoa(w0 = numero con signo)  ->  x1 = inicio del texto, x2 = longitud
//
//  Al reves que atoi. El problema: al dividir entre 10 repetidamente, los
//  digitos salen al reves entonces para 254 sale 452
//
//  Solucion escribir en el buffer de atras para adelante y terminar
//  y el puntero quedo justo sobre el primer digito
// ============================================================================
itoa:
    ldr     x1, =num_buf
    add     x1, x1, #24         // un byte despues del final - cada escritura
                                // hace x1- primero, asi que cae dentro
    mov     x2, #0              // longitud
    mov     w10, #10
    mov     w11, #0             // bandera de negativo

    // ---- caso especial: el cero ----
    // el ciclo de abajo no sigue sin este
    cmp     w0, #0
    b.ne    itoa_signo
    mov     w9, #'0'
    strb    w9, [x1, #-1]!      // pre-index: x1 = x1 - 1 y luego escribe
    add     x2, x2, #1
    b       itoa_fin

itoa_signo:
    cmp     w0, #0
    b.ge    itoa_loop
    mov     w11, #1
    neg     w0, w0              // trabajar con el valor absoluto

itoa_loop:
    sdiv    w3, w0, w10         // w3 = w0 / 10
    msub    w4, w3, w10, w0     // w4 = w0 - (w3 * 10) = ultimo digito
    add     w4, w4, #'0'        // valor -> caracter

    strb    w4, [x1, #-1]!      // escribir y retroceder
    add     x2, x2, #1

    mov     w0, w3              // seguir con el cociente
    cmp     w0, #0
    b.ne    itoa_loop

itoa_fin:
    cmp     w11, #0
    b.eq    itoa_ret
    mov     w9, #'-'            // el signo va de ultimo en el proceso,
    strb    w9, [x1, #-1]!      // que es la izquierda del resultado
    add     x2, x2, #1

itoa_ret:
    ret


// ============================================================================
//  print_num(w0 = numero con signo)  -  lo imprime en decimal
//  itoa deja x1 y x2 justo como print_str los quiere
// ============================================================================
print_num:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp

    bl      itoa
    bl      print_str

    ldp     x29, x30, [sp], #16
    ret
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from .models import DatosProducto
from .forms import ClienteForm, ServicioForm, TecnicoForm
from .models import DatosProducto, DatosProveedor, DatosGeneralesCliente, DatosTecnicosCliente, DatosServicio # <--- Importar los nuevos modelos
from django.contrib.auth.decorators import login_required
import json
import pyodbc
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ServidorBaseDatos # Importar modelo
from django.shortcuts import get_object_or_404 # Importante: agregarlo arriba
from datetime import datetime
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from .forms import PerfilUsuarioForm, AdminUsuarioForm
from django.core.paginator import Paginator
from django.db.models import Q

@login_required
def dashboard(request):
    return render(request, 'gestion/dashboard.html')

@login_required
def listar_clientes(request):
    # Traemos el cliente junto con su servicio, el producto del servicio y el estado
    lista_completa = DatosGeneralesCliente.objects.select_related(
        'servicio', 
        'servicio__producto', 
        'estado',
        'proveedor'
    ).all().order_by('-id') # Los más recientes primero
    
    # Obtener valores del GET (URL)
    filtro_nombre = request.GET.get('q', '')
    filtro_proveedor = request.GET.get('proveedor', '')
    filtro_estado = request.GET.get('estado', '')
    filtro_fecha_ini = request.GET.get('fecha_ini', '')
    filtro_fecha_fin = request.GET.get('fecha_fin', '')

    # 1. Filtro por Nombre o RUC
    if filtro_nombre:
        lista_completa = lista_completa.filter(
            Q(nombres_cliente__icontains=filtro_nombre) | 
            Q(ruc_cliente__icontains=filtro_nombre)
        )

    # 2. Filtro por Proveedor (relación servicio -> proveedor)
    if filtro_proveedor:
        lista_completa = lista_completa.filter(proveedor_id=filtro_proveedor)

    # 3. Filtro por Estado (relación servicio -> estado)
    if filtro_estado:
        lista_completa = lista_completa.filter(estado_id=filtro_estado)

    # 4. Filtro por Rango de Fechas (Vencimiento)
    if filtro_fecha_ini and filtro_fecha_fin:
        lista_completa = lista_completa.filter(
            servicio__fecha_vencimiento__range=[filtro_fecha_ini, filtro_fecha_fin]
        )

    # 2. Configurar el Paginador: 10 clientes por página
    paginator = Paginator(lista_completa, 8) 
    
    # 3. Obtener el número de página de la URL (ej: ?page=2)
    page_number = request.GET.get('page')
    
    # 4. Obtener solo los registros de esa página
    page_obj = paginator.get_page(page_number)
    
    # --- CONTEXTO EXTRA PARA LOS SELECTORES DEL HTML ---
    proveedores = DatosProveedor.objects.all()
    estados = DatosServicio.objects.all()

    # --- TRUCO PARA MANTENER FILTROS AL PAGINAR ---
    # Creamos un string con los filtros actuales para pegarlo en los botones "Siguiente"
    url_params = request.GET.copy()
    if 'page' in url_params:
        del url_params['page'] # Quitamos la página actual para no duplicar
    str_params = url_params.urlencode() # Genera "proveedor=1&estado=2..."

    context = {
        'clientes': page_obj,
        'proveedores': proveedores,
        'estados': estados,
        'params': str_params, # Variable clave para la paginación
    }
    
    return render(request, 'gestion/lista_clientes.html', context)

@login_required
def crear_cliente_completo(request):
    if request.method == 'POST':
        form_general = ClienteForm(request.POST)
        form_servicio = ServicioForm(request.POST)
        form_tecnico = TecnicoForm(request.POST)

        if form_general.is_valid() and form_servicio.is_valid() and form_tecnico.is_valid():
            try:
                with transaction.atomic():
                    # 1. Guardar Servicio
                    servicio = form_servicio.save()

                    # 2. Guardar Cliente
                    cliente = form_general.save(commit=False)
                    cliente.servicio = servicio
                    cliente.save()

                    # 3. Guardar Técnico
                    tecnico = form_tecnico.save(commit=False)
                    tecnico.cliente = cliente
                    tecnico.save()

                messages.success(request, 'Cliente creado exitosamente.')
                return redirect('lista_clientes') # Redirigiremos a la lista que crearemos hoy
            except Exception as e:
                messages.error(request, f"Error interno al guardar: {e}")
        else:
            # --- AQUÍ ESTÁ LA SOLUCIÓN DEL BUG ---
            # Si falla, mostramos qué campo específico tiene el error
            # Recorremos los 3 formularios buscando errores
            for form in [form_general, form_servicio, form_tecnico]:
                for field_name in form.errors:
                    # Si el error pertenece a un campo específico (y no es error general)
                    if field_name in form.fields:
                        # Recuperamos las clases CSS que ya tiene (ej: 'form-control uppercase-input')
                        clases_actuales = form.fields[field_name].widget.attrs.get('class', '')
                        # Le pegamos la clase 'is-invalid' de Bootstrap
                        form.fields[field_name].widget.attrs['class'] = clases_actuales + ' is-invalid'

                        
            messages.error(request, "Hay errores en el formulario. Revisa los campos en rojo.")
            
            # Esto imprimirá el error exacto en tu terminal negra (donde corre runserver)
            print("--- ERRORES DE VALIDACIÓN ---")
            print("General:", form_general.errors)
            print("Servicio:", form_servicio.errors)
            print("Técnico:", form_tecnico.errors)
            print("-----------------------------")
    
    else:
        form_general = ClienteForm()
        form_servicio = ServicioForm()
        form_tecnico = TecnicoForm()

    context = {
        'form_general': form_general,
        'form_servicio': form_servicio,
        'form_tecnico': form_tecnico
    }
    return render(request, 'gestion/cliente_form.html', context)

@login_required
def editar_cliente(request, id_cliente):
    # 1. Buscar el cliente general
    cliente = get_object_or_404(DatosGeneralesCliente, pk=id_cliente)
    
    # 2. Buscar sus partes relacionadas (Servicio y Técnico)
    # Nota: Como definimos relaciones OneToOne y ForeignKey, accedemos así:
    servicio = cliente.servicio
    
    # Para datos técnicos, usamos try/except por si acaso se creó un cliente sin datos técnicos (raro pero posible)
    try:
        tecnico = cliente.datos_tecnicos # related_name definido en el modelo o acceso inverso predeterminado
    except DatosTecnicosCliente.DoesNotExist:
        tecnico = None

    if request.method == 'POST':
        # Cargamos los formularios con los datos POST y las instancias existentes
        form_general = ClienteForm(request.POST, instance=cliente)
        form_servicio = ServicioForm(request.POST, instance=servicio)
        form_tecnico = TecnicoForm(request.POST, instance=tecnico)

        if form_general.is_valid() and form_servicio.is_valid() and form_tecnico.is_valid():
            try:
                with transaction.atomic():
                    form_servicio.save()
                    form_general.save()
                    
                    # Si no existía técnico y ahora lo llenaron, hay que vincularlo
                    tech = form_tecnico.save(commit=False)
                    tech.cliente = cliente
                    tech.save()

                messages.success(request, 'Datos del cliente actualizados correctamente.')
                return redirect('lista_clientes')
            except Exception as e:
                messages.error(request, f"Error al actualizar: {e}")
        else:
             messages.error(request, "Error en los datos. Revisa los campos en rojo.")
    
    else:
        # GET: Pre-llenar formularios con los datos actuales de la BD
        form_general = ClienteForm(instance=cliente)
        form_servicio = ServicioForm(instance=servicio)
        form_tecnico = TecnicoForm(instance=tecnico)

    context = {
        'form_general': form_general,
        'form_servicio': form_servicio,
        'form_tecnico': form_tecnico,
        'es_edicion': True # Flag para cambiar título en el template
    }
    return render(request, 'gestion/cliente_form.html', context)

# 1. LISTAR
@login_required
def listar_productos(request):
    productos = DatosProducto.objects.all().order_by('id') # O por nombre
    return render(request, 'gestion/lista_productos.html', {'productos': productos})

# 2. CREAR (Guardar nuevo)
@login_required
def guardar_producto(request):
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre_producto')
            plan_num = request.POST.get('plan_num')
            precio = request.POST.get('precio')
            vigencia = request.POST.get('vigencia')
            
            DatosProducto.objects.create(
                nombre_producto=nombre,
                plan_num=plan_num,
                precio=precio,
                vigencia=vigencia
            )
            messages.success(request, 'Producto creado correctamente.')
        except Exception as e:
            messages.error(request, f'Error al crear: {e}')
            
    return redirect('lista_productos')

# 3. EDITAR (Actualizar existente)
@login_required
def editar_producto(request):
    if request.method == 'POST':
        try:
            id_prod = request.POST.get('id_producto') # Este ID viene oculto en el modal
            producto = get_object_or_404(DatosProducto, pk=id_prod)
            
            producto.nombre_producto = request.POST.get('nombre_producto')
            producto.plan_num = request.POST.get('plan_num')
            producto.precio = request.POST.get('precio')
            producto.vigencia = request.POST.get('vigencia')
            producto.save()
            
            messages.success(request, 'Producto actualizado correctamente.')
        except Exception as e:
            messages.error(request, f'Error al editar: {e}')
            
    return redirect('lista_productos')

# 4. ELIMINAR
@login_required
def eliminar_producto(request, id):
    try:
        producto = get_object_or_404(DatosProducto, pk=id)
        producto.delete()
        messages.warning(request, 'Producto eliminado.')
    except Exception as e:
        messages.error(request, 'Error al eliminar.')
    return redirect('lista_productos')

# ==========================================
# GESTIÓN DE PROVEEDORES
# ==========================================
@login_required
def listar_proveedores(request):
    proveedores = DatosProveedor.objects.all().order_by('id')
    return render(request, 'gestion/lista_proveedores.html', {'proveedores': proveedores})

@login_required
def guardar_proveedor(request):
    if request.method == 'POST':
        try:
            DatosProveedor.objects.create(
                nombre=request.POST.get('nombre'),
                ruc=request.POST.get('ruc'),
                direccion=request.POST.get('direccion'),
                telefono=request.POST.get('telefono')
            )
            messages.success(request, 'Proveedor registrado correctamente.')
        except Exception as e:
            messages.error(request, f'Error al guardar: {e}')
    return redirect('lista_proveedores')

@login_required
def editar_proveedor(request):
    if request.method == 'POST':
        try:
            id_prov = request.POST.get('id_proveedor')
            prov = get_object_or_404(DatosProveedor, pk=id_prov)
            
            prov.nombre = request.POST.get('nombre')
            prov.ruc = request.POST.get('ruc')
            prov.direccion = request.POST.get('direccion')
            prov.telefono = request.POST.get('telefono')
            prov.save()
            
            messages.success(request, 'Proveedor actualizado.')
        except Exception as e:
            messages.error(request, f'Error al actualizar: {e}')
    return redirect('lista_proveedores')

@login_required
def eliminar_proveedor(request, id):
    try:
        prov = get_object_or_404(DatosProveedor, pk=id)
        prov.delete()
        messages.warning(request, 'Proveedor eliminado.')
    except Exception as e:
        messages.error(request, 'Error al eliminar.')
    return redirect('lista_proveedores')

# --- API INTERNA PARA CONSULTAR BASES EXTERNAS ---
@csrf_exempt # Usamos csrf_exempt para facilitar la llamada AJAX rápida en este prototipo
def consultar_facturas_externas(request):
    if request.method == 'POST':
        try:
            # 0. Decodificar JSON
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'status': 'error', 'mensaje': 'JSON inválido enviado por el navegador.'})
            
            # 1. Obtener datos del Request
            servidor_id = data.get('servidor')
            db_name = data.get('db_name')
            fecha_inicio_str = data.get('fecha_inicio')
            fecha_fin_str = data.get('fecha_fin')

            # Validación básica
            if not servidor_id or not db_name or not fecha_inicio_str:
                return JsonResponse({'status': 'error', 'mensaje': 'Faltan datos (Servidor, BD o Fechas).'})

            # --- 2. CONVERSIÓN DE FECHAS (DD/MM/YYYY) ---
            try:
                # Convertir de YYYY-MM-DD (Input HTML) a Objeto Fecha
                fecha_obj_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
                fecha_obj_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')

                # Convertir de Objeto Fecha a String DD/MM/YYYY (Formato SQL Server Exigido)
                fecha_sql_inicio = fecha_obj_inicio.strftime('%d/%m/%Y')
                fecha_sql_fin = fecha_obj_fin.strftime('%d/%m/%Y')
                
                print(f"DEBUG: Consultando fechas: {fecha_sql_inicio} y {fecha_sql_fin}")

            except ValueError:
                return JsonResponse({'status': 'error', 'mensaje': 'Formato de fecha inválido.'})

            # --- 3. BUSCAR CREDENCIALES DEL SERVIDOR ---
            try:
                servidor_obj = ServidorBaseDatos.objects.get(pk=servidor_id)
            except ServidorBaseDatos.DoesNotExist:
                return JsonResponse({'status': 'error', 'mensaje': 'Servidor no encontrado en catálogo.'})

            # --- 4. CONECTAR A LA BASE EXTERNA ---
            conn_str = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={servidor_obj.ip_host},{servidor_obj.puerto};'
                f'DATABASE={db_name};'
                f'UID={servidor_obj.usuario_sql};'
                f'PWD={servidor_obj.clave_sql};'
                'TrustServerCertificate=yes;'
                'Connection Timeout=5;'
            )

            print(f"DEBUG: Conectando a {servidor_obj.ip_host} -> {db_name}...")
            
            # --- MANEJO DE ERROR DE CONEXIÓN ESPECÍFICO ---
            try:
                conn = pyodbc.connect(conn_str)
            except Exception as e:
                print(f"ERROR CONEXIÓN: {e}")
                return JsonResponse({'status': 'error', 'mensaje': 'No se pudo conectar al SQL Server remoto. Revisa IP/Usuario.'})

            cursor = conn.cursor()
            
            # --- 5. EJECUTAR CONSULTA ---
            query = """
                SELECT COUNT(*) AS TotalDocumentos
                FROM FacElec_Documentos
                WHERE FechaEmision >= ? AND FechaEmision < ?
            """
            
            try:
                # Pasamos las fechas YA FORMATEADAS como strings "23/12/2024"
                cursor.execute(query, (fecha_sql_inicio, fecha_sql_fin))
                row = cursor.fetchone()
                cantidad = row[0] if row else 0
            except Exception as e:
                print(f"ERROR QUERY: {e}")
                return JsonResponse({'status': 'error', 'mensaje': f'Error al leer tabla FacElec_Documentos: {str(e)}'})
            
            conn.close()
            
            return JsonResponse({'status': 'ok', 'cantidad': cantidad})

        except Exception as e:
            # Captura cualquier otro error de Python (sintaxis, variables no definidas)
            print(f"ERROR CRÍTICO: {e}") 
            return JsonResponse({'status': 'error', 'mensaje': f'Error interno del servidor: {str(e)}'})
            
    return JsonResponse({'status': 'error', 'mensaje': 'Método no permitido'})

# --- VISTA 1: MI PERFIL (Para todos) ---
@login_required
def perfil_usuario(request):
    usuario = request.user
    
    if request.method == 'POST':
        form = PerfilUsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu información ha sido actualizada.')
            return redirect('perfil_usuario')
    else:
        form = PerfilUsuarioForm(instance=usuario)

    return render(request, 'gestion/perfil.html', {'form': form})

# --- VISTA 2: LISTA DE USUARIOS (Solo Superadmin) ---
@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='dashboard') # Candado de seguridad
def listar_usuarios(request):
    usuarios = User.objects.all().order_by('id')
    return render(request, 'gestion/lista_usuarios_admin.html', {'usuarios': usuarios})

# --- VISTA 3: CREAR/EDITAR USUARIO (Solo Superadmin) ---
@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='dashboard')
def guardar_usuario_admin(request, id_usuario=None):
    if id_usuario:
        # EDITAR
        usuario = get_object_or_404(User, pk=id_usuario)
        titulo = "Editar Usuario"
    else:
        # CREAR NUEVO
        usuario = None
        titulo = "Nuevo Usuario"

    if request.method == 'POST':
        form = AdminUsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            # Truco: Si es nuevo, el username será el email
            user_obj = form.save(commit=False)
            user_obj.username = user_obj.email 
            
            # Si es nuevo y no puso clave, poner una por defecto o obligar (aquí asumimos que puso)
            if not id_usuario and not form.cleaned_data.get('nueva_clave'):
                 messages.error(request, "Para un usuario nuevo, la contraseña es obligatoria.")
                 return render(request, 'gestion/form_usuario_admin.html', {'form': form, 'titulo': titulo})

            form.save() # Aquí se guarda y se setea el password si vino en el form
            messages.success(request, f'Usuario {user_obj.email} guardado correctamente.')
            return redirect('listar_usuarios')
    else:
        form = AdminUsuarioForm(instance=usuario)

    return render(request, 'gestion/form_usuario_admin.html', {'form': form, 'titulo': titulo})

# --- VISTA 4: ELIMINAR USUARIO ---
@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='dashboard')
def eliminar_usuario(request, id_usuario):
    if request.user.id == id_usuario:
        messages.error(request, "No puedes eliminarte a ti mismo.")
        return redirect('listar_usuarios')
        
    user = get_object_or_404(User, pk=id_usuario)
    user.delete()
    messages.warning(request, "Usuario eliminado permanentemente.")
    return redirect('listar_usuarios')
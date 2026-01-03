from django.db import models

# ==========================================
# 1. TABLAS DE CATÁLOGO (Configuración Global)
# ==========================================

class ServidorBaseDatos(models.Model):
    """
    NUEVA TABLA: Almacena las credenciales de los 3 servidores externos.
    RF22: Se usará para construir la cadena de conexión dinámica.
    """
    nombre_identificador = models.CharField(max_length=50, help_text="Ej: Servidor Principal, Servidor Secundario")
    ip_host = models.CharField(max_length=50, help_text="Dirección IP o DNS del servidor SQL")
    puerto = models.IntegerField(default=1433)
    usuario_sql = models.CharField(max_length=100, help_text="Usuario con permisos de lectura")
    # Nota: Se guarda en texto plano por requerimiento para el prototipo
    clave_sql = models.CharField(max_length=100, help_text="Contraseña de conexión a la BD externa")

    def __str__(self):
        return f"{self.nombre_identificador} ({self.ip_host})"

class EstadoCliente(models.Model):
    estado = models.CharField(max_length=50)

    def __str__(self):
        return self.estado

class DatosProducto(models.Model):
    nombre_producto = models.CharField(max_length=50)
    plan_num = models.IntegerField(help_text="Número de facturas permitidas al año")
    precio = models.DecimalField(max_digits=10, decimal_places=2) # MONEY en SQL
    vigencia = models.IntegerField(help_text="Vigencia en meses o días según lógica de negocio")

    def __str__(self):
        return f"{self.nombre_producto} - ${self.precio}"
    
# 1. NUEVA TABLA PARA LAS OPCIONES
class DatosRegimen(models.Model):
    nombre = models.CharField(max_length=50) # Aquí guardaremos "GENERAL" y "RIMPE"

    def __str__(self):
        return self.nombre

class DatosProveedor(models.Model):
    nombre = models.CharField(max_length=200)
    ruc = models.CharField(max_length=13, unique=True, verbose_name="RUC Proveedor")
    direccion = models.CharField(max_length=200)
    telefono = models.CharField(max_length=10)

    def __str__(self):
        return self.nombre

# ==========================================
# 2. TABLAS TRANSACCIONALES (Clientes y Servicios)
# ==========================================

class DatosServicio(models.Model):
    """
    Representa el contrato/servicio activo.
    Incluye el nuevo campo para el control de consumo.
    """
    # Relaciones
    producto = models.ForeignKey(DatosProducto, on_delete=models.PROTECT)
    proveedor = models.ForeignKey(DatosProveedor, on_delete=models.PROTECT, default=4)
    estado = models.ForeignKey(EstadoCliente, on_delete=models.PROTECT, default=2)

    # Fechas
    fecha_creacion = models.DateField(auto_now_add=True)
    fecha_renovacion = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)

    # NUEVO CAMPO SOLICITADO (RF23)
    # Se actualizará diariamente vía Job automático
    facturas_consumidas = models.IntegerField(default=0, help_text="Actualizado automáticamente desde BD externa")

    fecha_caducidad_firma = models.DateField(null=True, blank=True, verbose_name="Caducidad Firma")
    # 3. NUEVO: LOS 4 MÓDULOS DEL SISTEMA (Checkboxes)
    mod_ventas = models.BooleanField(default=False, verbose_name="Ventas (Facturación)")
    mod_compras = models.BooleanField(default=False, verbose_name="Compras (Liq/Ret)")
    mod_tesoreria = models.BooleanField(default=False, verbose_name="Tesoreria (C x P/C)")
    mod_inventario = models.BooleanField(default=False, verbose_name="Inventario (Kardex)")

    def __str__(self):
        return f"Servicio {self.id} - Plan: {self.producto.nombre_producto}"

class DatosGeneralesCliente(models.Model):
    # Relación 1 a 1: Un cliente tiene un servicio activo
    servicio = models.OneToOneField(DatosServicio, on_delete=models.CASCADE)
    
    nombres_cliente = models.CharField(max_length=200)
    ruc_cliente = models.CharField(max_length=13, unique=True, verbose_name="RUC Cliente") # RD02 Unicidad Fiscal
    telefono_cliente = models.CharField(max_length=10)
    correo_cliente = models.EmailField(max_length=100)
    activo = models.BooleanField(default=True, verbose_name="Cliente Activo")

    # Campos Alternativos
    contacto_alt = models.BooleanField(default=False)
    telefono_alt = models.CharField(max_length=10, null=True, blank=True)
    correo_alt = models.EmailField(max_length=100, null=True, blank=True)
    observacion_alt = models.TextField(null=True, blank=True) # VARCHAR(MAX)

    # NUEVO CAMPO VINCULADO (Sustituye al anterior si lo tenías como texto)
    regimen = models.ForeignKey(DatosRegimen, on_delete=models.SET_NULL, null=True, blank=True, default=2, verbose_name="Régimen Tributario")
    # Precio histórico (RD01 Inmutabilidad)
    precio_pactado = models.DecimalField(max_digits=10, decimal_places=2, help_text="Precio real vendido al cliente")
    motivo_precio = models.TextField(null=True, blank=True)
    
    envio_email = models.BooleanField(default=True)
    observaciones = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.nombres_cliente} ({self.ruc_cliente})"

class DatosTecnicosCliente(models.Model):
    """
    Información para conectar al sistema de este cliente específico.
    Se vincula a uno de los 3 servidores del catálogo.
    """
    cliente = models.OneToOneField(DatosGeneralesCliente, on_delete=models.CASCADE, related_name='datos_tecnicos')
    
    # CONEXIÓN BASE DE DATOS EXTERNA (RF22)
    # Seleccionamos en qué servidor físico (1, 2 o 3) está este cliente
    servidor_alojamiento = models.ForeignKey(ServidorBaseDatos, on_delete=models.PROTECT, help_text="Servidor físico donde está la BD")
    # Nombre específico de la BD de este cliente dentro de ese servidor
    nombre_basedatos = models.CharField(max_length=100, help_text="Nombre de la BD en SQL Server")

    # Datos del Portal Web (Gestión administrativa, NO conexión SQL)
    url_portal = models.URLField(max_length=200, blank=True, null=True)
    clave_portal = models.CharField(max_length=100, blank=True, null=True)
    num_portal = models.IntegerField(null=True, blank=True)
    
    # Otros datos técnicos
    version = models.IntegerField(null=True, blank=True)
    firma = models.CharField(max_length=100, null=True, blank=True)
    num_servicios = models.IntegerField(null=True, blank=True)
    
    # Email técnico (si difiere del cliente)
    email_tecnico = models.EmailField(max_length=100, null=True, blank=True)
    clave_email = models.CharField(max_length=100, null=True, blank=True)
    code_email = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"Datos Técnicos: {self.nombre_basedatos} en {self.servidor_alojamiento}"
    

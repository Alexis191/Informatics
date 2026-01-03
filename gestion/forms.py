from django import forms
from .models import DatosGeneralesCliente, DatosServicio, DatosTecnicosCliente
from django.contrib.auth.models import User

# Clase base para no repetir código de estilo (DRY)
class EstiloFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # VERIFICACIÓN: Si el campo es un Checkbox, usa 'form-check-input'
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            # Si es cualquier otro campo, usa 'form-control'
            else:
                field.widget.attrs.update({'class': 'form-control'})

class ServicioForm(EstiloFormMixin, forms.ModelForm):
    # Campo visual para la fecha de creación
    fecha_creacion_visual = forms.CharField(
        label="Fecha de Creación",
        required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'placeholder': 'Automático'})
    )

    class Meta:
        model = DatosServicio
        # 1. ASEGÚRATE QUE 'facturas_consumidas' ESTÉ EN ESTA LISTA
        fields = ['producto', 'proveedor', 'estado', 'mod_ventas', 'mod_compras', 'mod_tesoreria', 'mod_inventario', 'fecha_renovacion', 'fecha_vencimiento', 'fecha_caducidad_firma', 'facturas_consumidas']
        
        widgets = {
            'fecha_renovacion': forms.DateInput(attrs={'type': 'date'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date', 'readonly': 'readonly'}),
            'fecha_caducidad_firma': forms.DateInput(attrs={'type': 'date'}),
            
            # 2. AQUÍ FORZAMOS EL ID PARA QUE JAVASCRIPT LO ENCUENTRE SÍ O SÍ
            'facturas_consumidas': forms.NumberInput(attrs={
                'readonly': 'readonly', 
                'id': 'id_facturas_consumidas'  # <--- ESTO ES LA CLAVE
            }), 
        }

class ClienteForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = DatosGeneralesCliente
        exclude = ['servicio'] # Este campo se llena automáticamente en la vista
        widgets = {
            'observaciones': forms.Textarea(attrs={'rows': 3}),
            'envio_email': forms.CheckboxInput(), 
            'contacto_alt': forms.CheckboxInput(),
            'activo': forms.CheckboxInput(),
            # Agregamos una clase especial 'text-uppercase' para ayudar al CSS/JS
            'nombres_cliente': forms.TextInput(attrs={'class': 'text-uppercase'}),
            'direccion': forms.Textarea(attrs={'rows': 2, 'class': 'text-uppercase'}),
            'observacion_alt': forms.Textarea(attrs={'rows': 2, 'class': 'text-uppercase'}),
            'motivo_precio' : forms.Textarea(attrs={'rows': 2}),
        }
        # 1. VALIDACIÓN PERSONALIZADA DE RUC DUPLICADO
    def clean_ruc_cliente(self):
        ruc = self.cleaned_data.get('ruc_cliente')
        # Buscamos si existe otro cliente con este RUC
        # .exclude(pk=self.instance.pk) es vital para permitir EDICIONES del mismo cliente
        if DatosGeneralesCliente.objects.filter(ruc_cliente=ruc).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"⚠️ El RUC {ruc} ya está registrado en otro cliente.")
        return ruc

    # 2. CONVERTIR TEXTOS A MAYÚSCULAS AL GUARDAR
    def clean(self):
        cleaned_data = super().clean()
        
        # Lista de campos que queremos forzar a mayúsculas
        campos_mayusculas = ['nombres_cliente', 'direccion', 'observaciones', 'observacion_alt']
        
        for campo in campos_mayusculas:
            valor = cleaned_data.get(campo)
            if valor:
                cleaned_data[campo] = valor.upper()
        
        # Opcional: Forzar email a minúsculas
        email = cleaned_data.get('email')
        if email:
            cleaned_data['email'] = email.lower()
            
        return cleaned_data

class TecnicoForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = DatosTecnicosCliente
        exclude = ['cliente'] # Se llena automáticamente
        widgets = {

        }

# --- FORMULARIO 1: PERFIL PERSONAL (Para que el usuario se edite a sí mismo) ---
class PerfilUsuarioForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo Electrónico'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # REGLA DE ORO: El usuario normal NO puede cambiar su email
        # Lo ponemos como 'readonly' visualmente y deshabilitado
        if 'email' in self.fields:
            self.fields['email'].widget.attrs['readonly'] = True
            self.fields['email'].disabled = True 
            self.fields['email'].help_text = "Contacta al administrador para cambiar tu correo."

# --- FORMULARIO 2: GESTIÓN TOTAL (Solo para Superadmin) ---
class AdminUsuarioForm(EstiloFormMixin, forms.ModelForm):
    # Campo extra para contraseña (solo si se quiere cambiar)
    nueva_clave = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={'placeholder': 'Dejar vacío para mantener la actual'}),
        label="Nueva Contraseña"
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'is_active', 'is_superuser']
        labels = {
            'email': 'Correo (Usuario/Login)',
            'is_active': 'Usuario Activo (Puede entrar)',
            'is_superuser': 'Es Superadministrador'
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        # Si el superadmin escribió una nueva clave, la encriptamos y guardamos
        nueva_clave = self.cleaned_data.get('nueva_clave')
        if nueva_clave:
            user.set_password(nueva_clave)
        if commit:
            user.save()
        return user
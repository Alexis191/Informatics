0. Instalar visual studio code.
0. Instalar sql server
1. Primero descargar e instalar python en la computadora:
    Acceder a: https://www.python.org/downloads/
2. Crear una carpeta para el nuevo proyecto:
    Dentro de la carpeta abrir un terminal y ejecutar: code .
2.1. Intalar librerías necesarias: 
	pip install django mssql-django pyodbc apscheduler openpyxl
3. Dentro de VSC abrir un terminal y crear un entorno virtual:
    Ejecutar: python -m venv env
4. Activar el estorno virtual:
    Ejecutar: .\env\Scripts\activate
5. Ver que paquetes tenemos instalado por defecto: 
    Ejecutar: pip list
6. Instalar Django:
    Ejecutar: pip install Django
7. Instalar el conector de Django para sql server (django-mssql-backend)
    Ejecutar: pip install django-mssql-backend
8. Instalar el conector de Django para sql server (mssql-django pyodbc)
Ejecutar: pip install mssql-django pyodbc
9. Comprobar los paquetes que necesitamos: Django, django-mssql-backend, pyodbc
    Ejecutar: pip list
10. Crear un proyecto de Django:
    Ejecutar: django-admin startproject MENATICS .
11. Entrar dentro del proyecto desde el terminal
    Ejecutar: cd .\MENATICS\
12. Realizar la migracion a la base de datos para comprobar si esta bien configurada
    Ejecutar python manage.py migrate

PARA EJECUTAR EL PROGRAMA: python manage.py runserver
SUPERADMINISTRADOR
User: alexisntn@hotmail.com
Pass: 1q2w3eMenatics

USUARIO
User: admin@gmail.com
Pass: 123

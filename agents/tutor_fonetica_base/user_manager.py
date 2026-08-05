"""
Gestión de usuarios para asignaturas de Fonética.

Cada asignatura (agente concreto) tiene su propio archivo users.json.
Soporta:
  - Autenticación con contraseña (PBKDF2-HMAC-SHA256)
  - CRUD de usuarios (añadir, eliminar, modificar, listar)
  - Importación/exportación TSV
  - Roles: docente, estudiante
  - CLI para gestión offline

Uso como módulo:
    from tutor_fonetica_base.user_manager import UserManager
    um = UserManager(Path("agents/lali_tutor"))
    um.añadir_usuario("ana@uma.es", "P@ssw0rd1", nombre="Ana López", rol="estudiante")

Uso CLI:
    python user_manager.py /ruta/al/agente listar
    python user_manager.py /ruta/al/agente añadir ana@uma.es --nombre "Ana López"
    python user_manager.py /ruta/al/agente importar alumnos.tsv
    python user_manager.py /ruta/al/agente exportar alumnos.tsv
"""

import csv
import hashlib
import io
import json
import re
import secrets
from pathlib import Path
from typing import Optional


ROLES_VALIDOS = {"docente", "estudiante"}

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash con PBKDF2-HMAC-SHA256. Devuelve (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return h.hex(), salt


def _verify_password(password: str, hash_hex: str, salt: str) -> bool:
    h, _ = _hash_password(password, salt)
    return secrets.compare_digest(h, hash_hex)


def _validar_password(password: str) -> str | None:
    """Valida complejidad. Devuelve None si OK, o mensaje de error."""
    if len(password) < 8:
        return "La contraseña debe tener al menos 8 caracteres"
    if not re.search(r"[A-Z]", password):
        return "Debe contener al menos una mayúscula"
    if not re.search(r"[a-z]", password):
        return "Debe contener al menos una minúscula"
    if not re.search(r"[0-9]", password):
        return "Debe contener al menos un dígito"
    if not re.search(r"[^A-Za-z0-9]", password):
        return "Debe contener al menos un carácter especial (!@#$%...)"
    return None


def _generar_password(longitud: int = 12) -> str:
    """Genera una contraseña aleatoria que cumple los requisitos."""
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(longitud))
        if _validar_password(pwd) is None:
            return pwd


# ---------------------------------------------------------------------------
# UserManager
# ---------------------------------------------------------------------------

class UserManager:
    """Gestiona usuarios de una asignatura concreta."""

    def __init__(self, agent_dir: Path | str):
        """
        Args:
            agent_dir: directorio del agente concreto (ej: agents/lali_tutor/).
                       El archivo users.json se crea dentro de este directorio.
        """
        self._agent_dir = Path(agent_dir)
        self._users_file = self._agent_dir / "users.json"

    # -- Almacenamiento --

    def _load(self) -> dict:
        if not self._users_file.exists():
            return {}
        with open(self._users_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, users: dict) -> None:
        with open(self._users_file, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
            f.write("\n")

    # -- CRUD --

    def añadir_usuario(self, username: str, password: str, *,
                       nombre: str = "", apellidos: str = "",
                       rol: str = "estudiante",
                       grupo: str = "", email: str = "") -> bool:
        """Añade un usuario. Devuelve True si se creó, False si ya existe."""
        rol = rol.strip().lower()
        if rol not in ROLES_VALIDOS:
            raise ValueError(f"Rol inválido: {rol}. Debe ser: {', '.join(sorted(ROLES_VALIDOS))}")
        error = _validar_password(password)
        if error:
            raise ValueError(error)

        users = self._load()
        if username in users:
            return False

        hash_hex, salt = _hash_password(password)
        users[username] = {
            "nombre": nombre,
            "apellidos": apellidos,
            "rol": rol,
            "grupo": grupo,
            "email": email or username,
            "password_hash": hash_hex,
            "salt": salt,
            "activo": True,
        }
        self._save(users)
        return True

    def eliminar_usuario(self, username: str) -> bool:
        """Elimina un usuario. Devuelve True si se eliminó, False si no existe."""
        users = self._load()
        if username not in users:
            return False
        del users[username]
        self._save(users)
        return True

    def modificar_usuario(self, username: str, *,
                          nombre: str | None = None,
                          apellidos: str | None = None,
                          rol: str | None = None,
                          grupo: str | None = None,
                          email: str | None = None,
                          password: str | None = None,
                          activo: bool | None = None) -> bool:
        """Modifica campos de un usuario. Solo actualiza los que se pasan (no None).
        Devuelve True si se actualizó, False si el usuario no existe."""
        users = self._load()
        if username not in users:
            return False
        user = users[username]
        if nombre is not None:
            user["nombre"] = nombre
        if apellidos is not None:
            user["apellidos"] = apellidos
        if rol is not None:
            rol = rol.strip().lower()
            if rol not in ROLES_VALIDOS:
                raise ValueError(f"Rol inválido: {rol}")
            user["rol"] = rol
        if grupo is not None:
            user["grupo"] = grupo
        if email is not None:
            user["email"] = email
        if password is not None:
            error = _validar_password(password)
            if error:
                raise ValueError(error)
            hash_hex, salt = _hash_password(password)
            user["password_hash"] = hash_hex
            user["salt"] = salt
        if activo is not None:
            user["activo"] = activo
        self._save(users)
        return True

    def obtener_usuario(self, username: str) -> dict | None:
        """Devuelve datos del usuario (sin password_hash/salt), o None."""
        users = self._load()
        user = users.get(username)
        if not user:
            return None
        return {
            "username": username,
            "nombre": user.get("nombre", ""),
            "apellidos": user.get("apellidos", ""),
            "rol": user.get("rol", "estudiante"),
            "grupo": user.get("grupo", ""),
            "email": user.get("email", ""),
            "activo": user.get("activo", True),
        }

    def listar_usuarios(self, rol: str | None = None) -> list[dict]:
        """Lista todos los usuarios (sin datos sensibles).
        Opcionalmente filtra por rol."""
        users = self._load()
        resultado = []
        for username, data in users.items():
            if rol and data.get("rol") != rol:
                continue
            resultado.append({
                "username": username,
                "nombre": data.get("nombre", ""),
                "apellidos": data.get("apellidos", ""),
                "rol": data.get("rol", "estudiante"),
                "grupo": data.get("grupo", ""),
                "email": data.get("email", ""),
                "activo": data.get("activo", True),
            })
        return resultado

    def existe_usuario(self, username: str) -> bool:
        return username in self._load()

    # -- Autenticación --

    def autenticar(self, username: str, password: str) -> dict | None:
        """Autentica un usuario. Devuelve datos del usuario o None."""
        users = self._load()
        user = users.get(username)
        if not user:
            return None
        if not user.get("activo", True):
            return None
        if "password_hash" not in user:
            return None
        if not _verify_password(password, user["password_hash"], user["salt"]):
            return None
        return {
            "username": username,
            "nombre": user.get("nombre", ""),
            "apellidos": user.get("apellidos", ""),
            "rol": user.get("rol", "estudiante"),
            "grupo": user.get("grupo", ""),
            "email": user.get("email", ""),
        }

    def cambiar_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Cambia la contraseña verificando la anterior. Devuelve True si OK."""
        users = self._load()
        user = users.get(username)
        if not user or "password_hash" not in user:
            return False
        if not _verify_password(old_password, user["password_hash"], user["salt"]):
            return False
        error = _validar_password(new_password)
        if error:
            raise ValueError(error)
        hash_hex, salt = _hash_password(new_password)
        user["password_hash"] = hash_hex
        user["salt"] = salt
        self._save(users)
        return True

    def resetear_password(self, username: str) -> str | None:
        """Genera una nueva contraseña aleatoria. Devuelve la contraseña o None si no existe."""
        users = self._load()
        if username not in users:
            return None
        new_pwd = _generar_password()
        hash_hex, salt = _hash_password(new_pwd)
        users[username]["password_hash"] = hash_hex
        users[username]["salt"] = salt
        self._save(users)
        return new_pwd

    # -- Importación / Exportación TSV --

    _TSV_COLUMNS = ["username", "password", "nombre", "apellidos", "rol", "grupo", "email"]

    # Map common Spanish/Moodle column names to internal field names
    _COLUMN_ALIASES = {
        "correo electrónico": "username",
        "correo electronico": "username",
        "correo": "username",
        "email": "username",
        "nombre": "nombre",
        "apellido/s": "apellidos",
        "apellidos": "apellidos",
        "apellido": "apellidos",
        "rol": "rol",
        "role": "rol",
        "password": "password",
        "contraseña": "password",
        "grupo": "grupo",
        "username": "username",
    }

    def _normalize_columns(self, fieldnames: list[str]) -> dict[str, str]:
        """Map TSV column headers to internal field names (case-insensitive)."""
        mapping = {}
        for col in fieldnames:
            key = col.strip().lower()
            if key in self._COLUMN_ALIASES:
                mapping[col] = self._COLUMN_ALIASES[key]
        return mapping

    def importar_tsv(self, path: Path | str, *, sobreescribir: bool = False) -> dict:
        """Importa usuarios desde un archivo TSV.

        Columnas esperadas (con cabecera). Acepta dos formatos:

        Formato técnico:
            username  password  nombre  apellidos  rol  grupo  email

        Formato Moodle:
            Nombre  Apellido/s  Correo electrónico  Rol

        Las columnas son case-insensitive. El correo electrónico se usa como username.
        Si password está vacía o no existe, se genera una contraseña aleatoria.
        Si rol está vacío, se asigna 'estudiante'. El rol acepta mayúsculas/minúsculas.

        Args:
            path: ruta al archivo TSV
            sobreescribir: si True, actualiza usuarios existentes (excepto password
                           si ya tienen una). Si False, los salta.

        Returns:
            {"creados": int, "actualizados": int, "saltados": int,
             "errores": list[str], "passwords_generadas": dict[str, str]}
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        return self._importar_tsv_content(content, sobreescribir=sobreescribir)

    def _importar_tsv_content(self, content: str, *, sobreescribir: bool = False) -> dict:
        """Importa desde contenido TSV (string)."""
        result = {"creados": 0, "actualizados": 0, "saltados": 0,
                  "errores": [], "passwords_generadas": {}}

        reader = csv.DictReader(io.StringIO(content), delimiter="\t")

        # Validate header and build column mapping
        if not reader.fieldnames:
            result["errores"].append("El archivo TSV está vacío o no tiene cabecera.")
            return result

        col_map = self._normalize_columns(reader.fieldnames)
        # Build reverse lookup: internal_name -> original_column
        reverse = {}
        for orig, internal in col_map.items():
            reverse.setdefault(internal, orig)

        if "username" not in reverse:
            result["errores"].append(
                "No se encontró columna de usuario. Se acepta: "
                "'username', 'Correo electrónico', 'correo', 'email'. "
                f"Columnas encontradas: {', '.join(reader.fieldnames)}"
            )
            return result

        def get_field(row, field_name, default=""):
            col = reverse.get(field_name)
            if col is None:
                return default
            return (row.get(col) or default).strip()

        for line_num, row in enumerate(reader, start=2):
            username = get_field(row, "username").lower()
            if not username:
                result["errores"].append(f"Línea {line_num}: correo/username vacío")
                continue

            password = get_field(row, "password")
            nombre = get_field(row, "nombre")
            apellidos = get_field(row, "apellidos")
            rol = get_field(row, "rol", "estudiante").strip().lower()
            grupo = get_field(row, "grupo")

            if rol not in ROLES_VALIDOS:
                result["errores"].append(
                    f"Línea {line_num} ({username}): rol inválido '{rol}'"
                )
                continue

            if self.existe_usuario(username):
                if sobreescribir:
                    try:
                        self.modificar_usuario(username, nombre=nombre,
                                               apellidos=apellidos, rol=rol,
                                               grupo=grupo)
                        result["actualizados"] += 1
                    except ValueError as e:
                        result["errores"].append(f"Línea {line_num} ({username}): {e}")
                else:
                    result["saltados"] += 1
                continue

            # Generate password if missing
            if not password:
                password = _generar_password()
                result["passwords_generadas"][username] = password
            else:
                error = _validar_password(password)
                if error:
                    result["errores"].append(
                        f"Línea {line_num} ({username}): {error}"
                    )
                    continue

            try:
                self.añadir_usuario(username, password, nombre=nombre,
                                    apellidos=apellidos, rol=rol, grupo=grupo)
                result["creados"] += 1
            except ValueError as e:
                result["errores"].append(f"Línea {line_num} ({username}): {e}")

        return result

    def exportar_tsv(self, path: Path | str, *, incluir_passwords: bool = False) -> int:
        """Exporta usuarios a un archivo TSV.

        Args:
            path: ruta del archivo de salida
            incluir_passwords: si True, incluye una columna 'password' vacía
                               (las contraseñas hasheadas no se exportan nunca)

        Returns:
            número de usuarios exportados
        """
        usuarios = self.listar_usuarios()
        path = Path(path)

        columns = ["username", "nombre", "apellidos", "rol", "grupo", "email"]
        if incluir_passwords:
            columns.insert(1, "password")

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t",
                                    extrasaction="ignore")
            writer.writeheader()
            for u in usuarios:
                row = dict(u)
                if incluir_passwords:
                    row["password"] = ""
                writer.writerow(row)

        return len(usuarios)

    # -- Estadísticas --

    def estadisticas(self) -> dict:
        """Devuelve estadísticas básicas de usuarios."""
        users = self._load()
        total = len(users)
        por_rol = {}
        por_grupo = {}
        activos = 0
        for data in users.values():
            rol = data.get("rol", "estudiante")
            por_rol[rol] = por_rol.get(rol, 0) + 1
            grupo = data.get("grupo", "")
            if grupo:
                por_grupo[grupo] = por_grupo.get(grupo, 0) + 1
            if data.get("activo", True):
                activos += 1
        return {
            "total": total,
            "activos": activos,
            "por_rol": por_rol,
            "por_grupo": por_grupo,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    import argparse
    import sys
    import getpass

    parser = argparse.ArgumentParser(
        description="Gestión de usuarios para asignaturas de Fonética",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python user_manager.py ../lali_tutor listar
  python user_manager.py ../lali_tutor añadir ana@uma.es --nombre "Ana López"
  python user_manager.py ../lali_tutor importar alumnos.tsv
  python user_manager.py ../lali_tutor exportar alumnos_export.tsv
  python user_manager.py ../lali_tutor eliminar ana@uma.es
  python user_manager.py ../lali_tutor modificar ana@uma.es --grupo B
  python user_manager.py ../lali_tutor resetear-password ana@uma.es
  python user_manager.py ../lali_tutor estadisticas
        """,
    )
    parser.add_argument("agent_dir", help="Directorio del agente (ej: ../lali_tutor)")

    sub = parser.add_subparsers(dest="comando", required=True)

    # -- listar --
    p_listar = sub.add_parser("listar", help="Listar usuarios")
    p_listar.add_argument("--rol", choices=sorted(ROLES_VALIDOS), help="Filtrar por rol")

    # -- añadir --
    p_add = sub.add_parser("añadir", help="Añadir un usuario")
    p_add.add_argument("username", help="Nombre de usuario (ej: email)")
    p_add.add_argument("--nombre", default="", help="Nombre")
    p_add.add_argument("--apellidos", default="", help="Apellidos")
    p_add.add_argument("--rol", default="estudiante", choices=sorted(ROLES_VALIDOS))
    p_add.add_argument("--grupo", default="", help="Grupo (ej: A, B)")
    p_add.add_argument("--email", default="", help="Email (si distinto del username)")

    # -- eliminar --
    p_del = sub.add_parser("eliminar", help="Eliminar un usuario")
    p_del.add_argument("username")

    # -- modificar --
    p_mod = sub.add_parser("modificar", help="Modificar un usuario")
    p_mod.add_argument("username")
    p_mod.add_argument("--nombre", default=None)
    p_mod.add_argument("--apellidos", default=None)
    p_mod.add_argument("--rol", default=None, choices=sorted(ROLES_VALIDOS))
    p_mod.add_argument("--grupo", default=None)
    p_mod.add_argument("--email", default=None)
    p_mod.add_argument("--activo", default=None, type=lambda x: x.lower() in ("true", "1", "si", "sí"))

    # -- resetear-password --
    p_reset = sub.add_parser("resetear-password", help="Generar nueva contraseña aleatoria")
    p_reset.add_argument("username")

    # -- importar --
    p_imp = sub.add_parser("importar", help="Importar usuarios desde TSV")
    p_imp.add_argument("archivo", help="Ruta al archivo TSV")
    p_imp.add_argument("--sobreescribir", action="store_true",
                       help="Actualizar usuarios existentes")

    # -- exportar --
    p_exp = sub.add_parser("exportar", help="Exportar usuarios a TSV")
    p_exp.add_argument("archivo", help="Ruta del archivo de salida")

    # -- estadisticas --
    sub.add_parser("estadisticas", help="Mostrar estadísticas de usuarios")

    args = parser.parse_args()
    um = UserManager(args.agent_dir)

    if args.comando == "listar":
        usuarios = um.listar_usuarios(rol=args.rol)
        if not usuarios:
            print("No hay usuarios registrados.")
            return
        # Table header
        print(f"{'Username':<30} {'Nombre':<15} {'Apellidos':<20} {'Rol':<12} {'Grupo':<8} {'Activo'}")
        print("-" * 95)
        for u in usuarios:
            activo = "Sí" if u["activo"] else "No"
            print(f"{u['username']:<30} {u['nombre']:<15} {u.get('apellidos',''):<20} {u['rol']:<12} {u['grupo']:<8} {activo}")
        print(f"\nTotal: {len(usuarios)}")

    elif args.comando == "añadir":
        password = getpass.getpass(f"Contraseña para {args.username}: ")
        if not password:
            password = _generar_password()
            print(f"Contraseña generada: {password}")
        try:
            ok = um.añadir_usuario(args.username, password, nombre=args.nombre,
                                   apellidos=args.apellidos, rol=args.rol,
                                   grupo=args.grupo, email=args.email)
            if ok:
                print(f"Usuario '{args.username}' creado.")
            else:
                print(f"Error: el usuario '{args.username}' ya existe.", file=sys.stderr)
                sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.comando == "eliminar":
        if um.eliminar_usuario(args.username):
            print(f"Usuario '{args.username}' eliminado.")
        else:
            print(f"Error: usuario '{args.username}' no encontrado.", file=sys.stderr)
            sys.exit(1)

    elif args.comando == "modificar":
        kwargs = {}
        if args.nombre is not None:
            kwargs["nombre"] = args.nombre
        if args.apellidos is not None:
            kwargs["apellidos"] = args.apellidos
        if args.rol is not None:
            kwargs["rol"] = args.rol
        if args.grupo is not None:
            kwargs["grupo"] = args.grupo
        if args.email is not None:
            kwargs["email"] = args.email
        if args.activo is not None:
            kwargs["activo"] = args.activo
        if not kwargs:
            print("No se especificó ningún campo para modificar.", file=sys.stderr)
            sys.exit(1)
        try:
            if um.modificar_usuario(args.username, **kwargs):
                print(f"Usuario '{args.username}' actualizado.")
            else:
                print(f"Error: usuario '{args.username}' no encontrado.", file=sys.stderr)
                sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.comando == "resetear-password":
        new_pwd = um.resetear_password(args.username)
        if new_pwd:
            print(f"Nueva contraseña para '{args.username}': {new_pwd}")
        else:
            print(f"Error: usuario '{args.username}' no encontrado.", file=sys.stderr)
            sys.exit(1)

    elif args.comando == "importar":
        result = um.importar_tsv(args.archivo, sobreescribir=args.sobreescribir)
        print(f"Creados: {result['creados']}")
        if result["actualizados"]:
            print(f"Actualizados: {result['actualizados']}")
        if result["saltados"]:
            print(f"Saltados (ya existían): {result['saltados']}")
        if result["passwords_generadas"]:
            print(f"\nContraseñas generadas automáticamente:")
            for user, pwd in result["passwords_generadas"].items():
                print(f"  {user}: {pwd}")
        if result["errores"]:
            print(f"\nErrores:", file=sys.stderr)
            for err in result["errores"]:
                print(f"  {err}", file=sys.stderr)

    elif args.comando == "exportar":
        n = um.exportar_tsv(args.archivo)
        print(f"{n} usuarios exportados a '{args.archivo}'.")

    elif args.comando == "estadisticas":
        stats = um.estadisticas()
        print(f"Total usuarios: {stats['total']}")
        print(f"Activos: {stats['activos']}")
        if stats["por_rol"]:
            print("Por rol:")
            for rol, n in sorted(stats["por_rol"].items()):
                print(f"  {rol}: {n}")
        if stats["por_grupo"]:
            print("Por grupo:")
            for grupo, n in sorted(stats["por_grupo"].items()):
                print(f"  {grupo}: {n}")


if __name__ == "__main__":
    _cli()

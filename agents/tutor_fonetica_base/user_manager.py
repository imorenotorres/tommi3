"""
Gestión de usuarios para asignaturas de Fonética (versión Moodle SSO).

Almacena los datos en un archivo TSV plano (users.tsv) que el docente puede
editar directamente con cualquier hoja de cálculo.

NO gestiona contraseñas — la autenticación se hace exclusivamente vía Moodle SSO.

Columnas del TSV:
    email  nombre  apellidos  rol  grado  grupo

Valores de rol: docente, estudiante
Valores de grado: Logopedia, Doble Psicología-Logopedia (u otros)

Uso como módulo:
    from tutor_fonetica_base.user_manager import UserManager
    um = UserManager(Path("agents/eulalia"))
    um.obtener_usuario("ana@uma.es")  # → dict o None
    um.listar_usuarios(rol="estudiante")

Uso CLI:
    python user_manager.py ../eulalia listar
    python user_manager.py ../eulalia listar --rol estudiante
    python user_manager.py ../eulalia listar --grado Logopedia
    python user_manager.py ../eulalia añadir ana@uma.es --nombre Ana --apellidos "García López" --grado Logopedia
    python user_manager.py ../eulalia eliminar ana@uma.es
    python user_manager.py ../eulalia estadisticas
"""

import csv
import io
from pathlib import Path
from typing import Optional


ROLES_VALIDOS = {"docente", "estudiante"}

GRADOS_CONOCIDOS = {
    "Logopedia",
    "Doble Psicología-Logopedia",
}

TSV_COLUMNS = ["email", "nombre", "apellidos", "rol", "grado", "grupo"]

# Map common column names (case-insensitive) to internal field names
_COLUMN_ALIASES = {
    "correo electrónico": "email",
    "correo electronico": "email",
    "correo": "email",
    "email": "email",
    "username": "email",
    "nombre": "nombre",
    "apellido/s": "apellidos",
    "apellidos": "apellidos",
    "apellido": "apellidos",
    "rol": "rol",
    "role": "rol",
    "grado": "grado",
    "titulación": "grado",
    "titulacion": "grado",
    "degree": "grado",
    "grupo": "grupo",
    "group": "grupo",
}


class UserManager:
    """Gestiona usuarios de una asignatura concreta (archivo TSV plano)."""

    def __init__(self, agent_dir: Path | str):
        self._agent_dir = Path(agent_dir)
        self._tsv_file = self._agent_dir / "users.tsv"
        # Backwards compat: if users.json exists but not users.tsv, migrate
        self._json_file = self._agent_dir / "users.json"
        if self._json_file.exists() and not self._tsv_file.exists():
            self._migrate_from_json()

    # ── Storage ──

    def _load(self) -> list[dict]:
        """Load all users from TSV. Returns list of dicts."""
        if not self._tsv_file.exists():
            return []
        with open(self._tsv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            if not reader.fieldnames:
                return []
            col_map = self._normalize_columns(reader.fieldnames)
            users = []
            for row in reader:
                user = {}
                for orig_col, value in row.items():
                    internal = col_map.get(orig_col)
                    if internal:
                        user[internal] = (value or "").strip()
                # Ensure all fields exist
                for col in TSV_COLUMNS:
                    user.setdefault(col, "")
                # Normalize
                user["email"] = user["email"].lower().strip()
                user["rol"] = user["rol"].strip().lower() or "estudiante"
                if user["email"]:
                    users.append(user)
            return users

    def _save(self, users: list[dict]) -> None:
        """Save all users to TSV."""
        with open(self._tsv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t",
                                    extrasaction="ignore")
            writer.writeheader()
            for u in users:
                writer.writerow(u)

    def _normalize_columns(self, fieldnames: list[str]) -> dict[str, str]:
        """Map TSV column headers to internal field names (case-insensitive)."""
        mapping = {}
        for col in fieldnames:
            key = col.strip().lower()
            if key in _COLUMN_ALIASES:
                mapping[col] = _COLUMN_ALIASES[key]
        return mapping

    def _migrate_from_json(self):
        """One-time migration from users.json to users.tsv."""
        import json
        try:
            with open(self._json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            users = []
            for username, info in data.items():
                users.append({
                    "email": username,
                    "nombre": info.get("nombre", ""),
                    "apellidos": info.get("apellidos", ""),
                    "rol": info.get("rol", "estudiante"),
                    "grado": info.get("grado", ""),
                    "grupo": info.get("grupo", ""),
                })
            self._save(users)
        except Exception:
            pass

    # ── CRUD ──

    def añadir_usuario(self, email: str, *, nombre: str = "", apellidos: str = "",
                       rol: str = "estudiante", grado: str = "", grupo: str = "") -> bool:
        """Añade un usuario. Devuelve True si se creó, False si ya existe."""
        email = email.lower().strip()
        rol = rol.strip().lower()
        if rol not in ROLES_VALIDOS:
            raise ValueError(f"Rol inválido: {rol}. Debe ser: {', '.join(sorted(ROLES_VALIDOS))}")
        users = self._load()
        if any(u["email"] == email for u in users):
            return False
        users.append({
            "email": email,
            "nombre": nombre,
            "apellidos": apellidos,
            "rol": rol,
            "grado": grado,
            "grupo": grupo,
        })
        self._save(users)
        return True

    def eliminar_usuario(self, email: str) -> bool:
        """Elimina un usuario. Devuelve True si se eliminó."""
        email = email.lower().strip()
        users = self._load()
        before = len(users)
        users = [u for u in users if u["email"] != email]
        if len(users) == before:
            return False
        self._save(users)
        return True

    def modificar_usuario(self, email: str, **kwargs) -> bool:
        """Modifica campos de un usuario. Solo actualiza los que se pasan.
        Campos válidos: nombre, apellidos, rol, grado, grupo.
        Devuelve True si se actualizó, False si no existe."""
        email = email.lower().strip()
        users = self._load()
        found = False
        for u in users:
            if u["email"] == email:
                for key, val in kwargs.items():
                    if key in TSV_COLUMNS and val is not None:
                        if key == "rol":
                            val = val.strip().lower()
                            if val not in ROLES_VALIDOS:
                                raise ValueError(f"Rol inválido: {val}")
                        u[key] = val
                found = True
                break
        if not found:
            return False
        self._save(users)
        return True

    def obtener_usuario(self, email: str) -> dict | None:
        """Devuelve datos del usuario, o None."""
        email = email.lower().strip()
        users = self._load()
        for u in users:
            if u["email"] == email:
                return dict(u, username=email)  # backwards compat: include 'username'
        return None

    def listar_usuarios(self, rol: str | None = None, grado: str | None = None) -> list[dict]:
        """Lista usuarios. Opcionalmente filtra por rol y/o grado."""
        users = self._load()
        if rol:
            rol = rol.strip().lower()
            users = [u for u in users if u["rol"] == rol]
        if grado:
            users = [u for u in users if u["grado"].lower() == grado.lower()]
        return users

    def existe_usuario(self, email: str) -> bool:
        return self.obtener_usuario(email) is not None

    # ── Auth (Moodle SSO — no passwords) ──

    def autenticar(self, username: str, password: str) -> dict | None:
        """Compatibilidad con login form. Solo verifica que el usuario existe."""
        user = self.obtener_usuario(username)
        if not user:
            return None
        return user

    # ── Import / Export ──

    def importar_tsv(self, path: Path | str, *, sobreescribir: bool = False) -> dict:
        """Importa usuarios desde un archivo TSV externo.

        Acepta columnas con nombres flexibles (case-insensitive):
            email/correo electrónico, nombre, apellido/s, rol, grado/titulación, grupo

        Returns:
            {"creados": int, "actualizados": int, "saltados": int, "errores": list[str]}
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return self._importar_tsv_content(content, sobreescribir=sobreescribir)

    def _importar_tsv_content(self, content: str, *, sobreescribir: bool = False) -> dict:
        """Importa desde contenido TSV (string)."""
        result = {"creados": 0, "actualizados": 0, "saltados": 0, "errores": []}

        reader = csv.DictReader(io.StringIO(content), delimiter="\t")
        if not reader.fieldnames:
            result["errores"].append("El archivo TSV está vacío o no tiene cabecera.")
            return result

        col_map = self._normalize_columns(reader.fieldnames)
        reverse = {}
        for orig, internal in col_map.items():
            reverse.setdefault(internal, orig)

        if "email" not in reverse:
            result["errores"].append(
                "No se encontró columna de email. Se acepta: "
                "'email', 'Correo electrónico', 'correo', 'username'. "
                f"Columnas encontradas: {', '.join(reader.fieldnames)}"
            )
            return result

        def get_field(row, field_name, default=""):
            col = reverse.get(field_name)
            if col is None:
                return default
            return (row.get(col) or default).strip()

        for line_num, row in enumerate(reader, start=2):
            email = get_field(row, "email").lower()
            if not email:
                result["errores"].append(f"Línea {line_num}: email vacío")
                continue

            nombre = get_field(row, "nombre")
            apellidos = get_field(row, "apellidos")
            rol = get_field(row, "rol", "estudiante").strip().lower()
            grado = get_field(row, "grado")
            grupo = get_field(row, "grupo")

            if rol not in ROLES_VALIDOS:
                result["errores"].append(f"Línea {line_num} ({email}): rol inválido '{rol}'")
                continue

            if self.existe_usuario(email):
                if sobreescribir:
                    try:
                        self.modificar_usuario(email, nombre=nombre, apellidos=apellidos,
                                               rol=rol, grado=grado, grupo=grupo)
                        result["actualizados"] += 1
                    except ValueError as e:
                        result["errores"].append(f"Línea {line_num} ({email}): {e}")
                else:
                    result["saltados"] += 1
                continue

            try:
                self.añadir_usuario(email, nombre=nombre, apellidos=apellidos,
                                    rol=rol, grado=grado, grupo=grupo)
                result["creados"] += 1
            except ValueError as e:
                result["errores"].append(f"Línea {line_num} ({email}): {e}")

        return result

    def exportar_tsv(self, path: Path | str) -> int:
        """Exporta usuarios a un archivo TSV."""
        usuarios = self._load()
        path = Path(path)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t",
                                    extrasaction="ignore")
            writer.writeheader()
            for u in usuarios:
                writer.writerow(u)
        return len(usuarios)

    # ── Stats ──

    def estadisticas(self) -> dict:
        users = self._load()
        total = len(users)
        por_rol = {}
        por_grado = {}
        por_grupo = {}
        for u in users:
            rol = u.get("rol", "estudiante")
            por_rol[rol] = por_rol.get(rol, 0) + 1
            grado = u.get("grado", "")
            if grado:
                por_grado[grado] = por_grado.get(grado, 0) + 1
            grupo = u.get("grupo", "")
            if grupo:
                por_grupo[grupo] = por_grupo.get(grupo, 0) + 1
        return {"total": total, "por_rol": por_rol, "por_grado": por_grado, "por_grupo": por_grupo}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Gestión de usuarios (Moodle SSO, TSV plano)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python user_manager.py ../eulalia listar
  python user_manager.py ../eulalia listar --grado Logopedia
  python user_manager.py ../eulalia añadir ana@uma.es --nombre Ana --apellidos "García" --grado Logopedia
  python user_manager.py ../eulalia eliminar ana@uma.es
  python user_manager.py ../eulalia importar alumnos.tsv
  python user_manager.py ../eulalia exportar alumnos_export.tsv
  python user_manager.py ../eulalia estadisticas
        """,
    )
    parser.add_argument("agent_dir", help="Directorio del agente (ej: ../eulalia)")
    sub = parser.add_subparsers(dest="comando", required=True)

    # listar
    p_list = sub.add_parser("listar", help="Listar usuarios")
    p_list.add_argument("--rol", choices=sorted(ROLES_VALIDOS))
    p_list.add_argument("--grado", help="Filtrar por grado")

    # añadir
    p_add = sub.add_parser("añadir", help="Añadir un usuario")
    p_add.add_argument("email")
    p_add.add_argument("--nombre", default="")
    p_add.add_argument("--apellidos", default="")
    p_add.add_argument("--rol", default="estudiante", choices=sorted(ROLES_VALIDOS))
    p_add.add_argument("--grado", default="")
    p_add.add_argument("--grupo", default="")

    # eliminar
    p_del = sub.add_parser("eliminar", help="Eliminar un usuario")
    p_del.add_argument("email")

    # modificar
    p_mod = sub.add_parser("modificar", help="Modificar un usuario")
    p_mod.add_argument("email")
    p_mod.add_argument("--nombre", default=None)
    p_mod.add_argument("--apellidos", default=None)
    p_mod.add_argument("--rol", default=None, choices=sorted(ROLES_VALIDOS))
    p_mod.add_argument("--grado", default=None)
    p_mod.add_argument("--grupo", default=None)

    # importar
    p_imp = sub.add_parser("importar", help="Importar desde TSV")
    p_imp.add_argument("archivo")
    p_imp.add_argument("--sobreescribir", action="store_true")

    # exportar
    p_exp = sub.add_parser("exportar", help="Exportar a TSV")
    p_exp.add_argument("archivo")

    # estadisticas
    sub.add_parser("estadisticas", help="Estadísticas")

    args = parser.parse_args()
    um = UserManager(args.agent_dir)

    if args.comando == "listar":
        usuarios = um.listar_usuarios(rol=args.rol, grado=args.grado)
        if not usuarios:
            print("No hay usuarios.")
            return
        print(f"{'Email':<35} {'Nombre':<15} {'Apellidos':<20} {'Rol':<12} {'Grado':<30} {'Grupo'}")
        print("-" * 120)
        for u in usuarios:
            print(f"{u['email']:<35} {u['nombre']:<15} {u['apellidos']:<20} {u['rol']:<12} {u['grado']:<30} {u['grupo']}")
        print(f"\nTotal: {len(usuarios)}")

    elif args.comando == "añadir":
        try:
            ok = um.añadir_usuario(args.email, nombre=args.nombre, apellidos=args.apellidos,
                                   rol=args.rol, grado=args.grado, grupo=args.grupo)
            print(f"Usuario '{args.email}' creado." if ok else f"Error: ya existe '{args.email}'.")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)

    elif args.comando == "eliminar":
        print(f"Eliminado." if um.eliminar_usuario(args.email) else f"No encontrado.")

    elif args.comando == "modificar":
        kwargs = {k: v for k, v in vars(args).items()
                  if k in ("nombre", "apellidos", "rol", "grado", "grupo") and v is not None}
        if not kwargs:
            print("No se especificó ningún campo.", file=sys.stderr)
            return
        try:
            print("Actualizado." if um.modificar_usuario(args.email, **kwargs) else "No encontrado.")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)

    elif args.comando == "importar":
        r = um.importar_tsv(args.archivo, sobreescribir=args.sobreescribir)
        print(f"Creados: {r['creados']}, Actualizados: {r['actualizados']}, Saltados: {r['saltados']}")
        for err in r["errores"]:
            print(f"  Error: {err}", file=sys.stderr)

    elif args.comando == "exportar":
        n = um.exportar_tsv(args.archivo)
        print(f"{n} usuarios exportados a '{args.archivo}'.")

    elif args.comando == "estadisticas":
        s = um.estadisticas()
        print(f"Total: {s['total']}")
        for label, data in [("Rol", s["por_rol"]), ("Grado", s["por_grado"]), ("Grupo", s["por_grupo"])]:
            if data:
                print(f"Por {label}: " + ", ".join(f"{k}: {v}" for k, v in sorted(data.items())))


if __name__ == "__main__":
    _cli()

"""
Herramientas de fonética acústica basadas en Praat (vía parselmouth).

Genera espectrogramas y análisis acústicos a partir de archivos de audio.
Las imágenes se guardan como archivos PNG temporales para servir al frontend.

Uso:
    from praat_tools import generar_espectrograma, analizar_formantes

    path_png = generar_espectrograma("audio.wav", output_dir="/tmp")
    formantes = analizar_formantes("audio.wav")
"""

import os
import tempfile
from pathlib import Path

try:
    import parselmouth
    from parselmouth.praat import call
    _PARSELMOUTH_DISPONIBLE = True
except ImportError:
    _PARSELMOUTH_DISPONIBLE = False

try:
    import matplotlib
    matplotlib.use("Agg")  # Backend sin GUI
    import matplotlib.pyplot as plt
    import numpy as np
    _MATPLOTLIB_DISPONIBLE = True
except ImportError:
    _MATPLOTLIB_DISPONIBLE = False


def disponible() -> bool:
    """Comprueba si parselmouth y matplotlib están disponibles."""
    return _PARSELMOUTH_DISPONIBLE and _MATPLOTLIB_DISPONIBLE


def _check_disponible():
    if not _PARSELMOUTH_DISPONIBLE:
        raise RuntimeError(
            "parselmouth no está instalado. "
            "Instálalo con: pip install praat-parselmouth"
        )
    if not _MATPLOTLIB_DISPONIBLE:
        raise RuntimeError(
            "matplotlib no está instalado. "
            "Instálalo con: pip install matplotlib"
        )


# ═══════════════════════════════════════════════════════════════════════
# ESPECTROGRAMA
# ═══════════════════════════════════════════════════════════════════════

def generar_espectrograma(audio_path: str, output_dir: str = None, *,
                          max_freq: float = 5000.0,
                          dynamic_range: float = 70.0,
                          mostrar_formantes: bool = True,
                          mostrar_pitch: bool = False,
                          titulo: str = None) -> str:
    """Genera un espectrograma de banda ancha a partir de un archivo de audio.

    Args:
        audio_path: Ruta al archivo de audio (WAV, MP3, etc.)
        output_dir: Directorio de salida. Si None, usa tempdir.
        max_freq: Frecuencia máxima en Hz (default: 5000)
        dynamic_range: Rango dinámico en dB (default: 70)
        mostrar_formantes: Si True, superpone los formantes F1-F4
        mostrar_pitch: Si True, superpone la curva de F0
        titulo: Título del gráfico. Si None, usa el nombre del archivo.

    Returns:
        Ruta absoluta al archivo PNG generado.
    """
    _check_disponible()

    snd = parselmouth.Sound(audio_path)

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="praat_")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Crear espectrograma
    spectrogram = snd.to_spectrogram(
        window_length=0.005,  # Banda ancha (5ms)
        maximum_frequency=max_freq,
    )

    fig, ax = plt.subplots(figsize=(10, 4))

    # Dibujar espectrograma
    X, Y = spectrogram.x_grid(), spectrogram.y_grid()
    sg_db = 10 * np.log10(spectrogram.values + 1e-20)
    # x_grid/y_grid devuelven los bordes de celda (N+1), values es (N_freq, N_time)
    ax.pcolormesh(X, Y, sg_db, vmin=sg_db.max() - dynamic_range,
                  cmap="binary", shading="auto")

    # Formantes
    if mostrar_formantes:
        try:
            formant = snd.to_formant_burg(max_number_of_formants=4.0,
                                           maximum_formant=max_freq)
            times = np.linspace(snd.xmin, snd.xmax, 200)
            colores = ["#e63946", "#457b9d", "#2a9d8f", "#e9c46a"]
            for i_formant in range(1, 5):
                freqs = [formant.get_value_at_time(i_formant, t) for t in times]
                freqs_clean = [(t, f) for t, f in zip(times, freqs)
                               if f is not None and not np.isnan(f) and 0 < f < max_freq]
                if freqs_clean:
                    ts, fs = zip(*freqs_clean)
                    ax.plot(ts, fs, color=colores[i_formant - 1],
                            linewidth=1.5, alpha=0.8,
                            label=f"F{i_formant}")
            ax.legend(loc="upper right", fontsize=8, framealpha=0.7)
        except Exception:
            pass  # Si falla el cálculo de formantes, mostrar solo espectrograma

    # Pitch (F0)
    if mostrar_pitch:
        try:
            pitch = snd.to_pitch()
            pitch_values = pitch.selected_array["frequency"]
            pitch_times = pitch.xs()
            voiced = pitch_values > 0
            ax2 = ax.twinx()
            ax2.plot(pitch_times[voiced], pitch_values[voiced],
                     "o-", color="#f77f00", markersize=2, linewidth=1.5,
                     alpha=0.9, label="F0")
            ax2.set_ylabel("F0 (Hz)", color="#f77f00")
            ax2.set_ylim(50, 500)
            ax2.legend(loc="upper left", fontsize=8)
        except Exception:
            pass

    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Frecuencia (Hz)")
    if titulo:
        ax.set_title(titulo)
    else:
        nombre = Path(audio_path).stem
        ax.set_title(f"Espectrograma: {nombre}")

    fig.tight_layout()

    # Guardar
    basename = Path(audio_path).stem
    output_path = os.path.join(output_dir, f"{basename}_espectrograma.png")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path


# ═══════════════════════════════════════════════════════════════════════
# OSCILOGRAMA
# ═══════════════════════════════════════════════════════════════════════

def generar_oscilograma(audio_path: str, output_dir: str = None, *,
                        titulo: str = None) -> str:
    """Genera un oscilograma (forma de onda) de un archivo de audio.

    Returns:
        Ruta absoluta al archivo PNG generado.
    """
    _check_disponible()

    snd = parselmouth.Sound(audio_path)

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="praat_")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 3))

    times = snd.xs()
    values = snd.values[0] if snd.values.ndim > 1 else snd.values.flatten()
    ax.plot(times, values, color="#1d3557", linewidth=0.3)
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Amplitud")
    ax.set_xlim(snd.xmin, snd.xmax)

    if titulo:
        ax.set_title(titulo)
    else:
        ax.set_title(f"Oscilograma: {Path(audio_path).stem}")

    fig.tight_layout()

    basename = Path(audio_path).stem
    output_path = os.path.join(output_dir, f"{basename}_oscilograma.png")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path


# ═══════════════════════════════════════════════════════════════════════
# ANÁLISIS DE FORMANTES
# ═══════════════════════════════════════════════════════════════════════

def analizar_formantes(audio_path: str, *, max_formants: int = 4,
                       max_freq: float = 5000.0) -> list[dict]:
    """Extrae los valores medios de formantes (F1-F4) de un archivo de audio.

    Returns:
        Lista de dicts con time, F1, F2, F3, F4 (en Hz).
        Los valores None indican tramos sin voz.
    """
    _check_disponible()

    snd = parselmouth.Sound(audio_path)
    formant = snd.to_formant_burg(
        max_number_of_formants=float(max_formants),
        maximum_formant=max_freq,
    )

    resultados = []
    n_frames = formant.get_number_of_frames()
    for i in range(1, n_frames + 1):
        t = formant.get_time_from_frame_number(i)
        entry = {"time": round(t, 4)}
        for f in range(1, max_formants + 1):
            val = formant.get_value_at_time(f, t)
            entry[f"F{f}"] = round(val, 1) if val is not None and not np.isnan(val) else None
        resultados.append(entry)

    return resultados


def resumen_formantes(audio_path: str) -> dict | None:
    """Calcula los formantes medios (F1, F2, F3) del segmento sonoro.

    Útil para identificar vocales: F1 (apertura), F2 (anterioridad).

    Returns:
        dict con F1_medio, F2_medio, F3_medio (en Hz), o None si no hay voz.
    """
    _check_disponible()

    datos = analizar_formantes(audio_path, max_formants=3)
    f1s = [d["F1"] for d in datos if d["F1"] is not None and d["F1"] > 0]
    f2s = [d["F2"] for d in datos if d["F2"] is not None and d["F2"] > 0]
    f3s = [d["F3"] for d in datos if d["F3"] is not None and d["F3"] > 0]

    if not f1s:
        return None

    return {
        "F1_medio": round(sum(f1s) / len(f1s), 1),
        "F2_medio": round(sum(f2s) / len(f2s), 1),
        "F3_medio": round(sum(f3s) / len(f3s), 1) if f3s else None,
        "num_frames": len(datos),
        "frames_sonoros": len(f1s),
    }


# ═══════════════════════════════════════════════════════════════════════
# ANÁLISIS DE PITCH (F0)
# ═══════════════════════════════════════════════════════════════════════

def analizar_pitch(audio_path: str) -> dict | None:
    """Extrae estadísticas de F0 (frecuencia fundamental).

    Returns:
        dict con F0_medio, F0_min, F0_max (en Hz), o None si no hay voz.
    """
    _check_disponible()

    snd = parselmouth.Sound(audio_path)
    pitch = snd.to_pitch()
    f0_values = pitch.selected_array["frequency"]
    voiced = f0_values[f0_values > 0]

    if len(voiced) == 0:
        return None

    return {
        "F0_medio": round(float(np.mean(voiced)), 1),
        "F0_min": round(float(np.min(voiced)), 1),
        "F0_max": round(float(np.max(voiced)), 1),
        "F0_desv": round(float(np.std(voiced)), 1),
        "porcentaje_sonoro": round(len(voiced) / len(f0_values) * 100, 1),
    }


# ═══════════════════════════════════════════════════════════════════════
# ANÁLISIS COMPLETO (para el agente)
# ═══════════════════════════════════════════════════════════════════════

def analisis_completo(audio_path: str, output_dir: str = None) -> dict:
    """Realiza un análisis acústico completo de un archivo de audio.

    Returns:
        dict con:
            - espectrograma_path: ruta al PNG del espectrograma
            - oscilograma_path: ruta al PNG del oscilograma
            - formantes: resumen de formantes medios
            - pitch: estadísticas de F0
            - duracion: duración en segundos
    """
    _check_disponible()

    snd = parselmouth.Sound(audio_path)

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="praat_")

    return {
        "espectrograma_path": generar_espectrograma(
            audio_path, output_dir, mostrar_formantes=True, mostrar_pitch=True),
        "oscilograma_path": generar_oscilograma(audio_path, output_dir),
        "formantes": resumen_formantes(audio_path),
        "pitch": analizar_pitch(audio_path),
        "duracion": round(snd.xmax - snd.xmin, 3),
    }


def formatear_analisis(resultado: dict) -> str:
    """Formatea los resultados de analisis_completo() en markdown para el chat."""
    lineas = ["## Análisis acústico\n"]

    lineas.append(f"**Duración:** {resultado['duracion']} s\n")

    pitch = resultado.get("pitch")
    if pitch:
        lineas.append("### Frecuencia fundamental (F0)")
        lineas.append(f"- F0 medio: **{pitch['F0_medio']} Hz**")
        lineas.append(f"- Rango: {pitch['F0_min']} – {pitch['F0_max']} Hz")
        lineas.append(f"- Desviación: {pitch['F0_desv']} Hz")
        lineas.append(f"- Porcentaje sonoro: {pitch['porcentaje_sonoro']}%")
        lineas.append("")

    formantes = resultado.get("formantes")
    if formantes:
        lineas.append("### Formantes medios")
        lineas.append(f"- F1: **{formantes['F1_medio']} Hz** (correlato de apertura)")
        lineas.append(f"- F2: **{formantes['F2_medio']} Hz** (correlato de anterioridad)")
        if formantes.get("F3_medio"):
            lineas.append(f"- F3: {formantes['F3_medio']} Hz")
        lineas.append(f"- Frames sonoros: {formantes['frames_sonoros']}/{formantes['num_frames']}")
        lineas.append("")

    return "\n".join(lineas)

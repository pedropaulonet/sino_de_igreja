#!/usr/bin/env python3
"""
Sino de Igreja - Raspberry Pi
Toca sinos em horários programados com interface terminal
"""

import json
import os
import sys
import time
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Optional, List, Dict

try:
    import curses
    CURSES_DISPONIVEL: bool = True
except ImportError:
    CURSES_DISPONIVEL = False
    curses = None

CONFIG_FILE = "config.json"
__version__ = "1.0.0"
__author__ = "Pedro Paulo"
__email__ = "contato@pedropaulo.net"
__repo__ = "https://github.com/pedropaulonet/sino_de_igreja"


def exibir_sobre():
    print("Sino de Igreja")
    print(f"Versão {__version__}")
    print(f"LICENSE: MIT - https://opensource.org/licenses/MIT")
    print(f"Contato: {__email__}")
    print(f"Repositório: {__repo__}")
    print()


class AudioPlayer:
    def __init__(self):
        self.pygame_available = False
        self.player_command = None
        # Track subprocesses started by this player so we can stop them reliably
        self._procs = []
        self._lock = threading.Lock()
        self._stop_requested = False
        try:
            import pygame
            pygame.mixer.init()
            self.pygame_available = True
        except ImportError:
            pass

        if not self.pygame_available:
            for cmd in [["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"], ["paplay"], ["aplay"], ["omxplayer", "-o", "local"]]:
                if subprocess.call(["which", cmd[0]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                    self.player_command = cmd
                    break

    def play(self, filepath: str, blocking: bool = True) -> bool:
        if not os.path.exists(filepath):
            print(f"  AVISO: Arquivo não encontrado: {filepath}")
            return False

        self._stop_requested = False

        if self.pygame_available:
            import pygame
            if blocking:
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if self._stop_requested:
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.1)
            else:
                pygame.mixer.Sound(filepath).play()
        elif self.player_command:
            cmd = self.player_command + [filepath]
            # Use Popen for both blocking and non-blocking so we can stop specific processes later
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self._lock:
                self._procs.append(proc)

            if blocking:
                try:
                    while proc.poll() is None:
                        if self._stop_requested:
                            try:
                                proc.terminate()
                                proc.wait(timeout=1)
                            except Exception:
                                proc.kill()
                            break
                        time.sleep(0.1)
                finally:
                    with self._lock:
                        if proc in self._procs:
                            self._procs.remove(proc)
        else:
            print("  ERRO: Nenhum player de áudio disponível. Instale: pygame, ffmpeg, pulseaudio ou omxplayer")
            return False

        return True

    def stop(self):
        self._stop_requested = True
        if self.pygame_available:
            import pygame
            pygame.mixer.music.stop()
            pygame.mixer.stop()  # Also stop Sound channels
        elif self.player_command:
            # Terminate only processes we started
            with self._lock:
                procs = list(self._procs)
                self._procs.clear()

            for p in procs:
                try:
                    if p.poll() is None:
                        p.terminate()
                        try:
                            p.wait(timeout=1)
                        except Exception:
                            p.kill()
                except Exception:
                    # ignore individual failures and try to continue
                    pass

            # As a last resort, try pkill for known player names (handles players not started by us)
            player_name = self.player_command[0]
            if player_name == "ffplay":
                subprocess.run(["pkill", "-f", "ffplay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif player_name == "omxplayer":
                subprocess.run(["pkill", "-f", "omxplayer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif player_name == "paplay":
                subprocess.run(["pkill", "-9", "-x", "paplay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif player_name == "aplay":
                subprocess.run(["pkill", "-9", "-x", "aplay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class ScheduleManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config: Dict = {}
        self.audio = AudioPlayer()
        self.running = True
        self.ultimo_toque: Optional[datetime] = None
        self.tocando_agora = False
        self.parar_loop = False

    def carregar_config(self) -> bool:
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            return True
        except FileNotFoundError:
            print(f"ERRO: Arquivo de configuração não encontrado: {self.config_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"ERRO: JSON inválido: {e}")
            return False

    def obter_proximos_toques(self, limite: int = 5) -> List[Dict]:
        agora = datetime.now()
        toques = []

        for item in self.config.get("programacao", []):
            hora = item["hora"]
            minuto = item["minuto"]

            proximo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if proximo <= agora:
                proximo += timedelta(days=1)

            toques.append({
                "hora": hora,
                "minuto": minuto,
                "som": item["som"],
                "repeticoes": item["repeticoes"],
                "proximo": proximo,
                "diferenca": (proximo - agora).total_seconds()
            })

        toques.sort(key=lambda x: x["diferenca"])
        return toques[:limite]

    def obter_proximo_toque_ativo(self) -> Optional[Dict]:
        toques = self.obter_proximos_toques(100)
        return toques[0] if toques else None

    def tocar_sino(self, item: Dict):
        if self.tocando_agora:
            return

        self.tocando_agora = True
        self.parar_loop = False
        self.audio._stop_requested = False

        sonido_key = item["som"]
        repeticiones = item["repeticoes"]

        sonidos = self.config.get("sons", {})
        filepath = sonidos.get(sonido_key, f"sounds/{sonido_key}.mp3")

        if not os.path.exists(filepath):
            filepath = f"sounds/{sonido_key}.mp3"

        print(f"TOCANDO: {hora_str(item['hora'], item['minuto'])} - {sonido_key} x{repeticiones}")

        for i in range(repeticiones):
            if self.parar_loop:
                print("  Parado pelo usuário")
                break
            print(f"  Toque {i+1}/{repeticiones}")
            self.audio.play(filepath, blocking=True)

            if i < repeticiones - 1 and not self.parar_loop:
                time.sleep(0.5)

        self.ultimo_toque = datetime.now()
        self.tocando_agora = False

    def parar_audio(self):
        self.parar_loop = True
        self.audio.stop()
        self.tocando_agora = False

    def verificar_e_tocar(self) -> bool:
        agora = datetime.now()

        for item in self.config.get("programacao", []):
            if agora.hour == item["hora"] and agora.minute == item["minuto"]:
                if self.ultimo_toque:
                    if self.ultimo_toque.minute == agora.minute and self.ultimo_toque.hour == agora.hour:
                        continue

                self.tocar_sino(item)
                return True

        return False


def hora_str(hora: int, minuto: int) -> str:
    return f"{hora:02d}:{minuto:02d}"


def formatar_diferenca(segundos: float) -> str:
    if segundos < 60:
        return f"{int(segundos)} seg"
    elif segundos < 3600:
        return f"{int(segundos // 60)} min"
    else:
        horas = int(segundos // 3600)
        minutos = int((segundos % 3600) // 60)
        return f"{horas}h {minutos}min"


def safe_addstr(stdscr, y, x, text, attr=curses.A_NORMAL):
    """Add string to curses screen, truncating if it would overflow."""
    try:
        max_y, max_x = stdscr.getmaxyx()
        if y < 0 or y >= max_y:
            return
        available = max_x - x - 1
        if available <= 0:
            return
        stdscr.addstr(y, x, text[:available], attr)
    except curses.error:
        pass


class InterfaceCurses:
    def __init__(self, manager: ScheduleManager):
        self.manager = manager

    def iniciar(self):
        curses.wrapper(self._loop_principal)

    def _desenhar(self, stdscr):
        altura, largura = stdscr.getmaxyx()

        agora = datetime.now()

        stdscr.attrset(curses.A_NORMAL)
        stdscr.clear()
        stdscr.erase()

        titulo = "SINO DE IGREJA"
        safe_addstr(stdscr, 0, (largura - len(titulo)) // 2, titulo, curses.A_BOLD | curses.color_pair(1))

        horario = agora.strftime("%H:%M:%S")
        data = agora.strftime("%d/%m/%Y")
        safe_addstr(stdscr, 2, 2, f"{horario}", curses.A_BOLD)
        safe_addstr(stdscr, 2, 12, data)

        if self.manager.ultimo_toque:
            ultimo = self.manager.ultimo_toque.strftime("%H:%M:%S")
            safe_addstr(stdscr, 3, 2, f"Último toque: {ultimo}")

        safe_addstr(stdscr, 5, 2, "PRÓXIMOS TOQUES:", curses.A_BOLD)

        toques = self.manager.obter_proximos_toques(13)
        for i, toque in enumerate(toques):
            linha = 6 + i
            if linha >= altura - 3:
                break

            diff_str = formatar_diferenca(toque["diferenca"])
            num_key = str(i + 1) if i < 9 else " "
            texto = f"[{num_key}] {hora_str(toque['hora'], toque['minuto'])}  {toque['som']:12s}  x{toque['repeticoes']}  {diff_str}"

            if i == 0:
                safe_addstr(stdscr, linha, 2, texto, curses.A_REVERSE)
            else:
                safe_addstr(stdscr, linha, 2, texto)

        if self.manager.tocando_agora:
            msg = "TOCANDO..."
            safe_addstr(stdscr, altura // 2, (largura - len(msg)) // 2, msg, curses.A_BOLD | curses.color_pair(2))

        rodape = f"[Q] Sair  [R] Recarregar  [T] Sino  [S] Parar  [1-9] Testar   v{__version__}"
        safe_addstr(stdscr, altura - 1, (largura - len(rodape)) // 2, rodape, curses.A_DIM)

        sobre_linha = f"contato@pedropaulo.net | {__repo__}"
        safe_addstr(stdscr, altura - 2, (largura - len(sobre_linha)) // 2, sobre_linha, curses.A_DIM)

        stdscr.refresh()

    def _loop_principal(self, stdscr):
        curses.curs_set(0)
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_GREEN)

        stdscr.nodelay(True)

        ultimo_minuto = -1
        ultimo_segundo = -1

        while True:
            key = stdscr.getch()

            if key == ord('q') or key == ord('Q'):
                self.manager.running = False
                break
            elif key == ord('r') or key == ord('R'):
                self.manager.carregar_config()
            elif key == ord('t') or key == ord('T'):
                if not self.manager.tocando_agora:
                    sonidos = self.manager.config.get("sons", {})
                    if "sino" in sonidos:
                        som = sonidos["sino"]
                        threading.Thread(target=lambda s=som: self.manager.audio.play(s, blocking=True), daemon=True).start()
            elif key == ord('s') or key == ord('S'):
                self.manager.parar_audio()
            elif key == ord(' ') or key == 10:
                if not self.manager.tocando_agora:
                    sonidos = self.manager.config.get("sons", {})
                    if "sino" in sonidos:
                        som = sonidos["sino"]
                        def tocar_forcado(s=som):
                            self.manager.tocando_agora = True
                            self.manager.parar_loop = False
                            self.manager.audio._stop_requested = False
                            try:
                                for i in range(3):
                                    if self.manager.parar_loop:
                                        break
                                    self.manager.audio.play(s, blocking=True)
                                    if i < 2 and not self.manager.parar_loop:
                                        time.sleep(0.5)
                            finally:
                                self.manager.tocando_agora = False
                        threading.Thread(target=tocar_forcado, daemon=True).start()
            elif 48 < key < 58:
                idx = key - 49
                toques = self.manager.obter_proximos_toques(13)
                if idx < len(toques):
                    item = toques[idx]
                    def tocar_item(it=item):
                        self.manager.tocar_sino(it)
                    threading.Thread(target=tocar_item, daemon=True).start()

            agora = datetime.now()

            if agora.minute != ultimo_minuto:
                ultimo_minuto = agora.minute
                threading.Thread(target=self.manager.verificar_e_tocar, daemon=True).start()

            if agora.second != ultimo_segundo:
                ultimo_segundo = agora.second
                self._desenhar(stdscr)

            time.sleep(0.1)


def modo_console(manager: ScheduleManager):
    exibir_sobre()
    print("SINO DE IGREJA - Modo Console")
    print("=" * 40)
    print(f"Configuração: {CONFIG_FILE}")
    print("Pressione Ctrl+C para sair")
    print()

    ultimo_minuto = -1

    try:
        while manager.running:
            agora = datetime.now()

            if agora.minute != ultimo_minuto:
                ultimo_minuto = agora.minute
                threading.Thread(target=manager.verificar_e_tocar, daemon=True).start()

            proximo = manager.obter_proximo_toque_ativo()

            if proximo:
                diff = formatar_diferenca(proximo["diferenca"])
                print(f"\r{agora.strftime('%H:%M:%S')} Próximo: {hora_str(proximo['hora'], proximo['minuto'])} ({diff})", end="")

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando...")
        manager.running = False
    print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--sobre", "--about"):
        exibir_sobre()
        sys.exit(0)

    manager = ScheduleManager(CONFIG_FILE)
    if not manager.carregar_config():
        sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--console":
        modo_console(manager)
    elif CURSES_DISPONIVEL:
        try:
            interface = InterfaceCurses(manager)
            interface.iniciar()
        except Exception:
            print("\nCurses error, usando modo console...")
            modo_console(manager)
    else:
        print("Curses não disponível, usando modo console...")
        modo_console(manager)


if __name__ == "__main__":
    main()
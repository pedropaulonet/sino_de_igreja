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


class AudioPlayer:
    def __init__(self):
        self.pygame_available = False
        self.player_command = None
        # Track subprocesses started by this player so we can stop them reliably
        self._procs = []
        self._lock = threading.Lock()
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

        if self.pygame_available:
            import pygame
            if blocking:
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
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
                    proc.wait()
                finally:
                    with self._lock:
                        if proc in self._procs:
                            self._procs.remove(proc)
        else:
            print("  ERRO: Nenhum player de áudio disponível. Instale: pygame, ffmpeg, pulseaudio ou omxplayer")
            return False

        return True

    def stop(self):
        if self.pygame_available:
            import pygame
            pygame.mixer.music.stop()
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

    def hora_permitida(self) -> bool:
        return True

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
            # Play non-blocking via thread so UI stays responsive; but wait for each play to finish
            if self.audio.pygame_available:
                # pygame supports blocking playback through mixer
                self.audio.play(filepath, blocking=True)
            else:
                # For subprocess players we already track processes; use blocking behavior
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
        stdscr.addstr(0, (largura - len(titulo)) // 2, titulo, curses.A_BOLD | curses.color_pair(1))

        horario = agora.strftime("%H:%M:%S")
        data = agora.strftime("%d/%m/%Y")
        stdscr.addstr(2, 2, f"{horario}", curses.A_BOLD)
        stdscr.addstr(2, 12, data)

        if self.manager.ultimo_toque:
            ultimo = self.manager.ultimo_toque.strftime("%H:%M:%S")
            stdscr.addstr(3, 2, f"Último toque: {ultimo}")

        stdscr.addstr(5, 2, "PRÓXIMOS TOQUES:", curses.A_BOLD)

        toques = self.manager.obter_proximos_toques(13)
        for i, toque in enumerate(toques):
            linha = 6 + i
            if linha >= altura - 3:
                break

            diff_str = formatar_diferenca(toque["diferenca"])
            num_key = str(i + 1) if i < 9 else " "
            texto = f"[{num_key}] {hora_str(toque['hora'], toque['minuto'])}  {toque['som']:12s}  x{toque['repeticoes']}  {diff_str}"

            if i == 0:
                stdscr.addstr(linha, 2, texto, curses.A_REVERSE)
            else:
                stdscr.addstr(linha, 2, texto)

        if self.manager.tocando_agora:
            msg = "TOCANDO..."
            stdscr.addstr(altura // 2, (largura - len(msg)) // 2, msg, curses.A_BOLD | curses.color_pair(2))

        rodape = "[Q] Sair  [R] Recarregar  [T] Sino  [S] Parar  [1-9] Testar"
        stdscr.addstr(altura - 1, (largura - len(rodape)) // 2, rodape, curses.A_DIM)

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
                sonidos = self.manager.config.get("sons", {})
                if "sino" in sonidos:
                    som = sonidos["sino"]
                    threading.Thread(target=lambda s=som: self.manager.audio.play(s, blocking=True)).start()
            elif key == ord('s') or key == ord('S'):
                self.manager.parar_audio()
            elif key == ord(' ') or key == 10:
                sonidos = self.manager.config.get("sons", {})
                if "sino" in sonidos:
                    som = sonidos["sino"]
                    def tocar_forcado(s=som):
                        for i in range(3):
                            self.manager.audio.play(s, blocking=True)
                    threading.Thread(target=tocar_forcado).start()
            elif 48 < key < 58:
                idx = key - 49
                toques = self.manager.obter_proximos_toques(13)
                if idx < len(toques):
                    item = toques[idx]
                    def tocar_item(it=item):
                        self.manager.tocar_sino(it)
                    threading.Thread(target=tocar_item).start()

            agora = datetime.now()

            if agora.minute != ultimo_minuto:
                ultimo_minuto = agora.minute
                threading.Thread(target=self.manager.verificar_e_tocar).start()

            if agora.second != ultimo_segundo:
                ultimo_segundo = agora.second
                self._desenhar(stdscr)

            time.sleep(0.1)


def modo_console(manager: ScheduleManager):
    print("SINO DE IGREJA - Modo Console")
    print("=" * 40)
    print(f"Configuração: {CONFIG_FILE}")
    print("Pressione Ctrl+C para sair")
    print()

    ultimo_minuto = -1

    while manager.running:
        agora = datetime.now()

        if agora.minute != ultimo_minuto:
            ultimo_minuto = agora.minute
            manager.verificar_e_tocar()

        proximo = manager.obter_proximo_toque_ativo()

        if proximo:
            diff = formatar_diferenca(proximo["diferenca"])
            print(f"\r{agora.strftime('%H:%M:%S')} Próximo: {hora_str(proximo['hora'], proximo['minuto'])} ({diff})", end="")

        time.sleep(1)
    print()


def main():
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

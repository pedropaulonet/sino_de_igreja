#!/usr/bin/env python3
"""
Sino de Igreja - Interface Gráfica Tkinter Moderna
Executa o sino com interface GUI moderna e elegante.
"""

import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime
from tkinter import *
from tkinter import messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sino_igreja import (
    CONFIG_FILE,
    AudioPlayer,
    ScheduleManager,
    __author__,
    __email__,
    __repo__,
    __version__,
    formatar_diferenca,
    hora_str,
)


class SinoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sino de Igreja")
        self.root.resizable(False, False)
        self.root.geometry("500x720")
        self.root.configure(bg="#090d14")

        self.manager = ScheduleManager(CONFIG_FILE)
        if not self.manager.carregar_config():
            self.manager.config = {"sons": {}, "programacao": []}

        self.audio = AudioPlayer()
        self.tocando = False
        self.running = True
        self._ultimo_minuto = -1
        self._ativado = True

        self._cores = {
            "bg_principal": "#0a0a0a",
            "bg_card": "#141414",
            "bg_card_escuro": "#1a1a1a",
            "destaque": "#ffffff",
            "destaque_hover": "#cccccc",
            "sucesso": "#ffffff",
            "sucesso_escuro": "#e0e0e0",
            "texto": "#e0e0e0",
            "texto_secundario": "#666666",
            "borda": "#222222",
            "aviso": "#e0e0e0",
            "inativo": "#444444",
        }

        self._setup_ui()
        self._iniciar_atualizacao()

    def _criar_card(self, parent, padding=15):
        card = Frame(parent, bg=self._cores["bg_card"], relief=FLAT, bd=0)

        separator = Frame(card, bg=self._cores["borda"], height=1)
        separator.pack(fill=X, padx=20)

        card.pack(fill=X, padx=20, pady=(0, padding))

        Frame(card, bg=self._cores["bg_card"], height=8).pack()

        return card

    def _criar_botao(
        self, parent, texto, comando, icone="", cor=None, cor_hover=None, tamanho=11
    ):
        """"""
        if cor is None:
            cor = self._cores["destaque"]
        if cor_hover is None:
            cor_hover = self._cores["destaque_hover"]

        btn = Button(
            parent,
            text=f"{icone}  {texto}" if icone else texto,
            command=comando,
            bg=cor,
            fg="white",
            relief=FLAT,
            bd=0,
            font=("DejaVu Sans", tamanho, "bold"),
            cursor="hand1",
            padx=15,
            pady=8,
            activebackground=cor_hover,
            activeforeground="white",
        )

        btn.bind("<Enter>", lambda e: btn.config(bg=cor_hover))
        btn.bind("<Leave>", lambda e: btn.config(bg=cor))

        return btn

    def _setup_ui(self):
        """Configura a interface gráfica principal."""
        c = self._cores

        # Header com título
        frame_header = Frame(self.root, bg=c["bg_principal"], height=60)
        frame_header.pack(fill=X, padx=20, pady=(15, 0))
        frame_header.pack_propagate(False)

        Label(
            frame_header,
            text="SINO DE IGREJA",
            font=("DejaVu Sans", 18, "bold"),
            fg=c["destaque"],
            bg=c["bg_principal"],
        ).pack(pady=(10, 0))

        Label(
            frame_header,
            text="Sistema de Toques Programados",
            font=("DejaVu Sans", 9),
            fg=c["texto_secundario"],
            bg=c["bg_principal"],
        ).pack()

        # Card do Relógio e Status
        card_relogio = self._criar_card(self.root, padding=10)

        # Botão Ativar/Desativar no topo do card
        frame_controle = Frame(card_relogio, bg=c["bg_card"])
        frame_controle.pack(fill=X, padx=12, pady=(5, 0))

        self.btn_ativar = self._criar_botao(
            frame_controle,
            "Ativo",
            self._toggle_ativado,
            "",
            c["bg_card_escuro"],
            c["borda"],
            tamanho=9,
        )
        self.btn_ativar.pack(side=RIGHT)

        Label(
            frame_controle,
            text="Sistema",
            font=("DejaVu Sans", 10),
            fg=c["texto_secundario"],
            bg=c["bg_card"],
        ).pack(side=LEFT)

        self.label_relogio = Label(
            card_relogio,
            text="00:00:00",
            font=("DejaVu Sans", 46, "bold"),
            fg=c["sucesso"],
            bg=c["bg_card"],
        )
        self.label_relogio.pack(pady=(12, 5))

        self.label_data = Label(
            card_relogio,
            text="",
            font=("DejaVu Sans", 11),
            fg=c["texto_secundario"],
            bg=c["bg_card"],
        )
        self.label_data.pack(pady=(0, 5))

        # Status indicator
        self.frame_status = Frame(card_relogio, bg=c["bg_card"])
        self.frame_status.pack(pady=3)

        self.indicador = Canvas(
            self.frame_status,
            width=10,
            height=10,
            bg=c["bg_card"],
            highlightthickness=0,
        )
        self.indicador.pack(side=LEFT, padx=(0, 6))
        self.indicador_id = self.indicador.create_oval(
            2, 2, 8, 8, fill=c["sucesso_escuro"], outline=""
        )

        self.label_status = Label(
            self.frame_status,
            text="Sistema Ativo",
            font=("DejaVu Sans", 10, "bold"),
            fg=c["sucesso_escuro"],
            bg=c["bg_card"],
        )
        self.label_status.pack(side=LEFT)

        self.label_ultimo = Label(
            card_relogio,
            text="",
            font=("DejaVu Sans", 9),
            fg=c["texto_secundario"],
            bg=c["bg_card"],
        )
        self.label_ultimo.pack(pady=(3, 8))

        # Card dos Próximos Toques
        card_toques = self._criar_card(self.root, padding=10)

        header_toques = Frame(card_toques, bg=c["bg_card"])
        header_toques.pack(fill=X, padx=15, pady=(10, 5))

        Label(
            header_toques,
            text="Próximos Toques",
            font=("DejaVu Sans", 12, "bold"),
            fg=c["texto"],
            bg=c["bg_card"],
        ).pack(side=LEFT)

        # Lista de toques com scrollbar customizada
        frame_lista = Frame(card_toques, bg=c["bg_card"])
        frame_lista.pack(fill=X, padx=15, pady=(0, 10))

        scrollbar = Scrollbar(
            frame_lista,
            bg=c["bg_card"],
            troughcolor=c["bg_card_escuro"],
            activebackground=c["destaque"],
        )
        scrollbar.pack(side=RIGHT, fill=Y)

        self.listbox_toques = Listbox(
            frame_lista,
            height=6,
            font=("DejaVu Sans Mono", 10),
            bg=c["bg_card_escuro"],
            fg=c["texto"],
            relief=FLAT,
            bd=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
            selectbackground=c["destaque"],
            selectforeground="white",
        )
        self.listbox_toques.pack(fill=X, padx=(0, 5))
        scrollbar.config(command=self.listbox_toques.yview)

        # Card de Controles
        card_controles = self._criar_card(self.root, padding=8)

        Label(
            card_controles,
            text="Controles",
            font=("DejaVu Sans", 11, "bold"),
            fg=c["texto"],
            bg=c["bg_card"],
        ).pack(anchor=W, padx=12, pady=(8, 5))

        # Grid de botões (2x3)
        frame_botoes = Frame(card_controles, bg=c["bg_card"])
        frame_botoes.pack(fill=X, padx=12, pady=(0, 10))

        # Linha 1
        btn_tocar = self._criar_botao(
            frame_botoes,
            "Tocar",
            self._tocar_sino,
            "🔔",
            c["bg_card_escuro"],
            c["borda"],
            tamanho=10,
        )
        btn_tocar.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)

        btn_parar = self._criar_botao(
            frame_botoes, "Parar", self._parar, "", c["bg_card_escuro"], c["borda"], tamanho=10
        )
        btn_parar.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        btn_recarregar = self._criar_botao(
            frame_botoes,
            "Atualizar",
            self._recarregar,
            "🔄",
            c["bg_card_escuro"],
            c["borda"],
            tamanho=10,
        )
        btn_recarregar.grid(row=0, column=2, sticky="ew", padx=(4, 0), pady=2)

        # Linha 2
        btn_testar = self._criar_botao(
            frame_botoes,
            "Testar",
            self._abrir_teste,
            "",
            c["bg_card_escuro"],
            c["borda"],
            tamanho=10,
        )
        btn_testar.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=2)

        btn_config = self._criar_botao(
            frame_botoes,
            "Config JSON",
            self._abrir_config,
            "⚙️",
            c["bg_card_escuro"],
            c["borda"],
            tamanho=10,
        )
        btn_config.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        btn_sobre = self._criar_botao(
            frame_botoes,
            "Sobre",
            self._abrir_sobre,
            "",
            c["bg_card_escuro"],
            c["borda"],
            tamanho=10,
        )
        btn_sobre.grid(row=1, column=2, sticky="ew", padx=(4, 0), pady=2)

        frame_botoes.columnconfigure(0, weight=1)
        frame_botoes.columnconfigure(1, weight=1)
        frame_botoes.columnconfigure(2, weight=1)

        # Rodapé
        frame_rodape = Frame(self.root, bg=c["bg_principal"])
        frame_rodape.pack(fill=X, side=BOTTOM, pady=(5, 10))

        Label(
            frame_rodape,
            text=f"v{__version__} • Sino de Igreja",
            font=("DejaVu Sans", 8),
            fg=c["texto_secundario"],
            bg=c["bg_principal"],
        ).pack()

    def _toggle_ativado(self):
        """Alterna entre sistema ativo e inativo."""
        self._ativado = not self._ativado
        c = self._cores

        if self._ativado:
            self.btn_ativar.config(text="●  Ativo", bg=c["borda"])
            self.btn_ativar.bind(
                "<Leave>", lambda e: self.btn_ativar.config(bg=c["borda"])
            )
            self.label_status.config(text="Sistema Ativo", fg=c["sucesso"])
            self.indicador.itemconfig(self.indicador_id, fill=c["sucesso"])
        else:
            self.btn_ativar.config(text="○  Inativo", bg=c["inativo"])
            self.btn_ativar.bind(
                "<Leave>", lambda e: self.btn_ativar.config(bg=c["inativo"])
            )
            self.label_status.config(text="Sistema Inativo", fg=c["inativo"])
            self.indicador.itemconfig(self.indicador_id, fill=c["inativo"])

    def _abrir_teste(self):
        """Abre janela para testar sons individualmente."""
        janela = Toplevel(self.root)
        janela.title("Testar Sons")
        janela.geometry("350x300")
        janela.configure(bg=self._cores["bg_card"])
        janela.resizable(False, False)
        janela.transient(self.root)
        janela.grab_set()

        c = self._cores

        Label(
            janela,
            text="Testar Sons",
            font=("DejaVu Sans", 14, "bold"),
            fg=c["texto"],
            bg=c["bg_card"],
        ).pack(pady=(20, 15))

        frame_sons = Frame(janela, bg=c["bg_card"])
        frame_sons.pack(fill=BOTH, expand=True, padx=20, pady=10)

        sons = self.manager.config.get("sons", {})

        if not sons:
            Label(
                frame_sons,
                text="Nenhum som configurado",
                font=("DejaVu Sans", 11),
                fg=c["texto_secundario"],
                bg=c["bg_card"],
            ).pack(pady=20)
        else:
            for nome, caminho in sorted(sons.items()):
                frame_som = Frame(frame_sons, bg=c["bg_card_escuro"], padx=10, pady=5)
                frame_som.pack(fill=X, pady=3)

                Label(
                    frame_som,
                    text=nome,
                    font=("DejaVu Sans", 11),
                    fg=c["texto"],
                    bg=c["bg_card_escuro"],
                ).pack(side=LEFT)

                btn = Button(
                    frame_som,
                    text="▶ Tocar",
                    command=lambda n=nome, p=caminho: self._testar_som_individual(p),
                    bg=c["bg_card_escuro"],
                    fg=c["texto"],
                    relief=FLAT,
                    bd=0,
                    font=("DejaVu Sans", 9, "bold"),
                    cursor="hand1",
                    padx=10,
                    pady=3,
                )
                btn.pack(side=RIGHT)
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=c["borda"]))
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg=c["bg_card_escuro"]))

        btn_fechar = self._criar_botao(
            janela, "Fechar", janela.destroy, "", c["bg_card_escuro"], c["borda"], tamanho=10
        )
        btn_fechar.pack(pady=15, padx=20, fill=X)

    def _testar_som_individual(self, caminho):
        """Toca um som individual uma vez."""
        if not os.path.exists(caminho):
            messagebox.showerror("Erro", f"Arquivo não encontrado:\n{caminho}")
            return

        def tocar():
            self.audio.play(caminho, blocking=True)

        threading.Thread(target=tocar, daemon=True).start()

    def _abrir_config(self):
        """Abre o arquivo de configuração no editor padrão."""
        config_path = os.path.abspath(CONFIG_FILE)

        if not os.path.exists(config_path):
            messagebox.showerror(
                "Erro", f"Arquivo de configuração não encontrado:\n{config_path}"
            )
            return

        try:
            sistema = platform.system()
            if sistema == "Windows":
                os.startfile(config_path)
            elif sistema == "Darwin":  # macOS
                subprocess.run(["open", config_path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", config_path], check=True)

            self.label_status.config(
                text="Configuração aberta", fg=self._cores["sucesso"]
            )
            self.root.after(2000, lambda: self._atualizar_status_padrao())
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir o arquivo:\n{str(e)}")

    def _abrir_sobre(self):
        """Abre janela Sobre com informações do sistema."""
        janela = Toplevel(self.root)
        janela.title("Sobre")
        janela.geometry("580x360")
        janela.configure(bg=self._cores["bg_card"])
        janela.resizable(False, False)
        janela.transient(self.root)
        janela.grab_set()

        c = self._cores

        frame_centro = Frame(janela, bg=c["bg_card"])
        frame_centro.pack(fill=BOTH, expand=True, padx=20, pady=20)

        Label(
            frame_centro,
            text="SINO DE IGREJA",
            font=("DejaVu Sans", 18, "bold"),
            fg=c["destaque"],
            bg=c["bg_card"],
        ).pack(pady=(10, 10))

        linhas = [
            f"  Versão:      {__version__}",
            f"  Autor:       {__author__}",
            f"  Email:       {__email__}",
            f"  Repositório: {__repo__}",
            "  Descrição:   Sistema de toques programados para igrejas",
            "  Licença:     MIT License",
        ]

        for linha in linhas:
            Label(
                frame_centro,
                text=linha,
                font=("DejaVu Sans Mono", 10),
                fg=c["texto"],
                bg=c["bg_card"],
                anchor=W,
            ).pack(fill=X, pady=1)

        btn_fechar = self._criar_botao(
            janela, "Fechar", janela.destroy, "", c["bg_card_escuro"], c["borda"], tamanho=10
        )
        btn_fechar.pack(pady=(15, 15), padx=30, fill=X)

    def _atualizar_status_padrao(self):
        """Atualiza o status para o estado padrão baseado em _ativado."""
        if self._ativado:
            self.label_status.config(
                text="Sistema Ativo", fg=self._cores["sucesso_escuro"]
            )
        else:
            self.label_status.config(text="Sistema Inativo", fg=self._cores["inativo"])

    def _formatar_toque(self, toque, index):
        diff_str = formatar_diferenca(toque["diferenca"])
        emoji = "🔔" if index == 0 else "○"
        texto = f"{emoji} {hora_str(toque['hora'], toque['minuto'])}  {toque['som']:<12} ×{toque['repeticoes']}  ({diff_str})"
        return texto

    def _atualizar_toques(self):
        toques = self.manager.obter_proximos_toques(15)
        self.listbox_toques.delete(0, END)
        for i, toque in enumerate(toques):
            texto = self._formatar_toque(toque, i)
            self.listbox_toques.insert(END, texto)
            if i == 0:
                self.listbox_toques.itemconfig(i, fg=self._cores["sucesso"])
            else:
                self.listbox_toques.itemconfig(i, fg=self._cores["texto_secundario"])

    def _animar_indicador(self, ativo):
        """Anima o indicador de status (pisca quando tocando)."""
        if ativo and self.tocando:
            cor_atual = self.indicador.itemcget(self.indicador_id, "fill")
            nova_cor = (
                self._cores["destaque"]
                if cor_atual == self._cores["sucesso"]
                else self._cores["sucesso"]
            )
            self.indicador.itemconfig(self.indicador_id, fill=nova_cor)
            self.root.after(500, lambda: self._animar_indicador(True))
        elif not ativo:
            cor_status = (
                self._cores["sucesso_escuro"]
                if self._ativado
                else self._cores["inativo"]
            )
            self.indicador.itemconfig(self.indicador_id, fill=cor_status)

    def _tocar_sino(self):
        if self.tocando:
            return

        sonidos = self.manager.config.get("sons", {})
        som_key = "sino"
        som_path = sonidos.get(som_key, f"sounds/{som_key}.mp3")

        if not os.path.exists(som_path):
            som_path = f"sounds/{som_key}.mp3"

        if not os.path.exists(som_path):
            self.label_status.config(
                text="Erro: Som não encontrado", fg=self._cores["destaque"]
            )
            return

        self.tocando = True
        self.label_status.config(text="TOCANDO...", fg=self._cores["destaque"])
        self.label_ultimo.config(text="")
        self.indicador.itemconfig(self.indicador_id, fill=self._cores["destaque"])
        self._animar_indicador(True)

        def tocar():
            try:
                for i in range(3):
                    if not self.tocando:
                        break
                    if self.manager.parar_loop:
                        break
                    if not self.audio.play(som_path, blocking=True):
                        break
                    if i < 2 and self.tocando and not self.manager.parar_loop:
                        time.sleep(0.5)
                if self.tocando and not self.manager.parar_loop:
                    self.manager.ultimo_toque = datetime.now()
                    self.root.after(
                        0,
                        lambda: self.label_ultimo.config(
                            text=f"Último toque: {self.manager.ultimo_toque.strftime('%H:%M:%S')}"
                        ),
                    )
            except Exception as e:
                self.root.after(
                    0,
                    lambda: self.label_status.config(
                        text=f"Erro: {e}", fg=self._cores["destaque"]
                    ),
                )
            finally:
                self.tocando = False
                self.root.after(0, lambda: self._finalizar_tocar())

        threading.Thread(target=tocar, daemon=True).start()

    def _finalizar_tocar(self):
        self._atualizar_status_padrao()

    def _parar(self):
        self.tocando = False
        self.audio.stop()
        self.label_status.config(text="Parado", fg=self._cores["texto_secundario"])
        cor_status = (
            self._cores["sucesso_escuro"] if self._ativado else self._cores["inativo"]
        )
        self.indicador.itemconfig(self.indicador_id, fill=cor_status)

    def _recarregar(self):
        self.manager.carregar_config()
        self._atualizar_toques()
        self.label_status.config(
            text="Configuração recarregada", fg=self._cores["sucesso"]
        )
        self.root.after(2000, lambda: self._atualizar_status_padrao())

    def _iniciar_atualizacao(self):
        def atualizar():
            if not self.running:
                return

            agora = datetime.now()
            self.label_relogio.config(text=agora.strftime("%H:%M:%S"))
            self.label_data.config(
                text=agora.strftime("%A, %d de %B de %Y").capitalize()
            )

            if agora.minute != self._ultimo_minuto:
                self._ultimo_minuto = agora.minute
                self._atualizar_toques()
                # Só executa toques automáticos se o sistema estiver ativo
                if self._ativado:
                    threading.Thread(
                        target=self.manager.verificar_e_tocar, daemon=True
                    ).start()

            self.root.after(500, atualizar)

        atualizar()

    def iniciar(self):
        self._atualizar_toques()
        self.root.mainloop()


def main():
    root = Tk()
    app = SinoGUI(root)
    app.iniciar()


if __name__ == "__main__":
    main()

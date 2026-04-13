Sino de Igreja
================

Programa simples em Python para tocar sinos em horários programados (Linux / Raspberry Pi).

Principais pontos
- Configuração em `config.json` (chaves em pt-BR: `sons`, `programacao`, `hora`, `minuto`, `som`, `repeticoes`).
- Interface terminal com `curses` (modo gráfico) ou `--console` para modo texto.
- Reproduz áudio via `pygame` (preferido) ou fallback para `ffplay`, `paplay`, `aplay` ou `omxplayer`.
- Tecla `S` interrompe o toque em andamento (implementação segura que termina apenas os processos iniciados pelo programa).

Instalação
---------

1. Instale dependências (recomendado em venv):

```
pip install -r requirements.txt
```

2. Opcional: instale `ffmpeg`/`pulseaudio`/`omxplayer` se não for usar `pygame`.

Executando
---------

- Modo gráfico (com curses):

```
./sino_igreja.sh
```

ou

```
python3 sino_igreja.py
```

- Modo console:

```
python3 sino_igreja.py --console
```

Controles principais (UI)
- Q: sair
- R: recarregar `config.json`
- T: tocar o som principal (1x)
- S: parar o som/loop em execução
- Espaço: tocar o som principal 3x
- 1-9: tocar um dos próximos toques listados

Configuração
-----------

Exemplo `config.json`:

```
{
  "sons": {
    "sino": "sounds/sino.mp3",
    "nossa_senhora": "sounds/nossa_senhora.mp3"
  },
  "programacao": [
    {"hora": 7, "minuto": 0, "som": "sino", "repeticoes": 7},
    {"hora": 19, "minuto": 0, "som": "nossa_senhora", "repeticoes": 1}
  ]
}
```

Verificações / Debug
- Verificar saída do programa para mensagens de erro sobre áudio ou configuração.
- Para testar `stop()` com players externos, execute um toque longo e pressione `S`, depois confira processos com `ps aux | grep ffplay` (ou equivalente).

Arquivos importantes
- `sino_igreja.py` - código principal
- `config.json` - horários e sons
- `sino_igreja.sh` - lançador para ambiente gráfico
- `howto.html`, `ajuda.html` - documentação em pt-BR

Licença
-------
Recomendado: MIT. Veja o arquivo `LICENSE`.

Próximos passos sugeridos
1) Revisar e ajustar `README.md` com o nome do autor.
2) Validar em Raspberry Pi com HDMI/alto-falante para checar `omxplayer`/ALSA.
3) Opcional: adicionar `systemd` service para inicializar automaticamente.

#!/bin/bash
# Sino de Igreja - Script de inicialização
# Executa em modo gráfico (curses/terminal)

DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$DIR"

# Verifica se está em um terminal
if [ ! -t 0 ]; then
    # Se não está em terminal, abre um novo terminal
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- bash -c "cd '$DIR' && python3 sino_igreja.py; read -p 'Pressione Enter para sair...'"
    elif command -v konsole &> /dev/null; then
        konsole -e bash -c "cd '$DIR' && python3 sino_igreja.py; read -p 'Pressione Enter para sair...'"
    elif command -v xterm &> /dev/null; then
        xterm -e bash -c "cd '$DIR' && python3 sino_igreja.py; read -p 'Pressione Enter para sair...'"
    elif command -v lxterminal &> /dev/null; then
        lxterminal -e bash -c "cd '$DIR' && python3 sino_igreja.py; read -p 'Pressione Enter para sair...'"
    else
        echo "Nenhum terminal gráfico encontrado. Instale: gnome-terminal, konsole, xterm ou lxterminal"
        exit 1
    fi
else
    python3 sino_igreja.py
fi

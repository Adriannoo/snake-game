# Build para Windows

O jogador não precisa de Python. As ferramentas abaixo são usadas apenas para gerar a distribuição.

## Preparar e gerar o EXE

Use Python 3.12 de 64 bits. Na raiz do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe build.py
```

Resultado: `dist/SnakeGame.exe`, contendo Python e Pygame, incluindo a fonte usada pelo jogo.

## Gerar o instalador

Com Inno Setup 6 ou 7 instalado no local padrão ou disponível no PATH:

```powershell
.\.venv\Scripts\python.exe build.py --installer
```

Se o compilador estiver em outra pasta:

```powershell
.\.venv\Scripts\python.exe build.py --installer --iscc "C:\caminho\Inno Setup\ISCC.exe"
```

Resultado: `releases/SnakeGame-Setup.exe`. Instala para o usuário atual, cria atalho no menu Iniciar, oferece atalho na área de trabalho e inclui desinstalador. Novos builds atualizam esse mesmo arquivo.

Os dados ficam em `%LOCALAPPDATA%\AdrianoGames\SnakeGame\profile.json`, separados da instalação, e são preservados pela desinstalação.

## Conferir

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\dist\SnakeGame.exe --check-build "$env:TEMP\snake-check"
```

O diagnóstico não abre janela e usa somente a pasta indicada para capturas e dados. Em `result.json`, `ok` deve ser `true`. Use uma pasta nova em cada conferência.

Distribua o instalador de `releases/` ou o EXE portátil de `dist/`; não distribua `build/` nem `.venv/`.

O alvo verificado é Windows 10/11 de 64 bits. Outros sistemas precisam de builds e verificações próprios.

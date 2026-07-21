<div align="center">
  <img src="assets/icon.png" alt="SSH Tunnel Manager Logo" width="128">
  
  # WL Tech SSH Tunnel Manager

  **Gerenciador de túneis SSH seguro, moderno e open-source para Windows.**

  Versão atual: 2.0.0

  [![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
  [![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-blueviolet.svg)](https://github.com/TomSchimansky/CustomTkinter)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
  
  [Recursos](#recursos) • [Instalação](#instalação) • [Como Usar](#como-usar) • [Compilando](#compilando-do-código-fonte) • [Contribuindo](CONTRIBUTING.md)

</div>

---

## 💡 Sobre

O **wltech SSH Tunnel Manager** é uma interface gráfica (GUI) desenvolvida em Python (usando CustomTkinter) que facilita a criação e manutenção de túneis SSH locais (`Local Port Forwarding`). Ele abstrai a complexidade do terminal e permite que você gerencie múltiplas portas, acompanhe o status da conexão em tempo real e mantenha túneis estáveis com reconexão automática.

Perfeito para acessar dashboards restritos, bancos de dados em servidores remotos ou criar rotas seguras para sistemas como Wazuh, Grafana e Graylog.

## ✨ Recursos

- **Moderna Interface Escura**: UI premium com `CustomTkinter` (suporte nativo a Dark Mode).
- **Gerenciamento Flexível**: Configure o IP do Servidor e a Chave SSH diretamente pela interface gráfica.
- **Port Forwarding Descomplicado**: Adicione, remova e agrupe portas facilmente.
- **Reconexão Automática**: Se a conexão cair, o aplicativo tentará reconectar automaticamente.
- **Logs em Tempo Real**: Console visual na própria tela para depuração imediata.
- **Atualização Segura**: Verifica novas versões no GitHub oficial, exibe as notas e só baixa após sua confirmação.
- **Leve e Portátil**: Pode ser distribuído como um executável `.exe` independente.

## 🚀 Instalação

### Usando o Executável (Pronto para Uso)
1. Vá até a aba [Releases](../../releases) deste repositório.
2. Baixe a última versão do `wltech-tunnel.exe`.
3. Execute o arquivo (não requer instalação!).

> **Nota:** Certifique-se de ter o cliente `ssh` padrão do Windows instalado (já vem nativo no Windows 10/11 ou via Git for Windows).

## 🛠️ Como Usar

1. Ao abrir o app, acesse **Menu → Gerenciar Hosts** no canto superior direito.
2. Defina o Host remoto no formato `usuario@host` ou `usuario@IP`.
3. Opcionalmente, indique o caminho para a sua chave privada SSH (deixe em branco se usar `ssh-agent`).
4. Clique em **EDITAR PORTAS** e configure o encaminhamento (ex: Porta Local: `8443`, Remote Host: `127.0.0.1`, Remote Port: `443`).
5. Clique em **CONECTAR** na tela principal. O status ficará verde e você poderá acessar seus serviços em `localhost`!

## 🔄 Atualizações

O aplicativo verifica automaticamente, em segundo plano, se há uma nova versão publicada. Nenhum arquivo é baixado sem sua autorização. Também é possível usar **Menu → Verificar atualizações**.

Quando uma atualização estiver disponível, a janela mostra as notas da versão, permite ignorar aquele aviso e acompanha o download. Antes da instalação, o executável é validado com o digest SHA-256 informado pelo GitHub. Durante a troca, a versão atual é mantida como backup e restaurada automaticamente se a nova versão não iniciar corretamente.

As atualizações são aceitas exclusivamente da última release publicada em `leosgarcia/tunnel-ssh`, cujo asset deve se chamar exatamente `wltech-tunnel.exe`. A instalação automática está disponível no executável compilado para Windows; ao executar pelo código-fonte, a verificação continua disponível, mas o aplicativo não substitui os arquivos do projeto.

## 💻 Compilando do Código-Fonte

Se quiser compilar o executável por conta própria:

1. Clone o repositório:
   ```bash
   git clone https://github.com/leosgarcia/tunnel-ssh.git
   cd tunnel-ssh
   ```
2. Instale o Python (3.11 ou superior).
3. Execute o script de build:
   ```cmd
   .\build.bat
   ```
   *O script fará a instalação dos pacotes necessários via pip e gerará o executável na pasta `dist/`.*

### Publicando uma versão atualizável

1. Atualize `APP_VERSION` em `src/ui/app.py`.
2. Gere o executável com `build.bat`.
3. Crie uma release pública com a tag no formato `vX.Y.Z`.
4. Escreva as notas da versão no corpo da release.
5. Anexe `dist/wltech-tunnel.exe` com o nome exato `wltech-tunnel.exe`.

Drafts e pré-releases não são retornados pelo endpoint de última release usado pelo aplicativo.

## 🤝 Como Contribuir

Toda ajuda é bem-vinda! Se você achou um bug ou tem uma ideia nova, veja o nosso guia completo em [CONTRIBUTING.md](CONTRIBUTING.md).

---

## ☕ Apoie este projeto

Se esta ferramenta facilitou a sua vida no trabalho ou no dia a dia, considere pagar um café! Seu apoio ajuda muito a manter o desenvolvimento ativo.

<a href="https://buymeacoffee.com/leosgarcia" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" >
</a>

<br>

<p align="center">
  Desenvolvido com 💜 por wltech.
</p>

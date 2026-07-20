# Guia de Contribuição

Ficamos muito felizes que você tenha interesse em contribuir com o **wltech SSH Tunnel Manager**! Nosso objetivo é construir uma ferramenta limpa, segura e amigável. Toda ajuda é bem-vinda, seja corrigindo bugs, adicionando funcionalidades ou melhorando a documentação.

## 🛠 Como posso contribuir?

### 🐛 Reportando Bugs
Se você encontrar um comportamento inesperado, erro de conexão ou falha na interface, abra uma [Issue](https://github.com/leosgarcia/tunnel-ssh/issues) descrevendo o problema.
**Por favor, inclua:**
- Passos para reproduzir o bug.
- Qual sistema operacional você está usando.
- Quaisquer logs de erro que apareçam na tela (oculte IPs ou senhas se houver).

### ✨ Sugerindo Funcionalidades
Queremos ouvir suas ideias! Abra uma [Issue](https://github.com/leosgarcia/tunnel-ssh/issues) detalhando a nova funcionalidade, por que ela seria útil e como ela deveria funcionar na interface (se aplicável).

### 💻 Contribuindo com Código

Se você quer colocar a mão na massa, siga estes passos:

1. **Faça um Fork do repositório** e crie uma branch para a sua feature ou correção:
   ```bash
   git checkout -b feature/minha-nova-feature
   # ou
   git checkout -b fix/correcao-bug
   ```

2. **Configure o Ambiente de Desenvolvimento:**
   Recomendamos usar um ambiente virtual (`venv`).
   ```bash
   python -m venv venv
   # No Windows:
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Padrão de Código:**
   - O projeto utiliza Python (tipado via Type Hints) e `CustomTkinter` para UI.
   - Siga as diretrizes do **PEP 8** para estilização e clareza.
   - Se for criar novos módulos, mantenha o escopo isolado dentro da pasta `src/`.

4. **Teste suas Alterações:**
   - Para testar localmente basta rodar:
     ```bash
     python -m src.main
     ```
   - Certifique-se de que a build continua funcional executando o `build.bat` antes de enviar.

5. **Faça um Commit e Envie um Pull Request:**
   Escreva mensagens de commit claras e objetivas.
   ```bash
   git commit -m "feat: Adiciona botão para exportar logs de túnel"
   git push origin feature/minha-nova-feature
   ```
   Abra um Pull Request e nós revisaremos o mais rápido possível!

---

## ☕ Faça parte da comunidade

O projeto cresce com o esforço de desenvolvedores apaixonados. Se quiser apoiar nosso trabalho além do código, considere dar uma estrela no repositório no GitHub ou [pagar um café](https://www.buymeacoffee.com/leosg)!

Obrigado por contribuir! 🚀

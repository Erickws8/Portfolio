# Explorador AWS S3 — instalação, utilização e compilação

Aplicação desktop Python/Tkinter para navegar em **buckets Amazon S3 privados**, baixar arquivos e diretórios e gerar **links pré-assinados para download**. A interface possui layout responsivo e rolagem vertical.

> Este README corresponde ao script `explorador_s3.py` (com logo externo `logo.ico`). Os builds para Windows e Linux precisam ser feitos **separadamente em cada sistema operacional**.

## 1. Arquivos necessários

### Durante o desenvolvimento

```text
s3_navigator/
├── explorador_s3.py   # Código-fonte
├── logo.ico                              # Logo exibida na interface
├── config.ini                            # Opcional: configurações AWS
└── .venv/                                # Criada durante a instalação
```

### Após a compilação

**Windows**
```text
S3_Navigator/
├── explorador_s3_privado.exe
├── logo.ico
└── config.ini                            # Opcional
```

**Linux**
```text
S3_Navigator/
├── explorador_s3_privado
├── logo.ico
└── config.ini                            # Opcional
```

- `logo.ico` é **lido diretamente da pasta do executável**, sem consultar `config.ini`. O Pillow é necessário para exibi-lo na interface.
- `config.ini` é opcional. A aplicação lê o arquivo na inicialização, se existir, **na mesma pasta do `.py` ou `.exe`**. Alterações no INI exigem reiniciar a aplicação.
- `logo.ico` é usado como ícone de janela no Windows; no Linux, o script exibe a imagem no cabeçalho, mas não configura o ícone da janela pelo `iconbitmap`.
- O arquivo `.ico` pode ser incorporado como **ícone do executável Windows** pelo PyInstaller, mas o arquivo externo continua necessário para exibir a logo dentro da aplicação.

## 2. Dependências

| Componente | Uso | Instalação |
|---|---|---|
| Python 3 | Interpretador | Instalador Python / gerenciador de pacotes |
| `boto3` | Cliente AWS S3 | `pip install boto3` |
| `botocore` | Dependência do boto3 | Instalada com boto3 |
| `s3transfer` | Transferência S3 | Instalada com boto3 |
| `Pillow` (`PIL`) | Exibir `logo.ico` na interface | `pip install pillow` |
| `tkinter` | Interface gráfica | Integrado ao Python no Windows; pacote `python3-tk` no Ubuntu |
| `configparser`, `pathlib`, `queue`, `threading`, `sys`, `os` | Bibliotecas padrão | Já vêm com Python |
| `pyarmor` | Ofuscação e expiração | `pip install pyarmor` |
| `pyinstaller` | Empacotamento executável | `pip install pyinstaller` |

**PyArmor e PyInstaller são necessários apenas para gerar o executável, não para o usuário final.** O sistema de destino ainda precisa das bibliotecas nativas e do ambiente gráfico compatíveis.

### Windows (PowerShell)

```powershell
cd "C:\Users\Erick\Desktop\s3_navigator"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install boto3 pillow pyarmor pyinstaller
python -m tkinter
```

Se o PowerShell bloquear a ativação do ambiente, use os executáveis diretamente em `.venv\Scripts\` ou ajuste a política de execução conforme as regras de segurança da sua organização.

### Ubuntu/Debian (terminal)

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-tk
mkdir -p ~/s3_navigator
cd ~/s3_navigator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install boto3 pillow pyarmor pyinstaller
python -m tkinter
```

Para abrir a interface no Linux, é necessário um **ambiente gráfico** (X11 ou Wayland). Um servidor sem desktop não é suficiente para utilizar o Tkinter normalmente.

## 3. Configuração AWS (`config.ini`)

Crie este arquivo ao lado do script ou do executável, **se desejar carregar valores automaticamente**:

```ini
[AWS]
bucket = meu-bucket-privado
region = sa-east-1

; Opção A: credenciais explícitas (evite armazenar segredos em texto puro)
aws_access_key_id =
aws_secret_access_key =
aws_session_token =

; Opção B: perfil AWS CLI, quando não houver chaves explícitas
profile =
```

**Não é necessário adicionar `[APLICATIVO]` nem `logo = ...`: a logo é sempre `logo.ico` ao lado do programa.**

O código reconhece também nomes alternativos no INI:
- Região: `region` ou `regiao`.
- Access Key: `aws_access_key_id`, `access_key_id` ou `access_key`.
- Secret Key: `aws_secret_access_key`, `secret_access_key` ou `secret_key`.
- Token: `aws_session_token`, `session_token` ou `access_token`.
- Perfil: `profile` ou `perfil`.

### Formas de credenciamento

**A. Campos da interface**

Preencha Bucket, Região AWS, Access Key ID e Secret Access Key; informe Session Token caso use credenciais temporárias. Clique em **CONECTAR AO BUCKET**.

**B. Arquivo `config.ini`**

Se os campos de chaves da interface estiverem vazios, a aplicação consulta as chaves correspondentes no `config.ini`. O bucket e a região também podem ser inicializados pelo INI.

**C. Perfil AWS CLI**

Configure um perfil no computador:

```bash
aws configure --profile s3-navigator
```

Informe `s3-navigator` no campo **Perfil AWS (alternativo)** ou no `profile` do INI. Para usar perfil, **não mantenha chaves explícitas preenchidas no INI ou na interface**, pois elas têm prioridade. O AWS CLI é opcional e só é necessário para facilitar a configuração de perfis por esse comando; o boto3 também pode usar perfis já existentes.

**D. Cadeia padrão de credenciais do Boto3**

Sem chaves explícitas e sem perfil informado, o boto3 utiliza sua cadeia padrão de credenciais, que pode incluir variáveis de ambiente, perfil padrão e credenciais de função IAM conforme o ambiente.

Exemplo com variáveis de ambiente no PowerShell:

```powershell
$env:AWS_ACCESS_KEY_ID = "SUA_CHAVE"
$env:AWS_SECRET_ACCESS_KEY = "SEU_SEGREDO"
# Para credenciais temporárias:
$env:AWS_SESSION_TOKEN = "SEU_TOKEN"
```

Exemplo no Linux:

```bash
export AWS_ACCESS_KEY_ID="SUA_CHAVE"
export AWS_SECRET_ACCESS_KEY="SEU_SEGREDO"
# Para credenciais temporárias:
export AWS_SESSION_TOKEN="SEU_TOKEN"
```

**Prioridade efetiva do script:** valores individuais digitados na interface → valores correspondentes no INI → perfil indicado → cadeia padrão do boto3. Se houver apenas uma das duas chaves, a conexão será recusada; o perfil é ignorado quando há um par de chaves explícitas.

**Segurança:** prefira perfis/credenciais temporárias e permissões IAM mínimas. Um `config.ini` com chaves fica em **texto puro**, mesmo que o `.exe` tenha sido protegido pelo PyArmor. Nunca envie credenciais para repositórios públicos.

### Permissões AWS necessárias

A identidade AWS precisa, conforme o uso:
- `s3:ListBucket` para navegar/listar objetos do bucket.
- `s3:GetObject` para baixar arquivos e para que URLs pré-assinadas de leitura funcionem.
- Permissões adicionais de KMS, como `kms:Decrypt`, podem ser necessárias para objetos criptografados com SSE-KMS.

A política IAM e a política do bucket também podem restringir prefixos, redes, duração e acesso.

## 4. Como usar a aplicação

1. Execute o programa e confira a logo no cabeçalho.
2. Informe o bucket e a região; escolha uma forma de autenticação.
3. Clique em **CONECTAR AO BUCKET**.
4. Navegue pelas pastas com duplo clique; use **Voltar** e **Atualizar** quando necessário.
5. Para baixar, selecione arquivos e/ou pastas, abra a aba **Download**, escolha a pasta de destino e clique em **BAIXAR SELECIONADOS**. Confirme a operação.
6. Para gerar um link, selecione **exatamente um arquivo**, abra **Link assinado**, informe a validade de **1 a 10080 minutos** (até 7 dias), clique em **GERAR LINK ASSINADO** e depois em **Copiar link**.

**Atenção:** arquivos já existentes no destino com o mesmo nome podem ser substituídos no download. O link assinado dá acesso temporário ao objeto: trate-o como informação sensível. A validade real pode ser menor que a solicitada, por exemplo se a credencial temporária expirar antes.

A interface é responsiva, com rearranjo dos campos e rolagem em janelas menores; tamanho mínimo configurado: **580 × 440 pixels**.

## 5. Executar sem compilar

Windows:

```powershell
python .\explorador_s3.py
```

Linux:

```bash
python explorador_s3.py
```

## 6. Compilar com proteção e expiração — Windows

> Execute na pasta do projeto, com o ambiente virtual ativado. Exemplo de expiração: **31/12/2026**. Escolha uma data futura adequada.

### 6.1 Proteger com PyArmor

```powershell
pyarmor gen -O protegido -e 2026-12-31 explorador_s3.py
```

Teste o código protegido:

```powershell
python .\protegido\explorador_s3.py
```

### 6.2 Empacotar com PyInstaller

```powershell
pyinstaller --onefile --windowed --clean --noconfirm --icon "logo.ico" --name "explorador_s3_privado" --paths ".\protegido" --hidden-import configparser --collect-submodules tkinter --collect-all PIL --collect-all boto3 --collect-all botocore --collect-all s3transfer ".\protegido\explorador_s3.py"
```

Resultado: `dist\explorador_s3_privado.exe`.

Copie `logo.ico` e, se utilizado, `config.ini` para a pasta `dist` junto ao `.exe`.

### 6.3 Compilar sem ofuscação (para diagnóstico)

```powershell
pyinstaller --onefile --windowed --clean --noconfirm --icon "logo.ico" --name "explorador_s3_privado" explorador_s3.py
```

O build sem PyArmor ajuda a identificar dependências antes de ofuscar. **Não distribua esse build como versão protegida.**

## 7. Compilar com proteção e expiração — Linux

Copie o **arquivo-fonte original** para o Linux. **Não reutilize o diretório `protegido` gerado no Windows**: o runtime protegido é específico da plataforma.

### 7.1 Proteger

```bash
cd ~/s3_navigator
source .venv/bin/activate
pyarmor gen -O protegido -e 2026-12-31 explorador_s3.py
python ./protegido/explorador_s3.py
```

### 7.2 Empacotar

```bash
pyinstaller \
  --onefile \
  --windowed \
  --clean \
  --noconfirm \
  --name "explorador_s3_privado" \
  --paths "./protegido" \
  --hidden-import configparser \
  --collect-submodules tkinter \
  --collect-all PIL \
  --collect-all boto3 \
  --collect-all botocore \
  --collect-all s3transfer \
  "./protegido/explorador_s3.py"
```

Resultado: `dist/explorador_s3_privado` (sem extensão `.exe`).

```bash
cp logo.ico dist/
# Se você utiliza config.ini:
cp config.ini dist/
chmod +x dist/explorador_s3_privado
./dist/explorador_s3_privado
```

O ícone `.ico` não é aplicado ao arquivo executável Linux pelo argumento `--icon` do Windows. Para integração ao menu do Linux, pode-se criar um arquivo `.desktop` e um ícone PNG separadamente.

**Compatibilidade:** compile na mesma arquitetura (ex.: x86_64) e, preferencialmente, em uma distribuição com `glibc` tão antiga quanto a versão mínima que você deseja suportar. Um binário Linux não é universal para todas as distribuições.

## 8. PyArmor: licença, validade e limitações

- `-e 2026-12-31` configura a data de expiração do código protegido.
- O runtime do PyArmor deve ser incluído no executável; o PyInstaller normalmente o detecta pelo import presente no arquivo ofuscado.
- As limitações de **PyArmor Trial** e os direitos de distribuição dependem da licença e versão instalada. Confira a documentação/licença antes de distribuir comercialmente.
- A ofuscação **dificulta**, mas não impossibilita, engenharia reversa.
- A proteção por expiração não equivale a um servidor de licenças. Para reduzir a manipulação do relógio local, avalie uma verificação confiável de tempo/licença conforme os recursos suportados pela sua versão.
- Se alterar o código-fonte, execute **novamente** o PyArmor antes de gerar o executável.

## 9. Diagnóstico de erros comuns

| Problema | Possível causa e correção |
|---|---|
| `No module named 'configparser'` | Recompile com `--hidden-import configparser`. |
| `cannot import name 'filedialog' from 'tkinter'` | Use `--collect-submodules tkinter`. |
| `No module named 'PIL'` | Instale `pillow` e use `--collect-all PIL`. |
| Logo não aparece | Verifique `logo.ico` **ao lado do executável**, e não apenas no diretório de desenvolvimento. |
| O ícone do `.exe` não muda | Confirme `--icon "logo.ico"` no Windows e considere o cache de ícones do Explorador. |
| Terminal abre no Windows | Compile com `--windowed` e execute o `.exe` gerado no último build. |
| `AccessDenied` no S3 | Verifique IAM, política do bucket, nome/região e permissões para o prefixo/objeto. |
| `NoCredentialsError` | Preencha as chaves, configure um perfil ou a cadeia padrão de credenciais. |
| Link assinado não funciona | Verifique `s3:GetObject`, expiração da credencial, política do bucket e tempo de validade. |
| Interface não abre no Linux | Verifique instalação do Tkinter e sessão gráfica disponível. |
| Executável Linux não roda em outra máquina | Verifique arquitetura, `glibc` e bibliotecas nativas. |

Para diagnosticar erros que desaparecem quando o programa é aberto sem console, gere temporariamente um build **sem `--windowed`** e execute-o pelo terminal para ler o traceback.

## 10. Checklist de distribuição

- [ ] O script executa sem erros no sistema de build.
- [ ] O código protegido executa sem erros.
- [ ] O executável final abre a interface.
- [ ] A logo externa é exibida corretamente.
- [ ] A autenticação AWS funciona com a forma escolhida.
- [ ] A listagem, navegação e download funcionam.
- [ ] A geração e abertura do link pré-assinado funcionam.
- [ ] A responsividade foi testada com a janela pequena.
- [ ] `config.ini` não contém segredos desnecessários.
- [ ] A data de expiração e a licença PyArmor foram verificadas.
- [ ] O executável foi testado em um computador de destino sem Python instalado.

---

**Referências:** [Boto3 Credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html) · [Boto3 Presigned URLs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html) · [PyInstaller](https://pyinstaller.org/en/stable/) · [PyArmor](https://pyarmor.readthedocs.io/en/latest/)

"""Explorador S3 autenticado com downloads e links pré-assinados.
Instale: pip install boto3 pillow
Execute: python explorador_s3_privado.py
A logo é carregada de logo.ico ao lado do executável; o config.ini configura apenas a AWS.
"""
import os
import configparser
import queue
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, ProfileNotFound, PartialCredentialsError

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

# Altere estas cores para combinar com a sua marca.
CORES = {
    'fundo': '#F1F5F9', 'branco': '#FFFFFF', 'marinho': '#142D4E',
    'marinho_claro': '#203D63', 'azul': '#1674D1', 'azul_hover': '#0D5DAF',
    'verde': '#15803D', 'texto': '#233247', 'secundario': '#64748B',
    'borda': '#DCE5EF', 'cinza_claro': '#EAF0F6', 'vermelho': '#B91C1C'
}


def pasta_aplicativo():
    # Pasta do .exe quando empacotado, não a pasta temporária do PyInstaller.
    return Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent


def carregar_configuracao():
    """Carrega INI ao lado do .py/.exe. Não cria nem modifica o arquivo."""
    caminho = pasta_aplicativo() / 'config.ini'
    config = configparser.ConfigParser(interpolation=None)
    if caminho.is_file():
        with caminho.open('r', encoding='utf-8-sig') as arquivo:
            config.read_file(arquivo)
    return config


def config_valor(config, secao, *nomes):
    if not config.has_section(secao):
        return ''
    for nome in nomes:
        valor = config.get(secao, nome, fallback='').strip()
        if valor:
            return valor
    return ''


def caminho_logo():
    """Logo externa ao lado do .exe (ou do .py durante o desenvolvimento)."""
    return pasta_aplicativo() / 'logo.ico'


class ExploradorS3(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Explorador Amazon S3 | Gerenciador de Downloads')
        self.geometry('1080x760')
        self.minsize(580, 440)
        self.configure(bg=CORES['fundo'])
        self.eventos = queue.Queue()
        self.cliente = None
        self.bucket = ''
        self.prefixo = ''
        self.itens = {}
        self.ocupado = False
        self.logo_imagem = None
        self.logo_caminho = ''
        try:
            self.config_ini = carregar_configuracao()
            self.erro_ini = ''
        except (OSError, configparser.Error, UnicodeError) as erro:
            self.config_ini = configparser.ConfigParser(interpolation=None)
            self.erro_ini = str(erro)
        self._estilos()
        self._interface()
        logo = caminho_logo()
        if logo.is_file():
            try:
                self._carregar_logo(logo)
                # O ícone da janela também utiliza o arquivo externo.
                if sys.platform == 'win32':
                    self.iconbitmap(default=str(logo))
            except (OSError, ValueError, tk.TclError) as erro:
                self.status_var.set(f'Não foi possível carregar logo.ico: {erro}')
        else:
            self.status_var.set(f'Logo não encontrada: {logo}')
        if self.erro_ini:
            self.after(150, lambda: messagebox.showwarning('config.ini',
                       f'Não foi possível ler o config.ini:\n{self.erro_ini}'))
        self.after(100, self._processar_eventos)

    def _estilos(self):
        estilo = ttk.Style(self)
        estilo.theme_use('clam')
        estilo.configure('Arvore.Treeview', background='white', fieldbackground='white',
                         foreground=CORES['texto'], rowheight=30, borderwidth=0, font=('Segoe UI', 10))
        estilo.configure('Arvore.Treeview.Heading', background=CORES['cinza_claro'],
                         foreground=CORES['marinho'], font=('Segoe UI', 10, 'bold'), padding=8)
        estilo.map('Arvore.Treeview', background=[('selected', '#CDE6FF')],
                   foreground=[('selected', CORES['marinho'])])
        estilo.configure('Azul.Horizontal.TProgressbar', troughcolor=CORES['cinza_claro'],
                         background=CORES['azul'], bordercolor=CORES['cinza_claro'], thickness=17)

    def _rotulo(self, pai, texto, **kwargs):
        return tk.Label(pai, text=texto, bg=kwargs.pop('bg', CORES['branco']),
                        fg=kwargs.pop('fg', CORES['texto']), font=kwargs.pop('font', ('Segoe UI', 10)), **kwargs)

    def _botao(self, pai, texto, comando, cor=None, fg='white'):
        cor = cor or CORES['azul']
        return tk.Button(pai, text=texto, command=comando, bg=cor, fg=fg,
                         activebackground=CORES['marinho_claro'], activeforeground='white',
                         relief='flat', cursor='hand2', font=('Segoe UI', 10, 'bold'),
                         padx=13, pady=8, disabledforeground='#B8C1CC')

    def _campo(self, pai, variavel, secreto=False):
        return tk.Entry(pai, textvariable=variavel, show='•' if secreto else '',
                        bg='white', fg=CORES['texto'], insertbackground=CORES['texto'],
                        relief='solid', bd=1, highlightthickness=1,
                        highlightbackground=CORES['borda'], highlightcolor=CORES['azul'],
                        font=('Segoe UI', 10))

    def _interface(self):
        # Cabeçalho compacto, conteúdo rolável e campos que mudam de coluna
        # automaticamente conforme a largura da janela.
        topo = tk.Frame(self, bg=CORES['marinho'])
        topo.pack(fill='x')
        self.quadro_logo = tk.Frame(topo, bg='white', width=84, height=72)
        self.quadro_logo.pack(side='left', padx=(12, 12), pady=9)
        self.quadro_logo.pack_propagate(False)
        self.logo_label = tk.Label(self.quadro_logo, text='SUA\\nLOGO', bg='white',
                                   fg=CORES['secundario'], font=('Segoe UI', 10, 'bold'))
        self.logo_label.pack(fill='both', expand=True)
        titulos = tk.Frame(topo, bg=CORES['marinho'])
        titulos.pack(side='left', fill='both', expand=True, pady=12)
        self._rotulo(titulos, 'EXPLORADOR AMAZON S3', bg=CORES['marinho'],
                     fg='white', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        self._rotulo(titulos, 'Navegação, downloads e links assinados',
                     bg=CORES['marinho'], fg='#D7E7F6',
                     font=('Segoe UI', 9)).pack(anchor='w')

        area = tk.Frame(self, bg=CORES['fundo'])
        area.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(area, bg=CORES['fundo'], highlightthickness=0)
        scroll = ttk.Scrollbar(area, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        corpo = tk.Frame(self.canvas, bg=CORES['fundo'], padx=12, pady=10)
        self.janela_canvas = self.canvas.create_window((0, 0), window=corpo, anchor='nw')
        corpo.bind('<Configure>', self._atualizar_rolagem)
        self.canvas.bind('<Configure>', self._redimensionar_canvas)
        self.canvas.bind('<MouseWheel>', self._rolar_canvas)
        corpo.bind('<MouseWheel>', self._rolar_canvas)

        conexao = tk.LabelFrame(corpo, text='  CONEXÃO COM A AWS  ', bg='white',
                                fg=CORES['marinho'], font=('Segoe UI', 10, 'bold'),
                                padx=10, pady=7)
        conexao.pack(fill='x')
        self.bucket_var = tk.StringVar(value=config_valor(self.config_ini, 'AWS', 'bucket'))
        self.regiao_var = tk.StringVar(value=config_valor(self.config_ini, 'AWS', 'region', 'regiao') or 'sa-east-1')
        self.access_var = tk.StringVar()
        self.secret_var = tk.StringVar()
        self.token_var = tk.StringVar()
        self.perfil_var = tk.StringVar()
        self.campos_conexao = []
        for titulo, variavel, secreto in (
            ('Bucket', self.bucket_var, False),
            ('Região AWS', self.regiao_var, False),
            ('Access Key ID', self.access_var, False),
            ('Secret Access Key', self.secret_var, True),
            ('Session Token (opcional)', self.token_var, True),
            ('Perfil AWS (alternativo)', self.perfil_var, False),
        ):
            rotulo = self._rotulo(conexao, titulo)
            entrada = self._campo(conexao, variavel, secreto)
            self.campos_conexao.append((rotulo, entrada))
        self.conexao_frame = conexao
        self.rodape_conexao = tk.Frame(conexao, bg='white')
        self.botao_conectar = self._botao(self.rodape_conexao, 'CONECTAR AO BUCKET', self.conectar)
        self.botao_conectar.pack(side='left', padx=(0, 10))
        self.conexao_var = tk.StringVar(value='● Desconectado')
        self.indicador = self._rotulo(self.rodape_conexao, '', fg=CORES['vermelho'],
                                     textvariable=self.conexao_var)
        self.indicador.pack(side='left')
        self.ajuda_conexao = self._rotulo(
            conexao, 'Campos vazios: config.ini → perfil AWS → credenciais padrão.',
            fg=CORES['secundario'], font=('Segoe UI', 9), anchor='w')
        self._layout_conexao(2)

        barra = tk.Frame(corpo, bg=CORES['fundo'])
        barra.pack(fill='x', pady=(9, 6))
        self.botao_voltar = self._botao(barra, '↑ Voltar', self.voltar, cor=CORES['marinho_claro'])
        self.botao_voltar.pack(side='left', padx=(0, 6))
        self.botao_atualizar = self._botao(barra, '↻ Atualizar', self.atualizar, cor=CORES['marinho_claro'])
        self.botao_atualizar.pack(side='left')
        self.caminho_var = tk.StringVar(value='Conecte-se para visualizar os arquivos.')
        caminho = self._rotulo(corpo, '', bg=CORES['fundo'], fg=CORES['marinho'],
                              font=('Segoe UI', 9, 'bold'), textvariable=self.caminho_var,
                              anchor='w')
        caminho.pack(fill='x', pady=(0, 5))

        tabela = tk.Frame(corpo, bg='white', highlightbackground=CORES['borda'],
                          highlightthickness=1)
        tabela.pack(fill='both', expand=True)
        self.arvore = ttk.Treeview(tabela, columns=('tipo', 'tamanho', 'data'),
                                   show='tree headings', selectmode='extended',
                                   style='Arvore.Treeview', height=10)
        for coluna, titulo in (('#0', 'Nome'), ('tipo', 'Tipo'),
                               ('tamanho', 'Tamanho'), ('data', 'Última modificação')):
            self.arvore.heading(coluna, text=titulo)
        self.arvore.column('#0', width=290, minwidth=130, stretch=True)
        self.arvore.column('tipo', width=80, minwidth=65, anchor='center', stretch=False)
        self.arvore.column('tamanho', width=95, minwidth=75, anchor='e', stretch=False)
        self.arvore.column('data', width=145, minwidth=120, anchor='center', stretch=False)
        scroll_y = ttk.Scrollbar(tabela, orient='vertical', command=self.arvore.yview)
        scroll_x = ttk.Scrollbar(tabela, orient='horizontal', command=self.arvore.xview)
        self.arvore.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tabela.grid_rowconfigure(0, weight=1)
        tabela.grid_columnconfigure(0, weight=1)
        self.arvore.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')
        self.arvore.bind('<Double-1>', self.abrir_pasta)

        # Abas evitam que download e link assinado disputem espaço vertical.
        abas = ttk.Notebook(corpo)
        abas.pack(fill='x', pady=(9, 0))
        download = tk.Frame(abas, bg='white', padx=10, pady=10)
        assinatura = tk.Frame(abas, bg='white', padx=10, pady=10)
        abas.add(download, text='  Download  ')
        abas.add(assinatura, text='  Link assinado  ')

        self.destino_var = tk.StringVar(value=str(Path.home() / 'Downloads'))
        self._rotulo(download, 'Salvar em:').grid(row=0, column=0, sticky='w')
        self._campo(download, self.destino_var).grid(
            row=1, column=0, columnspan=2, sticky='ew', ipady=5, pady=(3, 7))
        self._botao(download, 'Escolher pasta', self.escolher_destino,
                    cor=CORES['marinho_claro']).grid(row=2, column=0, sticky='w')
        self.botao_baixar = self._botao(download, '↓ BAIXAR SELECIONADOS', self.baixar,
                                       cor=CORES['verde'])
        self.botao_baixar.grid(row=2, column=1, sticky='e')
        download.columnconfigure(0, weight=1)
        download.columnconfigure(1, weight=1)
        self.progresso = ttk.Progressbar(download, style='Azul.Horizontal.TProgressbar', maximum=100)
        self.progresso.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(9, 5))
        self.status_var = tk.StringVar(value='Pronto. Selecione arquivos ou pastas para baixar.')
        self._rotulo(download, '', textvariable=self.status_var, fg=CORES['secundario'],
                     anchor='w').grid(row=4, column=0, columnspan=2, sticky='ew')

        self.minutos_var = tk.StringVar(value='60')
        self.link_var = tk.StringVar()
        self._rotulo(assinatura, 'Validade (minutos):').grid(row=0, column=0, sticky='w')
        campo_minutos = self._campo(assinatura, self.minutos_var)
        campo_minutos.configure(width=9)
        campo_minutos.grid(row=0, column=1, sticky='w', padx=(8, 0), ipady=5)
        self.botao_assinar = self._botao(assinatura, 'GERAR LINK ASSINADO', self.gerar_link)
        self.botao_assinar.grid(row=1, column=0, columnspan=2, sticky='w', pady=(7, 6))
        self._rotulo(assinatura, 'Link gerado:').grid(row=2, column=0, sticky='w')
        self._campo(assinatura, self.link_var).grid(
            row=3, column=0, columnspan=2, sticky='ew', pady=(4, 7), ipady=5)
        self._botao(assinatura, 'Copiar link', self.copiar_link,
                    cor=CORES['marinho_claro']).grid(row=4, column=0, sticky='w')
        assinatura.columnconfigure(0, weight=1)
        self.arvore.bind('<<TreeviewSelect>>', lambda _evento: self.link_var.set(''))
        self._definir_ocupado(False)
        self.bind('<Configure>', self._ajustar_responsividade)

    def _layout_conexao(self, colunas):
        for widget in self.conexao_frame.grid_slaves():
            widget.grid_forget()
        for coluna in range(4):
            self.conexao_frame.columnconfigure(coluna, weight=0)
        if colunas == 2:
            self.conexao_frame.columnconfigure(1, weight=1)
            self.conexao_frame.columnconfigure(3, weight=1)
        else:
            self.conexao_frame.columnconfigure(1, weight=1)
        for indice, (rotulo, entrada) in enumerate(self.campos_conexao):
            linha, grupo = divmod(indice, colunas)
            rotulo.grid(row=linha, column=grupo*2, sticky='w', padx=(3, 6), pady=4)
            entrada.grid(row=linha, column=grupo*2+1, sticky='ew',
                         padx=(0, 10), pady=4, ipady=4)
        linha_final = (len(self.campos_conexao) + colunas - 1) // colunas
        self.rodape_conexao.grid(row=linha_final, column=0, columnspan=colunas*2,
                                sticky='w', pady=(7, 0))
        self.ajuda_conexao.grid(row=linha_final+1, column=0, columnspan=colunas*2,
                               sticky='w', pady=(5, 0))

    def _ajustar_responsividade(self, evento):
        if evento.widget is not self:
            return
        colunas = 1 if evento.width < 880 else 2
        if getattr(self, '_colunas_atuais', None) != colunas:
            self._colunas_atuais = colunas
            self._layout_conexao(colunas)

    def _atualizar_rolagem(self, _evento=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _redimensionar_canvas(self, evento):
        self.canvas.itemconfigure(self.janela_canvas, width=evento.width)
        self._atualizar_rolagem()

    def _rolar_canvas(self, evento):
        self.canvas.yview_scroll(-1 if evento.delta > 0 else 1, 'units')

    def gerar_link(self):
        if self.ocupado or not self.cliente:
            messagebox.showwarning('Conexão', 'Conecte-se a um bucket antes de gerar o link.')
            return
        selecionados = self.arvore.selection()
        if len(selecionados) != 1:
            messagebox.showwarning('Seleção', 'Selecione exatamente um arquivo para gerar o link.')
            return
        item = self.itens.get(selecionados[0])
        if not item or item['tipo'] != 'Arquivo':
            messagebox.showwarning('Seleção', 'Links assinados só podem ser gerados para arquivos.')
            return
        try:
            minutos = int(self.minutos_var.get().strip())
        except ValueError:
            messagebox.showwarning('Validade', 'Informe um número inteiro de minutos.')
            return
        if not 1 <= minutos <= 10080:
            messagebox.showwarning('Validade', 'Informe de 1 a 10080 minutos (até 7 dias).')
            return
        try:
            url = self.cliente.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': self.bucket, 'Key': item['key']},
                ExpiresIn=minutos * 60,
                HttpMethod='GET'
            )
            if not url:
                raise ValueError('A AWS não retornou uma URL.')
            self.link_var.set(url)
            self.status_var.set(f'Link gerado para {item["nome"]} com validade de {minutos} minuto(s).')
        except Exception as erro:
            self.link_var.set('')
            messagebox.showerror('Link assinado', self._mensagem_erro(erro))

    def copiar_link(self):
        url = self.link_var.get().strip()
        if not url:
            messagebox.showinfo('Link', 'Gere um link antes de copiar.')
            return
        self.clipboard_clear()
        self.clipboard_append(url)
        self.update_idletasks()
        self.status_var.set('Link assinado copiado para a área de transferência.')

    def _carregar_logo(self, caminho):
        if Image is not None:
            with Image.open(caminho) as original:
                figura = original.convert('RGBA')
                figura.thumbnail((96, 82), Image.Resampling.LANCZOS)
                self.logo_imagem = ImageTk.PhotoImage(figura)
        else:
            if caminho.suffix.lower() not in ('.png', '.gif'):
                raise ValueError('Para carregar logo.ico instale Pillow: pip install pillow')
            self.logo_imagem = tk.PhotoImage(file=str(caminho))
            fator = max(1, (self.logo_imagem.width() + 95) // 96,
                        (self.logo_imagem.height() + 81) // 82)
            self.logo_imagem = self.logo_imagem.subsample(fator, fator)
        self.logo_caminho = str(caminho)
        self.logo_label.configure(image=self.logo_imagem, text='')

    def _definir_ocupado(self, ocupado):
        self.ocupado = ocupado
        estado = 'disabled' if ocupado else 'normal'
        for botao in (self.botao_conectar, self.botao_atualizar, self.botao_voltar, self.botao_baixar, self.botao_assinar):
            botao.configure(state=estado)

    def _iniciar_tarefa(self, funcao, *args):
        threading.Thread(target=funcao, args=args, daemon=True).start()

    def conectar(self):
        if self.ocupado:
            return
        bucket = self.bucket_var.get().strip()
        regiao = self.regiao_var.get().strip()
        # Prioridade das credenciais:
        # campo preenchido > config.ini > perfil AWS > cadeia padrão do Boto3.
        # Os valores do INI não são copiados para os campos de senha da interface.
        access = self.access_var.get().strip() or config_valor(
            self.config_ini, 'AWS', 'aws_access_key_id', 'access_key_id', 'access_key')
        secret = self.secret_var.get().strip() or config_valor(
            self.config_ini, 'AWS', 'aws_secret_access_key', 'secret_access_key', 'secret_key')
        token = self.token_var.get().strip() or config_valor(
            self.config_ini, 'AWS', 'aws_session_token', 'session_token', 'access_token')
        perfil = self.perfil_var.get().strip() or config_valor(
            self.config_ini, 'AWS', 'profile', 'perfil')
        # O token só faz sentido junto de chaves explícitas. Um token isolado
        # no INI não deve impedir o uso de um perfil AWS.
        if not access and not secret and not self.token_var.get().strip():
            token = '' 
        if not bucket:
            messagebox.showwarning('Bucket', 'Informe o nome do bucket S3.')
            return
        if bool(access) != bool(secret):
            messagebox.showwarning('Credenciais', 'Preencha Access Key ID e Secret Access Key juntas.')
            return
        if token and not access:
            messagebox.showwarning('Credenciais', 'Session Token exige Access Key e Secret Access Key.')
            return
        # Chaves explícitas têm prioridade sobre um perfil definido no INI.
        # Um perfil digitado não substitui um par de chaves do INI: para
        # usar só o perfil, retire/comente as chaves do arquivo INI.
        if access:
            perfil = ''
        # Descarta qualquer conexão anterior enquanto testa as novas credenciais.
        self.cliente = None
        self.itens.clear()
        self.arvore.delete(*self.arvore.get_children())
        self.conexao_var.set('● Conectando...')
        self.indicador.configure(fg=CORES['azul'])
        self._definir_ocupado(True)
        self.status_var.set('Autenticando e listando diretórios...')
        self._iniciar_tarefa(self._conectar_worker, bucket, regiao, access, secret, token, perfil)

    def _conectar_worker(self, bucket, regiao, access, secret, token, perfil):
        try:
            opcoes = {}
            if regiao:
                opcoes['region_name'] = regiao
            if access:
                opcoes['aws_access_key_id'] = access
                opcoes['aws_secret_access_key'] = secret
                if token:
                    opcoes['aws_session_token'] = token
            elif perfil:
                opcoes['profile_name'] = perfil
            sessao = boto3.Session(**opcoes)
            cliente = sessao.client('s3', config=Config(connect_timeout=10, read_timeout=60,
                                                         retries={'max_attempts': 3}))
            self._listar_worker(cliente, bucket, '', True)
        except Exception as erro:
            self.eventos.put(('erro', self._mensagem_erro(erro)))

    def _listar_worker(self, cliente, bucket, prefixo, inicial=False):
        try:
            pastas, arquivos = [], []
            paginas = cliente.get_paginator('list_objects_v2').paginate(
                Bucket=bucket, Prefix=prefixo, Delimiter='/')
            for pagina in paginas:
                for pasta in pagina.get('CommonPrefixes', []):
                    chave = pasta['Prefix']
                    pastas.append({'key': chave, 'nome': chave[len(prefixo):].rstrip('/'), 'tipo': 'Pasta'})
                for objeto in pagina.get('Contents', []):
                    chave = objeto['Key']
                    if chave == prefixo or chave.endswith('/'):
                        continue
                    modificado = objeto.get('LastModified')
                    arquivos.append({'key': chave, 'nome': chave[len(prefixo):], 'tipo': 'Arquivo',
                                     'tamanho': objeto.get('Size', 0),
                                     'data': modificado.strftime('%d/%m/%Y %H:%M') if modificado else ''})
            pastas.sort(key=lambda i: i['nome'].casefold())
            arquivos.sort(key=lambda i: i['nome'].casefold())
            self.eventos.put(('lista', cliente, bucket, prefixo, pastas + arquivos))
        except Exception as erro:
            self.eventos.put(('erro', self._mensagem_erro(erro)))

    def navegar(self, prefixo):
        if self.ocupado or not self.cliente:
            return
        self._definir_ocupado(True)
        self.status_var.set('Carregando conteúdo do diretório...')
        self._iniciar_tarefa(self._listar_worker, self.cliente, self.bucket, prefixo)

    def voltar(self):
        if not self.prefixo:
            return
        anterior = '/'.join(self.prefixo.rstrip('/').split('/')[:-1])
        self.navegar(anterior + '/' if anterior else '')

    def atualizar(self):
        if self.cliente:
            self.navegar(self.prefixo)

    def abrir_pasta(self, _evento=None):
        selecionados = self.arvore.selection()
        if len(selecionados) == 1:
            item = self.itens.get(selecionados[0])
            if item and item['tipo'] == 'Pasta':
                self.navegar(item['key'])

    def escolher_destino(self):
        pasta = filedialog.askdirectory(initialdir=self.destino_var.get())
        if pasta:
            self.destino_var.set(pasta)

    def baixar(self):
        if self.ocupado or not self.cliente:
            return
        selecionados = [self.itens[i].copy() for i in self.arvore.selection() if i in self.itens]
        if not selecionados:
            messagebox.showinfo('Seleção', 'Selecione ao menos um arquivo ou diretório.')
            return
        texto_destino = self.destino_var.get().strip()
        if not texto_destino:
            messagebox.showwarning('Destino', 'Escolha uma pasta para salvar os downloads.')
            return
        destino = Path(texto_destino).expanduser()
        try:
            destino.mkdir(parents=True, exist_ok=True)
        except OSError as erro:
            messagebox.showerror('Destino', str(erro))
            return
        if not messagebox.askyesno('Confirmar download',
                'Baixar os itens selecionados?\n\nArquivos existentes com o mesmo nome serão substituídos.'):
            return
        self._definir_ocupado(True)
        self.progresso['value'] = 0
        self.status_var.set('Preparando relação de arquivos...')
        self._iniciar_tarefa(self._baixar_worker, selecionados, destino, self.cliente, self.bucket)

    @staticmethod
    def _caminho_seguro(relativo):
        partes = relativo.split('/')
        if (not relativo or relativo.startswith('/') or
                any(p in ('', '.', '..') or ':' in p or '\\' in p for p in partes) or
                any(p.rstrip(' .') != p for p in partes)):
            raise ValueError(f'Caminho inválido retornado pelo S3: {relativo}')
        return Path(*partes)

    def _baixar_worker(self, selecionados, destino, cliente, bucket):
        try:
            tarefas = []
            for item in selecionados:
                if item['tipo'] == 'Arquivo':
                    tarefas.append((item['key'], item['nome'], item.get('tamanho', 0)))
                else:
                    prefixo_pasta = item['key']
                    paginas = cliente.get_paginator('list_objects_v2').paginate(
                        Bucket=bucket, Prefix=prefixo_pasta)
                    for pagina in paginas:
                        for objeto in pagina.get('Contents', []):
                            chave = objeto['Key']
                            if not chave.endswith('/'):
                                relativo = item['nome'] + '/' + chave[len(prefixo_pasta):]
                                tarefas.append((chave, relativo, objeto.get('Size', 0)))
            if not tarefas:
                self.eventos.put(('concluido', 0))
                return
            tarefas = list({chave: (chave, relativo, tamanho)
                            for chave, relativo, tamanho in tarefas}.values())
            # Valida toda a lista antes de iniciar download de qualquer arquivo.
            destinos = [(chave, destino / self._caminho_seguro(relativo), relativo, tamanho)
                        for chave, relativo, tamanho in tarefas]
            total_bytes = sum(tamanho for _, _, _, tamanho in destinos)
            completos = 0
            for indice, (chave, alvo, relativo, tamanho) in enumerate(destinos, 1):
                alvo.parent.mkdir(parents=True, exist_ok=True)
                temporario = alvo.with_name(alvo.name + '.part')
                atual = 0

                def progresso(pedaco):
                    nonlocal atual
                    atual += pedaco
                    percentual = ((completos + atual) / total_bytes * 100) if total_bytes else (
                        (indice - 1) / len(destinos) * 100)
                    self.eventos.put(('progresso', min(100, percentual),
                                      f'Baixando {indice}/{len(destinos)}: {relativo}'))

                try:
                    cliente.download_file(bucket, chave, str(temporario), Callback=progresso)
                    os.replace(temporario, alvo)
                except Exception:
                    temporario.unlink(missing_ok=True)
                    raise
                completos += tamanho
                percentual = completos / total_bytes * 100 if total_bytes else indice / len(destinos) * 100
                self.eventos.put(('progresso', min(100, percentual),
                                  f'Concluído {indice}/{len(destinos)}: {relativo}'))
            self.eventos.put(('concluido', len(destinos)))
        except Exception as erro:
            self.eventos.put(('erro', self._mensagem_erro(erro)))

    @staticmethod
    def _mensagem_erro(erro):
        if isinstance(erro, NoCredentialsError):
            return 'Credenciais AWS não encontradas. Informe as chaves ou selecione um perfil configurado.'
        if isinstance(erro, PartialCredentialsError):
            return 'Credenciais incompletas. Confira as chaves e o token de sessão.'
        if isinstance(erro, ProfileNotFound):
            return f'Perfil AWS não encontrado: {erro}'
        if isinstance(erro, ClientError):
            codigo = erro.response.get('Error', {}).get('Code', '?')
            detalhe = erro.response.get('Error', {}).get('Message', str(erro))
            return f'Erro AWS ({codigo}): {detalhe}'
        if isinstance(erro, BotoCoreError):
            return f'Erro AWS: {erro}'
        return str(erro)

    def _processar_eventos(self):
        try:
            while True:
                evento = self.eventos.get_nowait()
                tipo = evento[0]
                if tipo == 'lista':
                    _, self.cliente, self.bucket, self.prefixo, itens = evento
                    self.arvore.delete(*self.arvore.get_children())
                    self.itens.clear()
                    for item in itens:
                        icone = '📁 ' if item['tipo'] == 'Pasta' else '📄 '
                        tamanho = (f"{item['tamanho'] / (1024 * 1024):,.2f} MB"
                                   if item['tipo'] == 'Arquivo' else '')
                        identificador = self.arvore.insert('', 'end', text=icone + item['nome'],
                            values=(item['tipo'], tamanho, item.get('data', '')))
                        self.itens[identificador] = item
                    self.caminho_var.set(f's3://{self.bucket}/{self.prefixo}')
                    self.conexao_var.set('● Conectado')
                    self.indicador.configure(fg=CORES['verde'])
                    self.status_var.set(f'{len(itens)} item(ns) encontrado(s). Abra pastas com duplo clique.')
                    self._definir_ocupado(False)
                elif tipo == 'progresso':
                    self.progresso['value'] = evento[1]
                    self.status_var.set(evento[2])
                elif tipo == 'concluido':
                    self.progresso['value'] = 100
                    self._definir_ocupado(False)
                    self.status_var.set(f'Download concluído: {evento[1]} arquivo(s).')
                    messagebox.showinfo('Download finalizado',
                                        f'{evento[1]} arquivo(s) baixado(s) com sucesso!')
                elif tipo == 'erro':
                    self._definir_ocupado(False)
                    if not self.cliente:
                        self.conexao_var.set('● Desconectado')
                        self.indicador.configure(fg=CORES['vermelho'])
                    self.status_var.set('Falha na operação.')
                    messagebox.showerror('Erro', evento[1])
        except queue.Empty:
            pass
        self.after(100, self._processar_eventos)


if __name__ == '__main__':
    ExploradorS3().mainloop()
